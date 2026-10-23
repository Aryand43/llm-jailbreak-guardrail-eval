"""Reviewed per-item annotations for sources whose release lacks harm domains or intents.

JBB's categories mix domains and SafeDialBench ships no detailed labels, so under the
team's labelling rules we assign one harm_domain per item directly (never via a category
crosswalk). One sidecar file per source, bound to the raw file's checksum, carries those
decisions. An item is emitted only once its entry is reviewed; everything else is held.
See docs/DATA_LOADERS.md.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from harmfloor import taxonomy
from harmfloor.schema import Annotation, Disposition

from ._utils import require_text, source_version

ENTRY_KEYS = {"disposition", "domain", "intent", "reason", "reviewed", "note"}


@dataclass(frozen=True)
class Resolved:
    """One reviewed annotation after validation. intent is "" when the source supplies it."""

    disposition: Disposition
    domain: str | None
    intent: str
    annotation: Annotation


def _unique_json_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate annotation key {key!r}")
        result[key] = value
    return result


def open_file(annotation_path: Path, expected_source_version: str, doc_hint: str) -> tuple[dict, str]:
    """Load the sidecar, check it is bound to the raw file, and return (entries, its sha256).

    Raises before any item is built: a missing file, bad JSON, a duplicate key, a stale
    checksum, or a malformed top level all fail loudly.
    """
    if not annotation_path.is_file():
        raise FileNotFoundError(
            f"{annotation_path}: reviewed annotations are required because {doc_hint}; "
            "see docs/DATA_LOADERS.md"
        )
    annotation_version = source_version(annotation_path)
    with annotation_path.open(encoding="utf-8") as stream:
        annotations = json.load(stream, object_pairs_hook=_unique_json_object)
    if not isinstance(annotations, dict) or annotations.get("source_version") != expected_source_version:
        raise ValueError(f"{annotation_path}: source_version must match {expected_source_version}")
    entries = annotations.get("items")
    if not isinstance(entries, dict):
        raise ValueError(f"{annotation_path}: items must be an object keyed by native id")
    return entries, annotation_version


def is_reviewed(entry: Any, context: str) -> bool:
    """True iff the entry is an object explicitly marked reviewed. Unreviewed drafts are held
    without further validation; a reviewed entry is fully checked in resolve."""
    if not isinstance(entry, dict) or type(entry.get("reviewed")) is not bool:
        raise ValueError(f"{context}: expected an object with a boolean 'reviewed'")
    return entry["reviewed"]


def resolve(entry: dict, context: str, version: str, *, require_intent: bool) -> Resolved:
    """Validate one reviewed entry under the labelling rules and return its decision.

    harmful needs a domain in configs/taxonomy.yaml (plus an intent when the source has
    none of its own); benign and excluded carry no domain; excluded needs a reason.
    """
    unknown = sorted(set(entry) - ENTRY_KEYS)
    if unknown:
        raise ValueError(f"{context}: unknown annotation keys {unknown}")
    disposition = entry.get("disposition")
    if disposition not in ("harmful", "benign", "excluded"):
        raise ValueError(f"{context}: disposition must be harmful, benign or excluded")

    if disposition == "harmful":
        domain = require_text(entry, "domain", context)
        if domain not in taxonomy.harm_domains():
            raise ValueError(f"{context}: domain {domain!r} is not a harm_domain in configs/taxonomy.yaml")
    else:
        if entry.get("domain") is not None:
            raise ValueError(f"{context}: domain is only for harmful items")
        domain = None

    intent = ""
    if disposition in ("harmful", "benign"):
        if require_intent:
            intent = require_text(entry, "intent", context)
    elif entry.get("intent") is not None:
        raise ValueError(f"{context}: excluded items take no intent")

    reason = entry.get("reason")
    if disposition == "excluded":
        reason = require_text(entry, "reason", context)

    annotation = Annotation(version=version, disposition=disposition, domain=domain, reason=reason)
    return Resolved(disposition=disposition, domain=domain, intent=intent, annotation=annotation)
