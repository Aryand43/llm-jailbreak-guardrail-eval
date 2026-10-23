"""Load the official JBB harmful behavior CSV with reviewed per-item harm domains.

JBB's ten categories mix harm domains (a nuclear-weapons request sits under
"Government decision-making"), so under the team's labelling rules we assign one
harm_domain per behavior directly through a reviewed annotations.json sidecar rather
than a category crosswalk. The category is kept verbatim in native_labels. The CSV
Goal is already a standalone request, so it is the intent and the sole user turn.
Behaviors without a reviewed entry are held. See docs/DATA_LOADERS.md.
"""

from __future__ import annotations

import csv
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from harmfloor import taxonomy
from harmfloor.schema import Item, Turn

from . import _annotations
from ._utils import require_text, review_flags, source_version
from .registry import register

SOURCE = "jbb_behaviors"
FILENAME = "harmful-behaviors.csv"
ANNOTATIONS_FILENAME = "annotations.json"
REQUIRED_COLUMNS = {"Index", "Goal", "Target", "Behavior", "Category", "Source"}
_DOC_HINT = "JBB's categories mix more than one harm domain"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Coverage:
    """How the annotation file splits the behaviors, by source_id (the Behavior name)."""

    harmful: tuple[str, ...]
    benign: tuple[str, ...]
    held: tuple[str, ...]  # no annotation entry, or reviewed: false
    excluded: tuple[str, ...]

    def __repr__(self) -> str:
        return (f"Coverage(harmful={len(self.harmful)}, benign={len(self.benign)}, "
                f"held={len(self.held)}, excluded={len(self.excluded)})")


def read_behaviors(path: Path) -> Iterator[dict[str, str]]:
    """Validate native CSV rows without assigning any harm domain."""
    seen: set[str] = set()
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        fields = reader.fieldnames or []
        missing = REQUIRED_COLUMNS - set(fields)
        if missing or len(fields) != len(set(fields)):
            raise ValueError(f"{path}: invalid CSV header; missing columns: {sorted(missing)}")
        for line, row in enumerate(reader, start=2):
            context = f"{path}: record {line - 1}"
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"{context}: row does not match the CSV header")
            source_id = require_text(row, "Behavior", context)
            if source_id in seen:
                raise ValueError(f"{context}: duplicate Behavior {source_id!r}")
            seen.add(source_id)
            require_text(row, "Goal", context)
            require_text(row, "Category", context)
            require_text(row, "Index", context)
            require_text(row, "Source", context)
            yield row
    if not seen:
        raise ValueError(f"{path}: no behavior records")


def resolve(raw_dir: Path) -> tuple[list[Item], Coverage]:
    """Validate the annotation file and split the behaviors into harmful, benign, held, excluded."""
    path = raw_dir / FILENAME
    version = source_version(path)
    annotation_path = raw_dir / ANNOTATIONS_FILENAME
    entries, annotation_version = _annotations.open_file(annotation_path, version, _DOC_HINT)
    rows = list(read_behaviors(path))
    ids = {row["Behavior"] for row in rows}
    unknown = sorted(entries.keys() - ids)
    if unknown:
        raise ValueError(f"{annotation_path}: Behavior ids not in the CSV: {unknown[:10]}")
    family = taxonomy.attack_family(SOURCE, "direct")
    items, harmful, benign, held, excluded = [], [], [], [], []
    for row in rows:
        source_id = row["Behavior"]
        context = f"{annotation_path}: {source_id!r}"
        entry = entries.get(source_id)
        if entry is None or not _annotations.is_reviewed(entry, context):
            held.append(source_id)
            continue
        decision = _annotations.resolve(entry, context, annotation_version, require_intent=False)
        if decision.disposition == "excluded":
            excluded.append(source_id)
            continue
        labels = {key: value for key, value in row.items() if key not in {"Goal", "Target"}}
        item_id = f"{SOURCE}:{source_id}"
        items.append(Item(
            item_id=item_id,
            source=SOURCE,
            source_id=source_id,
            source_version=version,
            intent_id=item_id,
            intent=row["Goal"],
            turns=[Turn(role="user", content=row["Goal"])],
            is_benign=decision.disposition == "benign",
            attack_family=family.value,
            attack_method=None,
            harm_domain=decision.domain,
            native_labels=labels,
            needs_review=review_flags(attack_family=family),
            annotation=decision.annotation,
            license="MIT",
        ))
        (benign if decision.disposition == "benign" else harmful).append(source_id)
    report = Coverage(tuple(harmful), tuple(benign), tuple(held), tuple(excluded))
    return items, report


def coverage(raw_dir: Path) -> Coverage:
    """Behavior ids that are harmful, benign, held and excluded under the current annotations."""
    return resolve(raw_dir)[1]


@register(SOURCE)
def load(raw_dir: Path) -> Iterator[Item]:
    """Yield one direct-request Item per reviewed, non-excluded behavior."""
    items, report = resolve(raw_dir)
    (logger.warning if report.held else logger.info)("%s: %s", SOURCE, report)
    yield from items
