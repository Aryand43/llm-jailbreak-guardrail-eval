"""Annotation review workflow: worksheet export, import of reviewed rows, blind sample, Cohen's kappa.

    worksheet  data/annotations/worksheets/<source>.csv     (gitignored: regenerable, holds source text)
    drafts     data/annotations/drafts/<source>.jsonl        (unreviewed; never read by loaders)
    reviewed   data/annotations/<source>.jsonl               (the only file loaders read)

Agreement is computed on the blind second annotator's labels against the first reviewer's labels
*before* any reconciliation, so run `kappa` before editing either file after disagreements.
"""

from __future__ import annotations

import csv
import json
import random
from collections import Counter
from pathlib import Path

from harmfloor.data.annotations import ANNOTATIONS_DIR, Annotation, sha256_file

FIELDS = ["source_id", "context", "draft_verdict", "draft_harm_domain", "draft_intent", "draft_reason",
          "verdict", "harm_domain", "intent", "reason", "reviewer", "notes"]
BLIND_FIELDS = ["source_id", "context", "verdict", "harm_domain", "intent", "reason", "reviewer"]


def read_drafts(source: str, root: Path = ANNOTATIONS_DIR) -> dict[str, dict]:
    path = root / "drafts" / f"{source}.jsonl"
    if not path.exists():
        return {}
    return {(r := json.loads(line))["source_id"]: r for line in path.open(encoding="utf-8") if line.strip()}


def export_worksheet(source: str, contexts: dict[str, str], out: Path, root: Path = ANNOTATIONS_DIR,
                     ids: list[str] | None = None, blind: bool = False) -> int:
    """Write one row per item. blind=True drops the draft columns (second-annotator sample)."""
    drafts = {} if blind else read_drafts(source, root)
    out.parent.mkdir(parents=True, exist_ok=True)
    fields = BLIND_FIELDS if blind else FIELDS
    with out.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for sid in ids or list(contexts):
            d = drafts.get(sid, {})
            row = {"source_id": sid, "context": contexts[sid]}
            if not blind:
                row |= {f"draft_{k}": d.get(k) or "" for k in ("verdict", "harm_domain", "intent", "reason")}
            w.writerow(row)
    return len(ids or contexts)


def import_worksheet(source: str, worksheet: Path, raw_file: Path, root: Path = ANNOTATIONS_DIR) -> tuple[int, list[str]]:
    """Rows with a reviewer and a verdict become reviewed annotations; others are reported, not written.

    The reviewed file is rewritten from the worksheet, so the worksheet is the record of review.
    """
    sha = sha256_file(raw_file)
    drafts = read_drafts(source, root)
    good, problems = [], []
    with worksheet.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            sid = row["source_id"]
            if not row.get("reviewer", "").strip() or not row.get("verdict", "").strip():
                problems.append(f"{sid}: not reviewed yet")
                continue
            try:
                good.append(Annotation(
                    source_id=sid, source_sha256=sha, verdict=row["verdict"].strip(),
                    harm_domain=row["harm_domain"].strip() or None, intent=row["intent"].strip() or None,
                    reason=row["reason"].strip() or None,
                    drafted_by=drafts.get(sid, {}).get("drafted_by", f"human:{row['reviewer'].strip()}"),
                    reviewed=True, reviewer=row["reviewer"].strip(),
                ))
            except ValueError as e:
                problems.append(f"{sid}: {e.errors()[0]['msg'] if hasattr(e, 'errors') else e}")
    if good:
        (root / f"{source}.jsonl").write_text("".join(a.model_dump_json() + "\n" for a in good), encoding="utf-8")
    return len(good), problems


def blind_sample(ids_by_stratum: dict[str, list[str]], n: int, seed: int = 0) -> list[str]:
    """Random sample spread across strata (e.g. attack method) as evenly as their sizes allow."""
    rng = random.Random(seed)
    pools = {k: rng.sample(v, len(v)) for k, v in sorted(ids_by_stratum.items())}
    out: list[str] = []
    while len(out) < n and any(pools.values()):
        for k in pools:
            if pools[k] and len(out) < n:
                out.append(pools[k].pop())
    return out


def cohen_kappa(a: list[str], b: list[str]) -> float:
    if len(a) != len(b) or not a:
        raise ValueError("need two equal-length, non-empty label lists")
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in ca.keys() | cb.keys()) / n**2
    return 1.0 if pe == 1 else (po - pe) / (1 - pe)


def agreement(first: dict[str, Annotation], blind_ws: Path) -> dict[str, float | int]:
    """Kappa on verdict, and on harm domain over items both annotators called harmful."""
    with blind_ws.open(encoding="utf-8", newline="") as f:
        second = {r["source_id"]: r for r in csv.DictReader(f) if r.get("verdict", "").strip()}
    both = [s for s in second if s in first]
    v1 = [first[s].verdict for s in both]
    v2 = [second[s]["verdict"].strip() for s in both]
    harm = [s for s in both if first[s].verdict == "harmful" and second[s]["verdict"].strip() == "harmful"]
    d1 = [first[s].harm_domain for s in harm]
    d2 = [second[s]["harm_domain"].strip() for s in harm]
    return {"n": len(both), "kappa_verdict": cohen_kappa(v1, v2),
            "n_domain": len(harm), "kappa_domain": cohen_kappa(d1, d2) if harm else float("nan")}

