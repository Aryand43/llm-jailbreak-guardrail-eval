"""JailbreakBench JBB-Behaviors, harmful split (100 behaviors, single-turn, attack family `direct`).

JBB's ten categories mix harm domains (e.g. a nuclear-weapons request under "Government
decision-making"), so the domain comes from a reviewed annotation per behavior; the category is
kept verbatim in native_labels.
"""

from __future__ import annotations

import csv
from pathlib import Path

from harmfloor import taxonomy
from harmfloor.data.annotations import ANNOTATIONS_DIR, gate, load_annotations, sha256_file
from harmfloor.data.registry import Held, LoadResult, register
from harmfloor.schema import Item, Turn

SOURCE = "jbb_behaviors"
FILENAME = "harmful-behaviors.csv"


@register(SOURCE)
def load(raw_dir: Path, annotations_root: Path = ANNOTATIONS_DIR) -> LoadResult:
    path = raw_dir / FILENAME
    sha = sha256_file(path)
    notes = load_annotations(SOURCE, sha, annotations_root)
    family = taxonomy.attack_family(SOURCE, "").value
    result = LoadResult()
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            sid = row["Index"]
            a = notes.get(sid)
            if (reason := gate(a)) is not None:
                result.held.append(Held(sid, reason))
                continue
            result.items.append(
                Item(
                    item_id=f"{SOURCE}:{sid}",
                    source=SOURCE,
                    source_id=sid,
                    source_version=f"sha256:{sha}",
                    intent_id=f"{SOURCE}:{sid}",
                    intent=a.intent or row["Goal"],
                    turns=[Turn(role="user", content=row["Goal"])],
                    is_benign=a.verdict == "benign",
                    attack_family=family,
                    harm_domain=a.harm_domain,
                    native_labels={"category": row["Category"], "behavior": row["Behavior"], "origin": row["Source"]},
                    license="MIT",
                )
            )
    return result
