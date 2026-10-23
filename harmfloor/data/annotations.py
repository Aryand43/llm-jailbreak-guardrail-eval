"""Reviewed annotations: our own labels for sources whose native labels do not fit the analysis.

One JSONL file per source at data/annotations/<source>.jsonl, one record per source item.
An item enters evaluation only if its record exists, matches the raw file's sha256, and is
reviewed by a person. Everything else is held back with a reason; nothing is labelled silently.

The verdict decides the item's role, so an item cannot be harmful while its annotation says
benign: the loader takes is_benign and harm_domain from the annotation and nowhere else.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

from harmfloor import taxonomy

ANNOTATIONS_DIR = Path(__file__).resolve().parents[2] / "data" / "annotations"

Verdict = Literal["harmful", "benign", "excluded"]


class Annotation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    source_id: str
    source_sha256: str  # raw file the label was made against; a changed file invalidates it
    verdict: Verdict
    harm_domain: str | None = None  # required iff harmful
    intent: str | None = None  # one-line plain request; required for multi-turn sources unless excluded
    reason: str | None = None  # required for excluded; recommended for borderline calls
    drafted_by: str  # "human:<name>" or the model + prompt version that drafted it
    reviewed: bool = False
    reviewer: str | None = None

    @model_validator(mode="after")
    def _consistent(self) -> "Annotation":
        if (self.verdict == "harmful") != (self.harm_domain is not None):
            raise ValueError(f"{self.source_id}: harm_domain is required for harmful and forbidden otherwise")
        if self.harm_domain is not None and self.harm_domain not in taxonomy.load()["harm_domains"]:
            raise ValueError(f"{self.source_id}: unknown harm_domain {self.harm_domain!r}")
        if self.verdict == "excluded" and not self.reason:
            raise ValueError(f"{self.source_id}: excluded items need a reason")
        if self.reviewed and not self.reviewer:
            raise ValueError(f"{self.source_id}: reviewed annotations need a reviewer")
        return self


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_annotations(source: str, source_sha256: str, root: Path = ANNOTATIONS_DIR) -> dict[str, Annotation]:
    """Annotations for one source, keyed by source_id. Missing file = no annotations yet."""
    path = root / f"{source}.jsonl"
    if not path.exists():
        return {}
    out: dict[str, Annotation] = {}
    with path.open(encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if not line.strip():
                continue
            a = Annotation.model_validate(json.loads(line))
            if a.source_id in out:
                raise ValueError(f"{path}:{n}: duplicate annotation for {a.source_id}")
            if a.source_sha256 != source_sha256:
                raise ValueError(f"{path}:{n}: annotation made against a different raw file; re-check it")
            out[a.source_id] = a
    return out


def gate(annotation: Annotation | None) -> str | None:
    """Why an item is held, or None if it may enter evaluation."""
    if annotation is None:
        return "no annotation"
    if not annotation.reviewed:
        return "annotation not reviewed"
    if annotation.verdict == "excluded":
        return f"excluded: {annotation.reason}"
    return None
