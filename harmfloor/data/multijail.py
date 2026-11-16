"""MultiJail (Deng et al., ICLR 2024): the same harmful prompts in English and nine translations.

Each MultiJail id is reviewed once, on its English text; that decision (harmful / benign /
excluded, harm domain) covers every language version. Items are one per (id, language):
the English version is the untranslated reference (family `direct`), translations are the
translation attack (family `obfuscation_based`). All versions of an id share an intent_id, so
the bootstrap resamples them together and languages can be compared on the same requests.
"""

from __future__ import annotations

from pathlib import Path

from harmfloor import taxonomy
from harmfloor.data.annotations import ANNOTATIONS_DIR, gate, load_annotations, sha256_file
from harmfloor.data.registry import Held, LoadResult, register
from harmfloor.schema import Item, Turn
from ._utils import review_flags
from .sources import MULTIJAIL_LANGUAGES, read_multijail

SOURCE = "multijail"
FILENAME = "MultiJail.csv"


@register(SOURCE)
def load(raw_dir: Path, annotations_root: Path = ANNOTATIONS_DIR) -> LoadResult:
    path = raw_dir / FILENAME
    sha = sha256_file(path)
    rows = read_multijail(path)
    notes = load_annotations(SOURCE, sha, annotations_root, valid_ids={r["id"] for r in rows})
    result = LoadResult()
    for row in rows:
        sid = row["id"]
        a = notes.get(sid)
        if (reason := gate(a)) is not None:
            bucket = result.excluded if a and a.reviewed and a.verdict == "excluded" else result.held
            bucket.append(Held(sid, reason))
            continue
        for lang in MULTIJAIL_LANGUAGES:
            family = taxonomy.attack_family(SOURCE, lang)
            result.items.append(Item(
                item_id=f"{SOURCE}:{sid}:{lang}",
                source=SOURCE,
                source_id=sid,
                source_version=f"sha256:{sha}",
                intent_id=f"{SOURCE}:{sid}",
                intent=row["en"],
                turns=[Turn(role="user", content=row[lang])],
                is_benign=a.verdict == "benign",
                attack_family=family.value,
                attack_method=f"MultiJail-{lang}",
                needs_review=review_flags(attack_family=family),
                annotation=notes.provenance(sid),
                harm_domain=a.harm_domain,
                native_labels={"language": lang, "tags": row["tags"], "origin": row["source"]},
                license="MIT",
            ))
    return result.report(SOURCE)
