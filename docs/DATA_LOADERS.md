# Dataset loaders

Implementation lives on `aniket`; Aryan is the supervisor and protocol approval owner. D7–D12 were approved on 2026-10-27. See [ANNOTATION.md](ANNOTATION.md) for review instructions and [PILOT_REVIEW_2026-10-27.md](PILOT_REVIEW_2026-10-27.md) for current pilot status. Approval of the rubric is separate from human approval of individual labels.

## Acquire and load

```bash
uv sync --locked
uv run python scripts/fetch_data.py
uv run pytest
```

The fetch script pins revisions and SHA-256 checksums for JBB, SafeDialBench English, SoK's OR-Bench sample and XSTest. Raw files remain under ignored `data/raw/<source>/`. See `configs/benchmarks.yaml` for source versions and terms; retain applicable attribution and licence notices when sharing data.

```python
from harmfloor.data import load, evaluation_pool

result = load("jbb_behaviors")  # returns LoadResult, not an iterator
print(result.coverage)         # harmful / benign / held / excluded counts
print(result.held)             # source IDs and reasons
print(result.excluded)         # reviewed exclusions with reasons
items = evaluation_pool(result.items)
```

`load(source, raw_root=Path(...))` supports a different raw-data root. Reviewed annotations still come from `data/annotations/`; lower-level loader tests inject a separate annotation root. All rows are validated before a result is returned. A missing raw file is an error. Missing annotation files or entries hold items; they do not prevent the reviewed subset from loading. JBB and SafeDialBench log coverage, with a warning while anything is held.

## Reviewed annotations and provenance

Loaders read only `data/annotations/jbb_behaviors.jsonl` and `data/annotations/safedialbench.jsonl`. Each JSONL row contains `source_id`, `source_sha256`, `verdict`, `harm_domain`, `intent`, `reason`, `drafted_by`, `reviewed` and `reviewer`. Use the worksheet importer to create these files.

- `harmful`: one valid harm domain; SafeDialBench also requires a standalone intent.
- `benign`: no domain and a reason; SafeDialBench also requires an intent.
- `excluded`: no domain or intent, with an exclusion reason; never emitted.
- Missing or `reviewed: false` entries are held. `reviewed` must be a JSON boolean. Reviewed entries require a named reviewer.

Final annotation files are validated strictly, including any unreviewed rows. Incomplete drafts belong in `data/annotations/drafts/`, which loaders never read. Unknown or duplicate IDs, stale source hashes, unknown fields, contradictory decisions and invalid reviewed content fail instead of quietly dropping data.

Each emitted item records the source checksum and ID, typed review flags, and annotation provenance: annotation-file checksum, decision, domain, reason, raw checksum, drafter and reviewer. `native_labels` contains upstream fields only. Benign items must have `harm_domain=None`; harmful items must have a domain. Duplicate item IDs are rejected at the evaluation gate.

Rebuild cached Items after source, annotation or taxonomy changes. Old caches without `needs_review`, with review flags in native labels, or without required JBB/SafeDialBench annotation provenance are rejected. Do not manufacture empty flags to make old caches pass.

## Source behavior

| Source | Pinned file | Loader behavior |
|---|---|---|
| JBB | `jbb_behaviors/harmful-behaviors.csv` | 100 raw behaviors; per-item annotation gate |
| SafeDialBench EN | `safedialbench/datasets_en.jsonl` | 2,037 raw dialogues; per-item annotation gate |
| OR-Bench | `or_bench/OR-Bench.json` | 1,000 benign prompts from the pinned SoK sample |
| XSTest | `xstest/xstest_prompts.csv` | 250 safe prompts; 200 unsafe contrast prompts not included |

JBB uses the CSV's numeric `Index` as `source_id`, and `Goal` as intent and user turn. `Index`, `Behavior`, `Category` and `Source` remain verbatim native labels. `Target` is never imported. This loader covers harmful behaviors, not the separate benign split or attack artifacts. Domain choices are per item; native categories do not automatically determine them.

SafeDialBench retains native `task`, `method`, `model_type`, `scene` and `id`. The native spelling `Scence Construct` remains in native labels and has an explicit taxonomy alias. Every raw dialogue's method mapping is checked, even while held. `model_type` is not treated as the attacked target model.

SafeDialBench `turns` contains **user turns only**. In accordance with METHODOLOGY §7, the future runner must generate intervening assistant turns from the target and sample the final response. `reference_turns` contains the source's earlier assistant responses for annotation and audit; it must not be passed as target-generated history. Neither field includes the stored final bot response. This loader does not implement the experiment runner. Under D10, label on source context; the runner must flag and exclude final questions that stop making sense with target replies and report the exclusion rate over attempted dialogues.

Dialogue 645 contains a blank user turn. It may remain held or be explicitly excluded by a reviewer; including it raises an error. The loader never silently edits the source dialogue. Blank earlier assistant turns also prevent inclusion.

## Evaluation gate

`evaluation_pool(items)` rejects open `attack_family`, `harm_domain` **and** `strategy_tags` flags by default. It also treats populated `provisional_tags` as an unresolved strategy mapping. Proposed strategies stay separate from approved `strategy_tags`.

`allow_provisional_strategies=True` admits unresolved secondary tags, but never unresolved family/domain mappings. D9 authorizes this for family-level analysis only. All seven SafeDialBench families and Purpose Reverse -> logical_exploit are approved; the six other strategy mappings remain flagged. No strategy-level claims are authorized yet. An item-level annotation does not approve a taxonomy mapping.

`family_evaluation_sets(items, benign_per_source=300, seed=0)` applies the approved family-level exception and returns `harmful`, `fpr_calibration`, `over_refusal` and `sampling_counts`. Benign SafeDialBench items go exclusively into `over_refusal`. Other benign sources are sampled without replacement up to `min(requested, available)`, recording all three counts; XSTest is capped at 250. Source ordering and input ordering do not change the selected set for a fixed seed. Use this helper when assembling family-level evaluations instead of combining all benign items into calibration.

Review mappings on the methodology's sample, record the decision, clear only approved `review: true` entries, then reload in a fresh process (or clear `taxonomy.load`'s cache). Following user acceptance through 2026-10-28, JBB emits the selected 50 harmful pilot items and holds the other 50. SafeDialBench emits 23 harmful and 14 benign Items, excludes 645 and holds 1,999 dialogues. Benign SafeDialBench is routed to the separate over-refusal set. See the pilot report for acceptance and verification provenance; unresolved drafts do not emit.

## Migration from the old format

Old `data/raw/jbb_behaviors/annotations.json` and `data/raw/safedialbench/annotations_en.json` are preserved as legacy drafts. They are no longer loader inputs. The migration script checks source hashes, translates JBB Behavior IDs to Index IDs, preserves each original entry and records an ID ledger. It refuses reviewed inputs and never approves labels.

```bash
uv run python scripts/migrate_annotations.py --help
```

The local migration is already complete: 100 JBB drafts (including 53 CHECK notes) and the existing 20-dialogue SafeDialBench pilot. The other SafeDialBench entries remain in the original file. Migration reports record hashes, counts and provenance gaps. Existing draft outputs cannot be overwritten by rerunning migration. See the review workflow before changing any label.
