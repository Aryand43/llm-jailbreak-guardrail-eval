"""Strict reviewed JSONL annotations, separate from incomplete AI drafts."""
from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator

from harmfloor import taxonomy
from harmfloor.schema import Annotation as Provenance
from ._utils import read_json

ANNOTATIONS_DIR = Path(__file__).resolve().parents[2] / "data" / "annotations"
Verdict = Literal["harmful", "benign", "excluded"]


class Annotation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    source_id: str
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    verdict: Verdict
    harm_domain: str | None = None
    intent: str | None = None
    reason: str | None = None
    drafted_by: str
    reviewed: StrictBool = False
    reviewer: str | None = None

    @field_validator("source_id", "drafted_by")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("source_id and drafted_by must not be blank")
        return value

    @field_validator("intent", "reason", "reviewer")
    @classmethod
    def optional_text(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("provided intent, reason and reviewer must not be blank")
        return value

    @model_validator(mode="after")
    def consistent(self) -> "Annotation":
        if (self.verdict == "harmful") != (self.harm_domain is not None):
            raise ValueError("harm_domain is required for harmful and forbidden otherwise")
        if self.harm_domain is not None and self.harm_domain not in taxonomy.harm_domains():
            raise ValueError(f"unknown harm_domain {self.harm_domain!r}")
        if self.verdict in {"benign", "excluded"} and not self.reason:
            raise ValueError("benign and excluded annotations need a reason")
        if self.verdict == "excluded" and self.intent is not None:
            raise ValueError("excluded annotations take no intent")
        if self.reviewed and not self.reviewer:
            raise ValueError("reviewed annotations need a reviewer")
        return self


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


class AnnotationSet(dict[str, Annotation]):
    version: str

    def provenance(self, sid: str) -> Provenance:
        a = self[sid]
        if not a.reviewed or a.verdict == "excluded":
            raise ValueError("only reviewed, included decisions can become item provenance")
        return Provenance(version=self.version, disposition=a.verdict, domain=a.harm_domain,
                          reason=a.reason, source_id=sid, source_sha256=a.source_sha256,
                          drafted_by=a.drafted_by, reviewer=a.reviewer, intent=a.intent)


def load_annotations(source: str, source_sha256: str, root: Path = ANNOTATIONS_DIR,
                     *, valid_ids: set[str] | None = None) -> AnnotationSet:
    path = root / f"{source}.jsonl"
    out = AnnotationSet()
    if not path.exists():
        return out
    data = path.read_bytes()
    out.version = "sha256:" + hashlib.sha256(data).hexdigest()
    for n, line in enumerate(data.decode("utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        a = Annotation.model_validate(read_json(line))
        if a.source_id in out:
            raise ValueError(f"{path}:{n}: duplicate annotation for {a.source_id}")
        if valid_ids is not None and a.source_id not in valid_ids:
            raise ValueError(f"{path}:{n}: annotation ID {a.source_id!r} not in source")
        if a.source_sha256 != source_sha256:
            raise ValueError(f"{path}:{n}: annotation made against a different raw file; re-check it")
        if source == "safedialbench" and a.reviewed and a.verdict != "excluded" and not a.intent:
            raise ValueError(f"{path}:{n}: reviewed SafeDialBench annotation needs an intent")
        out[a.source_id] = a
    return out


def gate(annotation: Annotation | None) -> str | None:
    if annotation is None:
        return "no annotation"
    if not annotation.reviewed:
        return "annotation not reviewed"
    if annotation.verdict == "excluded":
        return f"excluded: {annotation.reason}"
    return None
