# Dataset loaders

Loaders read local files and return `harmfloor.schema.Item` records. They make no network or model calls. Raw data and local annotations belong under the gitignored `data/raw/` directory.

```python
from harmfloor.data import load

items = list(load("jbb_behaviors"))
# SafeDialBench emits only dialogues with reviewed annotations (see below):
# items = list(load("safedialbench"))

# A different raw-data root is also supported:
# items = list(load("jbb_behaviors", raw_root=Path("my-data/raw")))
```

Materialize the iterator before publishing or exporting a dataset so validation errors cannot leave a partial release. Loaders fail on missing files, malformed records, duplicate identifiers, and unmapped labels. Every item records a SHA-256 of its raw source file, its original source ID, and native labels. Initially `intent_id == item_id`; cross-source intent deduplication happens later.

`native_labels` holds upstream fields only, verbatim. Our own metadata has typed fields: `needs_review` lists the fields whose taxonomy mapping is still a `review: true` proposal, and `annotation` records what our review decided (`disposition`, the assigned `harm_domain`, and a `reason`) for sources whose release has no harm domain of its own. A harmful item carries a `harm_domain`; a benign item has `harm_domain=None` and `is_benign=True`.

`needs_review` must be present explicitly, including `[]` when no mappings need review. Older cached Items without that field, or with `*_needs_review` flags inside `native_labels`, are rejected when parsed. Rebuild those caches from the raw files with the current loaders; do not remove the old flags and insert an empty list manually. Reloading preserves the current taxonomy review state. Cached Items are snapshots: regenerate them after any annotation or taxonomy change.

## Reviewed annotations

JBB's categories mix harm domains and SafeDialBench ships no detailed labels, so under the team's labelling rules (2026-10-23) each item's `harm_domain` is reviewed per item in a sidecar file, never mapped from a native category. One file per source, bound to the raw file's checksum: `jbb_behaviors/annotations.json` and `safedialbench/annotations_en.json`. An item is emitted only once its entry is `reviewed: true`; everything else is held.

Each entry is one of three dispositions:

```json
{"disposition": "harmful",  "domain": "cyber", "intent": "<standalone request>", "reviewed": true}
{"disposition": "benign",   "intent": "<standalone request>", "reason": "<why benign>", "reviewed": true}
{"disposition": "excluded", "reason": "<why not scored>", "reviewed": true}
```

- **harmful** needs a `domain` from the 13 in `configs/taxonomy.yaml` (`harm_domains`). It is scored normally.
- **benign** is a protective, educational or otherwise safe request kept for the false-positive-rate test (`is_benign=True`, no domain). A refusal of it is a false positive, so mark benign only when it is clearly safe; hold anything unclear.
- **excluded** is dropped from the study (unusable context, or a request whose only harm is rudeness, satire or blasphemy). It needs a `reason` and is not emitted.

`domain` belongs only to harmful entries; `intent` is required for harmful and benign SafeDialBench entries (JBB uses the CSV `Goal`) and forbidden on excluded. `reviewed` must be the JSON boolean, not a string. `intent` is a neutral, standalone description of the final request; do not invent a harmful aim, and a safety-related subject does not by itself make a request harmful (rule 1: label the harmful content a fully compliant answer would have to contain). When several domains apply, pick the primary one by the fixed order in rule 2.

The loader sorts every dialogue into four buckets, all checked before anything is yielded:

- **harmful / benign:** emitted (benign with `is_benign=True`).
- **held** (not emitted, not an error): no entry, or `reviewed: false`. Drafts are not validated until reviewed, so a messy draft is simply held.
- **excluded:** a reviewed `excluded` entry.
- **Error:** a stale checksum, an id not in the raw file, a duplicate key, a non-boolean `reviewed`, an unmapped method (SafeDialBench), an unknown annotation key, or a reviewed entry with an unknown/absent domain, a blank intent, a misplaced field or a blank turn.

Each load logs the four counts, as a warning while anything is held. For the id lists, call the loader's `coverage(Path("data/raw/<source>"))`, which returns `harmful`, `benign`, `held` and `excluded`. Emitted items carry `annotation.version` (the sidecar's SHA-256), `annotation.disposition` and `annotation.domain`, kept separate from the upstream `native_labels`. An AI-assisted draft is not human review: leave its entries `reviewed: false` until the team's procedure is complete.

## Source snapshots

These official snapshots were acquired on 2026-10-23. Dataset files are not committed.

