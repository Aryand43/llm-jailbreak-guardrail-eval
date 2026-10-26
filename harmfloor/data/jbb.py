"""JailbreakBench JBB-Behaviors, harmful split (100 behaviors, single-turn, attack family `direct`).

JBB's ten categories mix harm domains (e.g. a nuclear-weapons request under "Government
decision-making"), so the domain comes from a reviewed annotation per behavior; the category is
kept verbatim in native_labels.
"""

from __future__ import annotations

from pathlib import Path

from harmfloor import taxonomy
from harmfloor.data.annotations import ANNOTATIONS_DIR, gate, load_annotations, sha256_file
from harmfloor.data.registry import Held, LoadResult, register
from harmfloor.schema import Item, Turn
from ._utils import review_flags
from .sources import read_jbb

SOURCE = "jbb_behaviors"
FILENAME = "harmful-behaviors.csv"


@register(SOURCE)
def load(raw_dir: Path, annotations_root: Path = ANNOTATIONS_DIR) -> LoadResult:
    path = raw_dir / FILENAME
    sha = sha256_file(path)
    rows = read_jbb(path)
    notes = load_annotations(SOURCE, sha, annotations_root, valid_ids={r["Index"] for r in rows})
    family = taxonomy.attack_family(SOURCE, "")
    result = LoadResult()
    for row in rows:
        sid = row["Index"]
        a = notes.get(sid)
        if (reason := gate(a)) is not None:
            bucket = result.excluded if a and a.reviewed and a.verdict == "excluded" else result.held
            bucket.append(Held(sid, reason))
            continue
        if a.intent is not None and a.intent != row["Goal"]:
            raise ValueError(f"{sid}: JBB intent must be its source Goal")
        result.items.append(
            Item(
                item_id=f"{SOURCE}:{sid}",
                source=SOURCE,
                source_id=sid,
                source_version=f"sha256:{sha}",
                intent_id=f"{SOURCE}:{sid}",
                intent=row["Goal"],
                turns=[Turn(role="user", content=row["Goal"])],
                is_benign=a.verdict == "benign",
                attack_family=family.value,
                needs_review=review_flags(attack_family=family),
                annotation=notes.provenance(sid),
                harm_domain=a.harm_domain,
                native_labels={k: v for k, v in row.items() if k not in {"Goal", "Target"}},
                license="MIT",
            )
        )
    return result.report(SOURCE)
