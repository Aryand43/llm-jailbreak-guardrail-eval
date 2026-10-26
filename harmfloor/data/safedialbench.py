"""SafeDialBench, English release (2,037 multi-turn dialogues, attack family `multi_turn`).

The release has six broad themes but no per-dialogue harm label or standalone intent, and some
final requests are protective or educational. Verdict, domain and intent therefore come from a
reviewed annotation per dialogue.

Following METHODOLOGY §7, `turns` holds the user turns only; the runner regenerates the assistant
turns with each target. The source's ChatGPT replies before the final user turn go in
`reference_turns` for annotation and audit. A replay ablation would require a separate protocol
decision. The source's final reply is dropped entirely.
"""

from __future__ import annotations

import json
from pathlib import Path

from harmfloor import taxonomy
from harmfloor.data.annotations import ANNOTATIONS_DIR, gate, load_annotations, sha256_file
from harmfloor.data.registry import Held, LoadResult, register
from harmfloor.schema import Item, Turn
from .sources import read_safedial
from ._utils import review_flags

SOURCE = "safedialbench"
FILENAME = "datasets_en.jsonl"
METHOD_ALIASES = {"Scence Construct": "Scene Construct"}  # typo in the release; kept verbatim in native_labels


@register(SOURCE)
def load(raw_dir: Path, annotations_root: Path = ANNOTATIONS_DIR) -> LoadResult:
    path = raw_dir / FILENAME
    sha = sha256_file(path)
    rows = read_safedial(path)
    notes = load_annotations(SOURCE, sha, annotations_root, valid_ids={str(r["id"]) for r in rows})
    for native in {r["method"] for r in rows}:
        method = METHOD_ALIASES.get(native, native)
        taxonomy.attack_family(SOURCE, method)
        taxonomy.strategy_tag(SOURCE, method)
    result = LoadResult()
    for row in rows:
        sid = str(row["id"])
        history = row["history"]
        a = notes.get(sid)
        if (reason := gate(a)) is not None:
            bucket = result.excluded if a and a.reviewed and a.verdict == "excluded" else result.held
            bucket.append(Held(sid, reason))
            continue
        if any(not t["user"].strip() for t in history) or any(not t["bot"].strip() for t in history[:-1]):
            raise ValueError(f"{sid}: blank source turn; hold for explicit review/exclusion")
        method = METHOD_ALIASES.get(row["method"], row["method"])
        tag = taxonomy.strategy_tag(SOURCE, method)
        family = taxonomy.attack_family(SOURCE, method)
        reference = []
        for t in history[:-1]:
            reference += [Turn(role="user", content=t["user"]), Turn(role="assistant", content=t["bot"])]
        reference.append(Turn(role="user", content=history[-1]["user"]))
        result.items.append(
            Item(
                item_id=f"{SOURCE}:{sid}",
                source=SOURCE,
                source_id=sid,
                source_version=f"sha256:{sha}",
                intent_id=f"{SOURCE}:{sid}",
                intent=a.intent,
                turns=[Turn(role="user", content=t["user"]) for t in history],
                reference_turns=reference,
                is_benign=a.verdict == "benign",
                attack_family=family.value,
                needs_review=review_flags(attack_family=family, strategy_tags=tag),
                annotation=notes.provenance(sid),
                attack_method=method,
                strategy_tags=[] if tag.needs_review else [tag.value],
                provisional_tags=[tag.value] if tag.needs_review else [],
                harm_domain=a.harm_domain,
                native_labels={k: v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)
                               for k, v in row.items() if k != "history"},
                license="Apache-2.0",
            )
        )
    return result.report(SOURCE)
