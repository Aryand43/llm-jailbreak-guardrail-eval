"""SafeDialBench, English release (2,037 multi-turn dialogues, attack family `multi_turn`).

The release has six broad themes but no per-dialogue harm label or standalone intent, and some
final requests are protective or educational. Verdict, domain and intent therefore come from a
reviewed annotation per dialogue.

Following METHODOLOGY §7, `turns` holds the user turns only; the runner regenerates the assistant
turns with each target. The source's ChatGPT replies before the final user turn go in
`reference_turns` for the replay ablation. The source's final reply is dropped entirely.
"""

from __future__ import annotations

import json
from pathlib import Path

from harmfloor import taxonomy
from harmfloor.data.annotations import ANNOTATIONS_DIR, gate, load_annotations, sha256_file
from harmfloor.data.registry import Held, LoadResult, register
from harmfloor.schema import Item, Turn

SOURCE = "safedialbench"
FILENAME = "datasets_en.jsonl"
METHOD_ALIASES = {"Scence Construct": "Scene Construct"}  # typo in the release; kept verbatim in native_labels


@register(SOURCE)
def load(raw_dir: Path, annotations_root: Path = ANNOTATIONS_DIR) -> LoadResult:
    path = raw_dir / FILENAME
    sha = sha256_file(path)
    notes = load_annotations(SOURCE, sha, annotations_root)
    result = LoadResult()
    with path.open(encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            sid = str(row["id"])
            history = row["history"]
            if any(not t["user"].strip() for t in history):
                result.held.append(Held(sid, "blank user turn in source"))
                continue
            a = notes.get(sid)
            if (reason := gate(a)) is not None:
                result.held.append(Held(sid, reason))
                continue
            if not a.intent:
                result.held.append(Held(sid, "reviewed annotation has no intent"))
                continue
            method = METHOD_ALIASES.get(row["method"], row["method"])
            tag = taxonomy.strategy_tag(SOURCE, method)
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
                    attack_family=taxonomy.attack_family(SOURCE, method).value,
                    attack_method=method,
                    strategy_tags=[] if tag.needs_review else [tag.value],
                    provisional_tags=[tag.value] if tag.needs_review else [],
                    harm_domain=a.harm_domain,
                    native_labels={k: str(row[k]) for k in ("task", "method", "scene", "model_type")},
                    license="Apache-2.0",
                )
            )
    return result
