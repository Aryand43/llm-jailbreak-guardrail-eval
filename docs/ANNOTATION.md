# Annotation workflow

Aniket owns implementation and review preparation. **Aryan is the supervisor and protocol approval owner.** Labelling rules, independent-review coverage and acceptance criteria remain pending in METHODOLOGY §10. Existing AI drafts are proposals, not reviewed labels.

## Files

| Path under `data/annotations/` | Purpose | Git treatment |
|---|---|---|
| `drafts/<source>.jsonl` | Incomplete, unreviewed proposals; never read by loaders | Ignored |
| `drafts/<source>.migration.json` | Original hashes, migration counts and ID ledger | Ignored |
| `worksheets/<source>.csv` | Source context, draft columns and editable final decisions | Ignored |
| `worksheets/<source>.manifest.json` | Raw checksum, selected IDs, context hashes and drafter snapshot | Ignored; keep beside CSV |
| `<source>.jsonl` | Strict reviewed decisions used by loaders | Eligible for deliberate review/commit |
| `history/<source>/<hash>.jsonl` | Previous reviewed snapshots saved on import | Ignored |

Raw datasets and old sidecars are preserved under ignored `data/raw/`. Local drafts and worksheets will not reach Aryan through a branch push; arrange a deliberate handoff separately if he needs these local files. Never include API keys.

## Review sequence

1. Aryan confirms the pending rules, which items to review and the independent-review sample. Do not apply the old fixed domain priority order automatically.
2. Open the existing `worksheets/jbb_behaviors.csv` or `worksheets/safedialbench.csv`. The latter contains all 2,037 source rows but only the existing 20 pilot drafts are prefilled. Filter to the selected IDs; leave all other final verdicts blank. Do not delete rows.
3. Read the source context and fill the final `verdict`, `harm_domain`, `intent`, `reason` and `reviewer` columns. `draft_*` columns are suggestions. A blank final verdict means held. The reviewer must identify themselves; AI output is not human approval.
4. Keep the manifest beside the worksheet. Do not edit IDs, context, headers or the manifest. An export is bound to the raw file as it existed at export time. Imports fail if the source or reference context changes.
5. Once the agreed first-review procedure is complete, import the full worksheet using the command below. Import replaces the complete reviewed snapshot. **Blanking a previously completed verdict withdraws approval**, even if every row becomes blank. A malformed completed row aborts the entire import and preserves the prior file.
6. Freeze a copy of the first-reviewer JSONL before reconciliation. Have the independent reviewer complete a blind worksheet without access to drafts or first decisions. The prepared `safedialbench.pilot.blind.csv` covers the existing 20 pilot IDs; it is not a random population sample.
7. Compute agreement against the frozen first-review snapshot, then reconcile disagreements under Aryan's procedure. Keep original reviews and agreement results. Re-import the reconciled full first worksheet and reload the data.

```bash
# These full worksheets already exist locally. Export refuses to overwrite them.
uv run python scripts/review.py export jbb_behaviors
uv run python scripts/review.py export safedialbench

# After review; each import replaces that source's complete reviewed snapshot.
uv run python scripts/review.py import jbb_behaviors
uv run python scripts/review.py import safedialbench

# Example independent sample size, subject to Aryan's approval:
uv run python scripts/review.py blind jbb_behaviors 50 --seed 0

# Use a frozen pre-reconciliation JSONL, not the live reconciled file.
uv run python scripts/review.py kappa safedialbench --worksheet data/annotations/worksheets/safedialbench.pilot.blind.csv --first-labels path/to/frozen-first-review.jsonl
```

Use `--worksheet path/to/new-name.csv` to export another round without overwriting work. Blind or partial worksheets cannot replace the full reviewed snapshot. The sampler balances JBB native Category strata or SafeDialBench native method/task strata; it records seed and selection. Sample size is a protocol choice, not an automatic acceptance rule.

Agreement output reports the sampled count, completed second reviews, paired denominator, label counts, raw agreement and Cohen's kappa. Domain agreement uses only pairs both reviewers called harmful. Undefined kappa is `null`, not perfect agreement. Low sample coverage and reconciliation must be reported explicitly.

## Label content and pending decisions

- Proposed criterion: classify what a fully compliant answer to the request, in context, would contain. Framing alone does not establish safety or harm. Aryan must confirm operational inclusion and exclusion rules.
- Harmful decisions require one of the 13 domains in `configs/taxonomy.yaml`. Select the primary requested harm under the approved rubric. Multi-domain ties remain an explicit supervisor decision; the old fixed priority order is not an approved default.
- Benign decisions require no domain and a reason. Their eligibility for the study's FPR pool is a separate pending protocol decision.
- Exclusions require a reason, no domain and no intent. Hold unresolved cases rather than inventing exclusions to satisfy coverage.
- SafeDialBench included decisions require a neutral standalone intent. Reference context includes earlier source assistant replies, never the final reply. Target-generated history may differ; Aryan must resolve this evaluation/annotation consistency issue.
- JBB uses its exact source Goal. Leave the final intent blank or copy Goal unchanged.
- Native labels remain upstream data. Our decisions and review provenance use typed fields.
- Preserve known drafting provenance and explicitly record gaps. Migration does not invent a model version, prompt version, reviewer or approval.

Item review and taxonomy approval are separate. Default evaluation still blocks unresolved family, domain or strategy flags. See [DATA_LOADERS.md](DATA_LOADERS.md).
