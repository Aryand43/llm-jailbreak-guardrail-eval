"""Pilot diagnostics over frozen AI drafts; never creates human-reviewed annotations."""
from collections import Counter
import math
from pathlib import Path

from ._utils import read_json
from .annotations import Annotation, sha256_file
from .review import _read_worksheet, cohen_kappa


def compare_ai_drafts(first_file: Path, second_worksheet: Path, raw_file: Path) -> dict:
    """Compare pre-existing drafts with the returned AI sheet; held is not a verdict.

    The caller must freeze first_file before viewing the returned sheet. A source-bound
    manifest validates the second sheet. This diagnostic cannot satisfy human agreement.
    """
    second_rows, meta = _read_worksheet(second_worksheet, "safedialbench", raw_file)
    if not meta["blind"]:
        raise ValueError("expected a blind worksheet")
    sha = sha256_file(raw_file)
    first = {}
    for line in first_file.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        row = read_json(line)
        sid = row["source_id"]
        if sid in first:
            raise ValueError("duplicate first-draft ID")
        if row.get("reviewed") is not False:
            raise ValueError("AI diagnostic expects explicitly unreviewed first drafts")
        if row.get("source_sha256") != sha:
            raise ValueError("first draft belongs to a different raw snapshot")
        first[sid] = row
    records = []
    for row in second_rows:
        sid = row["source_id"]
        if not row["verdict"].strip():
            raise ValueError(f"{sid}: returned diagnostic sheet has an unfinished verdict")
        author = row["reviewer"].strip()
        if not author:
            raise ValueError(f"{sid}: missing reported AI reviewer identity")
        second = Annotation(source_id=sid, source_sha256=sha, verdict=row["verdict"].strip(),
                            harm_domain=row["harm_domain"].strip() or None,
                            intent=row["intent"].strip() or None,
                            reason=row["reason"].strip() or None,
                            drafted_by=author, reviewed=False, reviewer=None)
        if second.verdict != "excluded" and not second.intent:
            raise ValueError(f"{sid}: included SafeDialBench draft needs intent")
        draft = first.get(sid)
        initial = None
        if draft and draft.get("verdict"):
            initial = Annotation.model_validate({k: draft.get(k) for k in Annotation.model_fields})
        records.append({"source_id": sid, "first_verdict": initial.verdict if initial else None,
                        "second_verdict": second.verdict,
                        "first_domain": initial.harm_domain if initial else None,
                        "second_domain": second.harm_domain,
                        "first_intent": draft.get("intent") if draft else None,
                        "second_intent": second.intent,
                        "first_reason": (draft.get("reason") or draft.get("note")) if draft else None,
                        "second_reason": second.reason,
                        "first_drafter": draft.get("drafted_by") if draft else None,
                        "second_drafter": author,
                        "status": "first_held" if initial is None else (
                            "verdict_disagreement" if initial.verdict != second.verdict else (
                            "domain_disagreement" if initial.harm_domain != second.harm_domain else "agree"))})
    paired = [r for r in records if r["first_verdict"] is not None]
    harmful = [r for r in paired if r["first_verdict"] == r["second_verdict"] == "harmful"]
    def metric(rows, key):
        a, b = [r[f"first_{key}"] for r in rows], [r[f"second_{key}"] for r in rows]
        kappa = cohen_kappa(a, b) if rows else float("nan")
        return {"n": len(rows), "matches": sum(x == y for x,y in zip(a,b)),
                "agreement": sum(x == y for x,y in zip(a,b))/len(rows) if rows else None,
                "kappa": kappa if math.isfinite(kappa) else None,
                "first_counts": dict(Counter(a)), "second_counts": dict(Counter(b))}
    return {"comparison": "AI draft vs AI; not human agreement", "human_agreement_pending": True,
            "first_snapshot_sha256": sha256_file(first_file),
            "returned_worksheet_sha256": sha256_file(second_worksheet),
            "raw_sha256": sha, "sampled": len(records),
            "first_held_ids": [r["source_id"] for r in records if r["first_verdict"] is None],
            "returned_counts": dict(Counter(r["second_verdict"] for r in records)),
            "verdict": metric(paired, "verdict"), "domain": metric(harmful, "domain"),
            "records": records}
