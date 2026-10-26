"""Raw-source validation shared by loaders, worksheet export and draft migration."""
from __future__ import annotations
import csv
from pathlib import Path
from ._utils import read_json, require_text

JBB_COLUMNS = {"Index", "Goal", "Target", "Behavior", "Category", "Source"}


def read_jbb(path: Path) -> list[dict[str, str]]:
    rows, ids, behaviors = [], set(), set()
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames or []
        if not JBB_COLUMNS.issubset(fields) or len(fields) != len(set(fields)):
            raise ValueError(f"{path}: invalid CSV header")
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"{path}: row does not match CSV header")
            for key in JBB_COLUMNS - {"Target"}:
                require_text(row, key, str(path))
            sid = row["Index"]
            if not sid.isdecimal() or str(int(sid)) != sid:
                raise ValueError(f"{path}: Index must be a canonical nonnegative integer")
            if sid in ids or row["Behavior"] in behaviors:
                raise ValueError(f"{path}: duplicate Index or Behavior")
            ids.add(sid)
            behaviors.add(row["Behavior"])
            rows.append(row)
    if not rows:
        raise ValueError(f"{path}: no behavior records")
    return rows


def read_safedial(path: Path) -> list[dict]:
    rows, ids = [], set()
    with path.open(encoding="utf-8-sig") as stream:
        for n, line in enumerate(stream, 1):
            if not line.strip():
                continue
            context = f"{path}:{n}"
            row = read_json(line)
            if not isinstance(row, dict):
                raise ValueError(f"{context}: expected a JSON object")
            sid = row.get("id")
            if type(sid) is not int or sid < 1:
                raise ValueError(f"{context}: id must be a positive integer")
            if sid in ids:
                raise ValueError(f"{context}: duplicate id {sid}")
            for key in ("task", "method", "model_type", "scene"):
                require_text(row, key, context)
            history = row.get("history")
            if not isinstance(history, list) or len(history) < 2:
                raise ValueError(f"{context}: history must contain at least two exchanges")
            for turn in history:
                if not isinstance(turn, dict) or any(not isinstance(turn.get(k), str) for k in ("user", "bot")):
                    raise ValueError(f"{context}: history requires string user/bot fields")
            ids.add(sid)
            rows.append(row)
    if not rows:
        raise ValueError(f"{path}: no dialogue records")
    return rows


def source_rows(source: str, path: Path) -> list[dict]:
    if source == "jbb_behaviors":
        return read_jbb(path)
    if source == "safedialbench":
        return read_safedial(path)
    raise ValueError(f"annotation workflow does not support {source!r}")


def source_id(source: str, row: dict) -> str:
    return row["Index"] if source == "jbb_behaviors" else str(row["id"])


def contexts(source: str, path: Path) -> tuple[dict[str, str], dict[str, list[str]]]:
    result, strata = {}, {}
    for row in source_rows(source, path):
        sid = source_id(source, row)
        if source == "jbb_behaviors":
            result[sid] = f"[{row['Category']}] {row['Goal']}"
            stratum = row["Category"]
        else:
            history = row["history"]
            lines = [f"[{row['task']} / {row['method']}] SOURCE REFERENCE CONTEXT"]
            for i, turn in enumerate(history):
                lines.append(f"User {i + 1}: {turn['user']}")
                if i < len(history) - 1:
                    lines.append(f"Source assistant {i + 1}: {turn['bot']}")
            result[sid] = "\n".join(lines)
            stratum = f"{row['method']} / {row['task']}"
        strata.setdefault(stratum, []).append(sid)
    return result, strata
