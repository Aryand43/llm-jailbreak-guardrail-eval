"""Source-bound review worksheets. Import is transactional; blank verdict withdraws approval."""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import random
from collections import Counter
from pathlib import Path

from harmfloor.data.annotations import ANNOTATIONS_DIR, Annotation, sha256_file
from ._utils import atomic_write, read_json
from .sources import contexts, source_id, source_rows

FIELDS = ["source_id", "context", "draft_verdict", "draft_harm_domain", "draft_intent", "draft_reason",
          "draft_note", "verdict", "harm_domain", "intent", "reason", "reviewer", "notes"]
BLIND_FIELDS = ["source_id", "context", "verdict", "harm_domain", "intent", "reason", "reviewer"]


def manifest_path(worksheet: Path) -> Path:
    return worksheet.with_suffix(".manifest.json")


def read_drafts(source: str, root: Path = ANNOTATIONS_DIR) -> dict[str, dict]:
    path = root / "drafts" / f"{source}.jsonl"
    if not path.exists():
        return {}
    result = {}
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        row = read_json(line)
        if not isinstance(row, dict) or not isinstance(row.get("source_id"), str):
            raise ValueError(f"{path}: draft needs a string source_id")
        if row["source_id"] in result:
            raise ValueError(f"{path}: duplicate draft source_id")
        if row.get("reviewed") is not False:
            raise ValueError(f"{path}: drafts must explicitly remain reviewed: false")
        result[row["source_id"]] = row
    return result


def export_worksheet(source: str, raw_file: Path, out: Path, root: Path = ANNOTATIONS_DIR,
                     ids: list[str] | None = None, blind: bool = False,
                     sampling: dict | None = None) -> int:
    """Export immutable reference context plus editable labels and a source-bound manifest.

    Existing worksheets are never overwritten. Choose a new output name for another round.
    """
    meta_path = manifest_path(out)
    if out.exists() or meta_path.exists():
        raise FileExistsError(f"{out}: preserve the existing review and use a new worksheet name")
    sha = sha256_file(raw_file)
    ctx, _ = contexts(source, raw_file)
    selected = list(ctx) if ids is None else ids
    if not selected or len(set(selected)) != len(selected) or set(selected) - ctx.keys():
        raise ValueError("worksheet selection must contain unique existing source IDs")
    drafts = {} if blind else read_drafts(source, root)
    if drafts.keys() - ctx.keys():
        raise ValueError("draft contains IDs not in raw source")
    fields = BLIND_FIELDS if blind else FIELDS
    stream = io.StringIO(newline="")
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    authors = {}
    for sid in selected:
        draft = drafts.get(sid, {})
        if draft and draft.get("source_sha256") != sha:
            raise ValueError(f"{sid}: draft belongs to a different raw snapshot")
        authors[sid] = draft.get("drafted_by")
        row = {"source_id": sid, "context": ctx[sid]}
        if not blind:
            row.update({f"draft_{key}": draft.get(key) or "" for key in
                        ("verdict", "harm_domain", "intent", "reason", "note")})
        writer.writerow(row)
    if sha256_file(raw_file) != sha:
        raise ValueError("source changed while worksheet was exported")
    manifest = {"format": 1, "source": source, "source_sha256": sha, "ids": selected,
                "blind": blind, "drafted_by": authors, "fields": fields,
                "context_sha256": {sid: hashlib.sha256(ctx[sid].encode()).hexdigest() for sid in selected}}
    if sampling is not None:
        manifest["sampling"] = sampling
    atomic_write(meta_path, json.dumps(manifest, indent=2) + "\n")
    atomic_write(out, stream.getvalue())
    return len(selected)


def _read_worksheet(worksheet: Path, source: str, raw_file: Path) -> tuple[list[dict], dict]:
    meta = read_json(manifest_path(worksheet).read_text(encoding="utf-8"))
    if meta.get("format") != 1 or meta.get("source") != source:
        raise ValueError("unsupported worksheet manifest or wrong source")
    sha = sha256_file(raw_file)
    if meta.get("source_sha256") != sha:
        raise ValueError("raw file changed since worksheet export; re-export and re-review")
    ctx, _ = contexts(source, raw_file)
    ids = meta.get("ids", [])
    if not ids or len(set(ids)) != len(ids) or set(ids) - ctx.keys():
        raise ValueError("invalid worksheet source ID manifest")
    with worksheet.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != meta.get("fields"):
            raise ValueError("worksheet columns changed; use the exported format")
        rows = list(reader)
    seen = set()
    for row in rows:
        if None in row or any(value is None for value in row.values()):
            raise ValueError("malformed worksheet row")
        sid = row["source_id"]
        if sid in seen or sid not in ids:
            raise ValueError(f"duplicate or unknown worksheet ID {sid!r}")
        seen.add(sid)
        if row["context"] != ctx[sid] or hashlib.sha256(ctx[sid].encode()).hexdigest() != meta["context_sha256"].get(sid):
            raise ValueError(f"{sid}: source context was changed in the worksheet")
    if seen != set(ids):
        raise ValueError("worksheet rows are missing; blank the verdict to withdraw an approval")
    return rows, meta


