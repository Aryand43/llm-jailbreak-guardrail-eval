"""Load English SafeDialBench histories with reviewed harm domains and intents.

The upstream English release has only six broad themes, no second-tier harm labels and
no standalone intents. Under the team's labelling rules a version-bound annotations_en.json
sidecar assigns one harm_domain per dialogue directly, plus a standalone intent; protective
or general dialogues are kept as is_benign for the false-positive test, and rude/satire/
blasphemy-only or unusable ones are excluded. Dialogues without a reviewed entry are held.
Stored final bot replies never enter target prompts. See docs/DATA_LOADERS.md.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from harmfloor import taxonomy
from harmfloor.schema import Item, Turn

from . import _annotations
from ._utils import require_text, review_flags, source_version
from .registry import register

SOURCE = "safedialbench"
FILENAME = "datasets_en.jsonl"
ANNOTATIONS_FILENAME = "annotations_en.json"
_DOC_HINT = "the upstream English file has no second-tier harm labels or standalone intents"

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Coverage:
    """How the annotation file splits the English dialogues, by native ID."""

    harmful: tuple[str, ...]
    benign: tuple[str, ...]
    held: tuple[str, ...]  # no annotation entry, or reviewed: false
    excluded: tuple[str, ...]  # reviewed exclusions (rude/satire/blasphemy-only, or unusable)

    def __repr__(self) -> str:
        return (f"Coverage(harmful={len(self.harmful)}, benign={len(self.benign)}, "
                f"held={len(self.held)}, excluded={len(self.excluded)})")


def read_dialogues(path: Path) -> Iterator[dict[str, Any]]:
    """Validate native English records without guessing missing evaluation labels."""
    seen: set[int] = set()
    with path.open(encoding="utf-8-sig") as stream:
        for line_number, line in enumerate(stream, start=1):
            if not line.strip():
                continue
            context = f"{path}:{line_number}"
            try:
                row = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"{context}: invalid JSON: {error.msg}") from error
            if not isinstance(row, dict):
                raise ValueError(f"{context}: expected a JSON object")
            source_id = row.get("id")
            if type(source_id) is not int or source_id < 1:
                raise ValueError(f"{context}: id must be a positive integer")
            if source_id in seen:
                raise ValueError(f"{context}: duplicate id {source_id}")
            seen.add(source_id)
            for key in ("task", "method", "model_type", "scene"):
                require_text(row, key, context)
            history = row.get("history")
            if not isinstance(history, list) or len(history) < 2:
                raise ValueError(f"{context}: history must contain at least two user/bot exchanges")
            for index, exchange in enumerate(history):
                turn_context = f"{context} history[{index}]"
                if not isinstance(exchange, dict):
                    raise ValueError(f"{turn_context}: expected a user/bot object")
                for role in ("user", "bot"):
                    if not isinstance(exchange.get(role), str):
                        raise ValueError(f"{turn_context}: {role!r} must be a string")
            yield row
    if not seen:
        raise ValueError(f"{path}: no dialogue records")


def _turns(row: dict[str, Any], source_id: str, path: Path) -> list[Turn]:
    """Each user turn, each earlier bot reply, ending on the final user turn."""
    turns = []
    for index, exchange in enumerate(row["history"]):
        turn_context = f"{path}: id {source_id} history[{index}]"
        user = require_text(exchange, "user", turn_context)
        turns.append(Turn(role="user", content=user))
        if index < len(row["history"]) - 1:
            bot = require_text(exchange, "bot", turn_context)
            turns.append(Turn(role="assistant", content=bot))
    return turns


def resolve(raw_dir: Path) -> tuple[list[Item], Coverage]:
    """Validate the annotation file and split the dialogues into harmful, benign, held, excluded.

    Missing and unreviewed entries are held. A stale checksum, unknown IDs, an unmapped
    method and invalid reviewed entries fail, all before anything is emitted.
    """
    path = raw_dir / FILENAME
    version = source_version(path)
    annotation_path = raw_dir / ANNOTATIONS_FILENAME
    entries, annotation_version = _annotations.open_file(annotation_path, version, _DOC_HINT)
    rows = list(read_dialogues(path))
    unknown = sorted(entries.keys() - {str(row["id"]) for row in rows})
    if unknown:
        raise ValueError(f"{annotation_path}: IDs not in the English file: {unknown[:10]}")
    # Every method must map, even while its dialogues are held.
    for method in sorted({row["method"] for row in rows}):
        taxonomy.attack_family(SOURCE, method)
        taxonomy.strategy_tag(SOURCE, method)
    items, harmful, benign, held, excluded = [], [], [], [], []
    for row in rows:
        source_id = str(row["id"])
        context = f"{annotation_path}: id {source_id}"
        entry = entries.get(source_id)
        if entry is None or not _annotations.is_reviewed(entry, context):
            held.append(source_id)
            continue
        decision = _annotations.resolve(entry, context, annotation_version, require_intent=True)
        if decision.disposition == "excluded":
            excluded.append(source_id)
            continue
        method = row["method"]
        family = taxonomy.attack_family(SOURCE, method)
        strategy = taxonomy.strategy_tag(SOURCE, method)
        labels = {
            key: value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
            for key, value in row.items() if key != "history"
        }
        item_id = f"{SOURCE}:{source_id}"
        items.append(Item(
            item_id=item_id,
            source=SOURCE,
            source_id=source_id,
            source_version=version,
            intent_id=item_id,
            intent=decision.intent,
            turns=_turns(row, source_id, path),
            is_benign=decision.disposition == "benign",
            attack_family=family.value,
            attack_method=method,
            # model_type is the upstream dialogue generator, not an attack target.
            attack_target_model=None,
            strategy_tags=[strategy.value],
            harm_domain=decision.domain,
            native_labels=labels,
            needs_review=review_flags(attack_family=family, strategy_tags=strategy),
            annotation=decision.annotation,
            license="Apache-2.0",
        ))
        (benign if decision.disposition == "benign" else harmful).append(source_id)
    report = Coverage(tuple(harmful), tuple(benign), tuple(held), tuple(excluded))
    return items, report


def coverage(raw_dir: Path) -> Coverage:
    """Native IDs that are harmful, benign, held and excluded under the current annotations."""
    return resolve(raw_dir)[1]


@register(SOURCE)
def load(raw_dir: Path) -> Iterator[Item]:
    """Yield one final-turn evaluation Item per reviewed, non-excluded dialogue."""
    items, report = resolve(raw_dir)
    (logger.warning if report.held else logger.info)("%s: %s", SOURCE, report)
    yield from items