| Source | Local file under `data/raw/` | Revision | SHA-256 |
|---|---|---|---|
| [JBB harmful behaviors](https://huggingface.co/datasets/JailbreakBench/JBB-Behaviors) | `jbb_behaviors/harmful-behaviors.csv` | `886acc352a31533ffbcf4ef22c744658688086fc` | `4a8ec6832056b631eb092dccc60d37a61c3d441268268888b3d006288afeffa1` |
| [SafeDialBench English](https://huggingface.co/datasets/HongyeCao/SafeDialBench) | `safedialbench/datasets_en.jsonl` | `0d27436754b80c28d40c3748ede8e498405a63a8` | `a5429b6477ab7d3f6e47da55e0a9c889bbbba7575dd2ba7e1672379a412bc988` |

To acquire these same files in PowerShell:

```powershell
New-Item -ItemType Directory -Force data/raw/jbb_behaviors, data/raw/safedialbench
Invoke-WebRequest -Uri 'https://huggingface.co/datasets/JailbreakBench/JBB-Behaviors/resolve/886acc352a31533ffbcf4ef22c744658688086fc/data/harmful-behaviors.csv' -OutFile 'data/raw/jbb_behaviors/harmful-behaviors.csv'
Invoke-WebRequest -Uri 'https://huggingface.co/datasets/HongyeCao/SafeDialBench/resolve/0d27436754b80c28d40c3748ede8e498405a63a8/datasets_en.jsonl' -OutFile 'data/raw/safedialbench/datasets_en.jsonl'
Get-FileHash -Algorithm SHA256 data/raw/jbb_behaviors/harmful-behaviors.csv, data/raw/safedialbench/datasets_en.jsonl
```

Compare the hashes with the table. Preserve the upstream dataset cards and applicable licence notices when redistributing; see `configs/benchmarks.yaml`. The development downloads also have local `provenance.json`, `UPSTREAM_README.md`, and `LICENSE` files.

## JBB harmful behaviors

The loader turns each reviewed CSV behavior into a direct-request item. The upstream `Behavior` identifier becomes `source_id`; `Goal` is the intent and the sole user turn (JBB requests are already standalone, so no per-item intent is reviewed). It preserves `Index`, `Behavior`, `Category`, and `Source` in `native_labels`. The stored `Target` response is not a prompt or a new model response and is not imported. `attack_family` is `direct`.

This loader covers the **behavior split**, not submitted PAIR/GCG/etc. attack artifacts or the benign split. Those formats require separate integration and transfer-target provenance. The broader registry entry continues to describe those available artifacts.

The ten JBB categories mix harm domains (a nuclear-weapons request sits under `Government decision-making`), so the category is **not** mapped to a domain. Instead each behavior's `harm_domain` is reviewed per item in `jbb_behaviors/annotations.json` (see **Reviewed annotations**). JBB is a harmful-behaviors benchmark, so its entries are `harmful`; `benign` is not used (JBB has its own benign split) and `excluded` only for a genuinely unusable row. `read_behaviors` checks the raw CSV structure without annotations. Registry status is `sourced` until the drafts are reviewed.

## SafeDialBench English

The official English file contains 2,037 dialogues, with fields `task`, `method`, `model_type`, `scene`, `id`, and `history`. Histories contain `user`/`bot` pairs. The upstream method spelling `Scence Construct` is preserved and explicitly mapped in the taxonomy.

The loader emits one item per included dialogue. It preserves each earlier user/bot exchange and ends at the final user turn, omitting the stored final bot reply. This is a **fixed-context final-turn evaluation**, not a fresh interactive rollout of the whole conversation. `model_type` is preserved as a native generator label; it is not treated as `attack_target_model`. No upstream judgment scores are used.

The release has only six broad safety tasks (e.g. `Privacy`) and no standalone intent; a scene label such as `Law and Morality` cannot substitute for either. So the `harm_domain`, `intent` and disposition come from the reviewed `safedialbench/annotations_en.json` (see **Reviewed annotations**), not from the native fields. Protective or educational dialogues (recognising abuse, historical analysis) are kept as `benign` for the false-positive test; a request whose only issue is rudeness, satire or blasphemy is `excluded`; genuinely unclear dialogues stay held.

Dialogue **645** in this snapshot has a whitespace-only user turn at history index 2. If reviewed as harmful or benign it errors on the blank turn; a reviewer excludes it explicitly (`{"disposition": "excluded", "reason": "...", "reviewed": true}`). The loader never edits or drops the source turn itself. `read_dialogues` checks the raw structure without annotations, and `load` checks every dialogue's method mapping even while all entries are held.

## Entering the evaluation set

Build the evaluation set from `harmfloor.data.evaluation_pool(items)`. It raises if any item carries an unreviewed **primary-axis** mapping — `attack_family` or `harm_domain` — in `needs_review`, naming each source and field with a count. `strategy_tags` is a secondary axis and does not block (team decision, rule 5), so a provisional strategy tag is reported but still admitted. Flagged items are refused rather than dropped, so the pool cannot be skewed silently. To clear a blocking flag, validate the mapping on ~20 items (all available when fewer exist), record the decision, clear its `review: true` in `configs/taxonomy.yaml`, and reload in a fresh process (or call `harmfloor.taxonomy.load.cache_clear()`). Approving a dialogue's annotation does not approve a taxonomy mapping; they are separate steps.

Keep first-pass review notes and annotation drafts under the ignored `data/cache/` directory; `jbb_domain_review.csv` lists the proposed JBB domains for review, and the pilot's `START_HERE.md` explains the independent annotation workflow. A safety-related subject does not by itself establish a harmful requested action: preserve the actual request, and hold unclear cases until the team's labelling rules are applied.