def _decision(row: dict, source: str, sha: str, drafted_by: str | None) -> Annotation:
    reviewer = row["reviewer"].strip()
    if not reviewer:
        raise ValueError("completed decisions need a nonblank reviewer")
    a = Annotation(source_id=row["source_id"], source_sha256=sha, verdict=row["verdict"].strip(),
                   harm_domain=row["harm_domain"].strip() or None, intent=row["intent"].strip() or None,
                   reason=row["reason"].strip() or None, drafted_by=drafted_by or f"human:{reviewer}",
                   reviewed=True, reviewer=reviewer)
    if source == "safedialbench" and a.verdict != "excluded" and not a.intent:
        raise ValueError("included SafeDialBench decisions require a standalone intent")
    return a


def import_worksheet(source: str, worksheet: Path, raw_file: Path,
                     root: Path = ANNOTATIONS_DIR) -> tuple[int, list[str]]:
    """Replace the FULL reviewed snapshot. Blank verdicts withdraw approval, even for all rows.

    Any invalid completed row aborts without altering the prior file. Import only full first-
    reviewer worksheets; a blind subset must never replace the source's approved set.
    """
    rows, meta = _read_worksheet(worksheet, source, raw_file)
    raw_rows = {source_id(source, r): r for r in source_rows(source, raw_file)}
    if meta["blind"] or set(meta["ids"]) != set(raw_rows):
        raise ValueError("only a full first-reviewer worksheet may replace reviewed annotations")
    good, problems = [], []
    for row in rows:
        if not row["verdict"].strip():
            continue
        sid = row["source_id"]
        try:
            a = _decision(row, source, meta["source_sha256"], meta["drafted_by"].get(sid))
            raw = raw_rows[sid]
            if source == "jbb_behaviors" and a.intent is not None and a.intent != raw["Goal"]:
                raise ValueError("JBB intent must equal the source Goal (or be left empty)")
            if source == "safedialbench" and a.verdict != "excluded":
                history = raw["history"]
                if any(not t["user"].strip() for t in history) or any(not t["bot"].strip() for t in history[:-1]):
                    raise ValueError("blank source turn; hold or explicitly exclude after review")
            good.append(a)
        except ValueError as error:
            problems.append(f"{sid}: {error}")
    if problems:
        return 0, problems
    if sha256_file(raw_file) != meta["source_sha256"]:
        raise ValueError("raw file changed during import")
    destination = root / f"{source}.jsonl"
    content = "".join(a.model_dump_json() + "\n" for a in good)
    if destination.exists():
        old = destination.read_bytes()
        snapshot = root / "history" / source / (hashlib.sha256(old).hexdigest() + ".jsonl")
        if not snapshot.exists():
            atomic_write(snapshot, old.decode("utf-8"))
    atomic_write(destination, content)
    return len(good), []


def blind_sample(ids_by_stratum: dict[str, list[str]], n: int, seed: int = 0,
                 required_ids: list[str] | None = None) -> list[str]:
    if n <= 0:
        raise ValueError("sample size must be positive")
    all_ids = [sid for ids in ids_by_stratum.values() for sid in ids]
    if len(all_ids) != len(set(all_ids)):
        raise ValueError("sampling strata contain duplicate IDs")
    required = list(required_ids or [])
    if len(required) != len(set(required)) or set(required) - set(all_ids):
        raise ValueError("required IDs must be unique and present in sampling strata")
    if len(required) > n:
        raise ValueError("required IDs exceed requested sample size")
    rng = random.Random(seed)
    pools = {k: rng.sample([sid for sid in v if sid not in required],
                           len([sid for sid in v if sid not in required]))
             for k, v in sorted(ids_by_stratum.items())}
    counts = {k: sum(sid in required for sid in v) for k, v in ids_by_stratum.items()}
    out = required.copy()
    while len(out) < n and any(pools.values()):
        key = min((k for k in pools if pools[k]), key=lambda k: (counts[k], k))
        out.append(pools[key].pop())
        counts[key] += 1
    return out


def cohen_kappa(a: list[str], b: list[str]) -> float:
    if len(a) != len(b) or not a:
        raise ValueError("need two equal-length, non-empty label lists")
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in ca.keys() | cb.keys()) / n**2
    return float("nan") if pe == 1 else (po - pe) / (1 - pe)


def agreement(first: dict[str, Annotation], blind_ws: Path, *, source: str,
              raw_file: Path) -> dict:
    rows, meta = _read_worksheet(blind_ws, source, raw_file)
    if not meta["blind"]:
        raise ValueError("agreement requires a blind second-review worksheet")
    second = {r["source_id"]: _decision(r, source, meta["source_sha256"], None)
              for r in rows if r["verdict"].strip()}
    both = [sid for sid in second if sid in first and first[sid].reviewed]
    if any(first[sid].source_sha256 != meta["source_sha256"] for sid in both):
        raise ValueError("first and second reviews refer to different source snapshots")
    v1, v2 = [first[s].verdict for s in both], [second[s].verdict for s in both]
    harm = [s for s in both if first[s].verdict == second[s].verdict == "harmful"]
    d1, d2 = [first[s].harm_domain for s in harm], [second[s].harm_domain for s in harm]
    def summary(a, b):
        kappa = cohen_kappa(a, b) if a else float("nan")
        return {"n": len(a), "agreement": sum(x == y for x, y in zip(a, b))/len(a) if a else None,
                "kappa": kappa if math.isfinite(kappa) else None,
                "first_counts": dict(Counter(a)), "second_counts": dict(Counter(b))}
    return {"sampled": len(rows), "second_completed": len(second),
            "verdict": summary(v1, v2), "domain": summary(d1, d2)}
