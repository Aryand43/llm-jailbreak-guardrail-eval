# Integration handoff — 2026-10-26

**Update 2026-10-28:** All 100 selected annotation-pilot decisions are recorded: 76 harmful, 23 separate over-refusal and 1 excluded. The [accepted case-review outcome](PILOT_CASE_REVIEW_2026-10-28.md#accepted-outcome--2026-10-28) supersedes the historical data-state table below. Independent first-pass agreement remains unmeasured, five rubric boundary groups remain documented, and paid generation remains funding-dependent. No PR or paid run has been performed.

**Update 2026-10-27:** Aryan approved D7–D12. The 26 October baseline below is historical; its pending-decision list and model availability have been superseded by [the pilot review report](PILOT_REVIEW_2026-10-27.md) and METHODOLOGY §10. The paid pilot remains funding-dependent; PR into main follows the annotation pilot.

Working branch: **`aniket`**. Implementation owner: **Aniket**. Supervisor and protocol approval owner: **Aryan**.

This integration is prepared on `aniket` for supervisor review; it is not a merge into `main` or a release. Relevant loader, worksheet, utility and OpenRouter code from Aryan's branch has been incorporated and hardened while retaining Aniket's validation safeguards. `main` was not changed. The handoff document and implementation travel together in the integration commit; local review materials remain separate as described below.

## Branch baseline

The fetched branch heads when integration began were:

| Branch | Commit |
|---|---|
| `main` | `56c4ce1ab526b66d08abfba19edc484b83a22f40` |
| `aniket` | `a27acfa7e700c16af62d43224a9e8adde236532a` |
| `aryan/loaders-openrouter` | `ec9bea988de028f72a21783da8baa28cbb54b4b0` |

The common ancestor is `4449b87`. These are recorded baselines, not a claim that remote heads cannot subsequently change.

## Implemented

- JBB and SafeDialBench use strict reviewed JSONL decisions with raw-file checksums and named reviewer/drafter provenance on emitted Items. Missing decisions are held and reported. Unknown/duplicate IDs, inconsistent labels and stale hashes fail explicitly.
- SafeDialBench separates user-only target inputs from source reference context, and drops the final source bot reply entirely. Taxonomy proposals remain flagged. The evaluation gate blocks all unresolved mappings by default.
- Worksheet exports bind to source hashes immediately. Imports reject changed context, unknown/duplicate/deleted rows and invalid completed decisions. Replacement is atomic; clearing the last decision produces an empty reviewed snapshot instead of retaining stale approvals. Previous snapshots are retained locally.
- Blind worksheets omit drafts. Agreement uses a specified frozen first-review snapshot and reports coverage, denominators, raw agreement and kappa before reconciliation.
- Pinned OR-Bench and XSTest acquisition/loaders work. The OpenRouter client records tokens, reported cost, provider, request ID and attempts, without prompt/completion text or API keys. Missing cost is unknown, not zero. Tests use mocked completions; no paid generation was run.
- Existing local drafts were migrated without approvals or changes to originals. Migration reports retain exact hashes and an ID ledger. JBB uses numeric Index IDs; its old Behavior IDs remain in native labels and the migration ledger.

## Data state

| Source | Raw count | Reviewed emitted | Held | Local draft preparation |
|---|---:|---:|---:|---|
| JBB harmful behaviors | 100 | 0 | 100 | 100 drafts, 53 CHECK notes |
| SafeDialBench English | 2,037 | 0 | 2,037 | 20 pilot drafts: 6 benign, 4 harmful, 1 exclusion, 9 open |
| SoK OR-Bench sample | 1,000 | 1,000 benign from source labels | 0 | No per-item annotation gate |
| XSTest | 450 | 250 source-labelled safe prompts | 0 | 200 unsafe contrast prompts not included |

All migrated draft entries remain `reviewed: false`. No final reviewed annotation file has been created. Original sidecars remain unchanged. Drafting provenance gaps are explicit; no model/prompt version or reviewer identity was invented.

Full first-review worksheets are prepared under `data/annotations/worksheets/`. The independent SafeDialBench worksheet `safedialbench.pilot.blind.csv` contains the existing 20 pilot IDs and no draft columns. Keep each CSV beside its `.manifest.json`.

**These drafts and worksheets are ignored by Git. A branch push will not transfer them to Aryan.** The code and docs will transfer after commit/push; arrange sharing of local review material separately. The preserved old pilot pack is historical context, not the current editable annotation format.

## OpenRouter catalogue check

Public catalogue checked on **2026-10-26**. Five configured slugs were listed, advertising `temperature`, `top_p` and `seed`:

- `meta-llama/llama-3.2-3b-instruct`
- `meta-llama/llama-3.1-8b-instruct`
- `meta-llama/llama-3.3-70b-instruct`
- `google/gemma-3-27b-it`
- `openai/gpt-oss-120b`

Four configured slugs were absent:

- `nvidia/llama-3.1-nemotron-70b-instruct`
- `nvidia/llama-3.1-nemotron-ultra-253b-v1`
- `qwen/qwen3-8b`
- `deepseek/deepseek-r1-distill-qwen-7b`

Availability is time-sensitive. Catalogue parameter support does not verify a chosen provider's behavior or deterministic outputs. Aryan must approve replacements/omissions, provider pins and a pilot budget; the configured grid has not been silently substituted.

## Ordered next steps

| Order | Owner | Work | Completion evidence |
|---|---|---|---|
| 1 | Aryan | Resolve METHODOLOGY D7–D10: inclusion/exclusion rubric, domain ties, benign FPR eligibility, review coverage, mapping policy and source-versus-target context | Dated protocol decisions; no AI draft counted as approval |
| 2 | Aniket + independent reviewer | Review the agreed JBB and SafeDialBench pilot IDs using the prepared worksheets | Named final decisions; first-review snapshot preserved; unclear items held |
| 3 | Aniket, adjudicated by Aryan | Measure independent agreement before reconciliation; resolve disagreements and reassess problematic rules | Counts, denominators, kappa and adjudication notes |
| 4 | Aniket, approved by Aryan | Validate seven SafeDialBench family/strategy mappings and clear only approved flags | Mapping evidence and decision log; reload produces expected gate behavior |
| 5 | Aniket | Import reviewed decisions, inspect coverage and build the permitted pilot pool | Source-bound annotations, explicit held/excluded counts and passing evaluation gate |
| 6 | Aryan | Resolve unavailable models, provider pins and pilot spending limit (D11) | Approved grid and budget |
| 7 | Aniket | Run a small approved live API pilot; verify actual provider, decoding, tokens and cost; implement target-history generation and intent checks before multi-turn experiments | Auditable run logs, usage estimate and validated multi-turn behavior |
| 8 | Aniket + Aryan | Review the integration on `aniket`, then review a PR into `main` when ready | Reviewed commits/PR; deliberate handoff of ignored local materials |
| 9 | Research team | Extend reviewed coverage, deduplicate intents, freeze utility calibration/sampling and judges; resolve remaining dataset access/terms including MultiBreak | Reproducible frozen evaluation manifests and budget approval before full runs |

XSTest has only 250 safe prompts while `benign_per_source` currently requests 300: the eventual sampler must explicitly handle undersized sources under the approved sampling policy. No experiment runner or final sampling manifest is claimed complete here.

## Validation

Final validation on 2026-10-26: **123 tests passed**, taxonomy validation returned no errors, and `git diff --check` was clean. Tests cover stale worksheets, withdrawn approvals, invalid rows, failed atomic replacement, duplicate IDs, provenance, review gates, independent-agreement denominators and malformed API responses.

Run `uv run pytest` and `uv run python scripts/check_models.py` from the repository root. Real-file validation confirms JBB/SafeDialBench are fully held without human decisions, OR-Bench emits 1,000 benign items, and XSTest emits 250. Original draft hashes were rechecked after migration. Local evidence is in `data/cache/integration_validation.json`; it contains counts and hashes, not human approval.

See [DATA_LOADERS.md](DATA_LOADERS.md) for the API/migration changes and [ANNOTATION.md](ANNOTATION.md) for exact worksheet commands.
