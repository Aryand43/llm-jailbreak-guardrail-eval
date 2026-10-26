"""Benign prompts for the false-positive-rate constraint (refusal threshold calibration).

These sources are built to be benign, so their own labels are used directly: no annotation gate.

  or_bench: SoK's 1,000-prompt OR-Bench sample, read from SoK's release so the IDs match theirs
            (all 1,000 are verbatim in or-bench-80k; it is not the hard-1k split).
  xstest:   the 250 safe prompts; the 200 unsafe contrast prompts are left out.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from harmfloor import taxonomy
from harmfloor.data.annotations import sha256_file
from harmfloor.data.registry import LoadResult, register
from harmfloor.schema import Item, Turn
from ._utils import read_json, require_text, review_flags


def _benign(source: str, sid: str, text: str, sha: str, labels: dict[str, str], license: str) -> Item:
    family = taxonomy.attack_family(source, "")
    return Item(
        item_id=f"{source}:{sid}",
        source=source,
        source_id=sid,
        source_version=f"sha256:{sha}",
        intent_id=f"{source}:{sid}",
        intent=text,
        turns=[Turn(role="user", content=text)],
        is_benign=True,
        attack_family=family.value,
        needs_review=review_flags(attack_family=family),
        harm_domain=None,
        native_labels=labels,
        license=license,
    )


@register("or_bench")
def load_or_bench(raw_dir: Path) -> LoadResult:
    path = raw_dir / "OR-Bench.json"
    sha = sha256_file(path)
    rows = read_json(path.read_text(encoding="utf-8-sig"))
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"{path}: expected nonempty OR-Bench list")
    ids = set()
    for row in rows:
        sid = row.get("index") if isinstance(row, dict) else None
        if type(sid) is not int or sid < 0 or sid in ids:
            raise ValueError(f"{path}: invalid or duplicate index")
        ids.add(sid)
        require_text(row, "goal", str(path)); require_text(row, "category", str(path))
    return LoadResult(items=[
        _benign("or_bench", str(r["index"]), r["goal"], sha, {"category": r["category"]}, "CC-BY-4.0")
        for r in rows
    ])


@register("xstest")
def load_xstest(raw_dir: Path) -> LoadResult:
    path = raw_dir / "xstest_prompts.csv"
    sha = sha256_file(path)
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        if not {"id", "prompt", "type", "label", "focus"}.issubset(fields) or len(fields) != len(set(fields)):
            raise ValueError(f"{path}: invalid XSTest header")
        rows, ids = [], set()
        for row in reader:
            if None in row or any(v is None for v in row.values()):
                raise ValueError(f"{path}: malformed CSV row")
            sid = require_text(row, "id", str(path))
            if sid in ids:
                raise ValueError(f"{path}: duplicate id")
            ids.add(sid)
            require_text(row, "prompt", str(path))
            if row["label"] not in {"safe", "unsafe"}:
                raise ValueError(f"{path}: unknown safe/unsafe label")
            if row["label"] == "safe":
                rows.append(row)
        if not ids:
            raise ValueError(f"{path}: no XSTest records")
    return LoadResult(items=[
        _benign("xstest", r["id"], r["prompt"], sha, {"type": r["type"], "focus": r["focus"]}, "CC-BY-4.0")
        for r in rows
    ])
