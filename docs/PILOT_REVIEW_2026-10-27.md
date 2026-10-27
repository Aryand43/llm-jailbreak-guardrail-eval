# Pilot review — 2026-10-27

Supervisor: Aryan. Branch: `aniket`. D7–D12 are recorded as approved in [METHODOLOGY §10](METHODOLOGY.md#10-open-decisions-and-deviation-log). No PR into main before the pilot. Paid generation remains off pending funding confirmation.

## Current state — 2026-10-28

**Latest acceptance:** The user subsequently confirmed **“accepted everything!”** for the 12 full-context proposals and the proposed intent correction for 851. The selected pilot now has **100 recorded decisions: 76 harmful, 23 separate over-refusal, 1 excluded, zero selected cases held**. See the [accepted outcome](PILOT_CASE_REVIEW_2026-10-28.md#accepted-outcome--2026-10-28) and [acceptance audit](../data/annotations/approvals/safedialbench.remaining12-2026-10-28.json). Current annotations are in the live JSONL; older CSVs are historical and must not overwrite it. The remaining paragraphs describe earlier stages, including the superseded 88-decision state.

Follow-up: the [2026-10-28 case review](PILOT_CASE_REVIEW_2026-10-28.md) audits all 100 selected cases and supplies full-context AI recommendations for the remaining 12 (3 harmful, 9 benign), plus an explicit boundary-review queue. Those new proposals are unreviewed; the accepted counts below remain unchanged. The [case audit](../data/annotations/reviews/pilot-case-review-2026-10-28.json) preserves per-case scope and source hashes.

The user replied **"accepted!"** to the 9 harmful and 9 benign proposals for the additional SafeDialBench cases. Those **18 decisions are adopted**, preserving their AI screening provenance and all 20 earlier accepted decisions. No independent human first-pass review is asserted. The 12 proposals without a verdict remain held: **297, 405, 562, 711, 850, 983, 1116, 1252, 1511, 1578, 1686, 1701**.

The selected pilot now has **88 accepted decisions: 73 harmful, 14 benign in the separate over-refusal set, and 1 excluded**. SafeDialBench contributes 23 harmful, 14 benign and 1 exclusion; 1,999 raw dialogues remain held, including the 12 unresolved pilot cases. The 50 accepted JBB decisions are unchanged. Main FPR calibration remains 300 OR-Bench + 250 XSTest items, with no SafeDialBench benign items included.

The previous accepted annotation snapshot is archived under `data/annotations/history/safedialbench/`. The new audit is `data/annotations/approvals/safedialbench.additional18-2026-10-28.json`. It records the exact confirmation, original screening limitations, source/draft/snapshot hashes and adopted IDs. The AI-only agreement diagnostic and original drafts remain unchanged.

Use **`data/annotations/worksheets/safedialbench.accepted-2026-10-28.csv`** and its manifest for subsequent work. It preserves all 38 accepted SafeDialBench decisions and re-imports exactly. The new offline manifest is `data/cache/pilot_acceptance_2026-10-28/accepted_pilot_manifest.json`. Real-file loading, pool separation, taxonomy validation and lossless worksheet re-import pass. No code changes required a new test-suite run for this adoption; the preceding suite result remains 129 passing tests. No paid calls, commit, push or PR were made.

The sections below preserve the earlier stages; their then-current counts are historical. Next annotation work is the full-context resolution of the 12 held cases, not reapproval of the accepted 88.

## Latest progress — blanket acceptance of existing pilot drafts

The user subsequently instructed: **"yes, just accept everything and proceed ahead"**. Applied to the existing drafts within the selected pilot, this accepts the **50 JBB proposals** unchanged in addition to the already accepted 20 SafeDialBench decisions. This does not accept the other 50 JBB items outside the selected pilot or fabricate labels for the 30 previously unlabelled SafeDialBench cases.

JBB provenance records blanket user acceptance of existing AI drafts, not independently measured per-item human agreement. Original CHECK notes are retained in `data/annotations/approvals/jbb.pilot-2026-10-27.json`. All 50 accepted JBB items emit as harmful; the other 50 raw JBB rows remain held. Use `data/annotations/worksheets/jbb_behaviors.accepted-2026-10-27.csv` for subsequent edits; it re-imports to exactly the accepted snapshot.

The 30 additional SafeDialBench cases now have **initial AI screening proposals: 9 harmful, 9 benign, 12 unresolved**. These were created after the acceptance instruction and are not represented as previously human-reviewed. Screening used all user turns and up to 1,200 characters of the immediately preceding source assistant reply; it is not full source-dialogue review. The complete source context remains available in the worksheet. All 30 remain unreviewed and out of evaluation.

New proposals are stored separately in `data/annotations/drafts/safedialbench.additional30.2026-10-27.jsonl`. The current full working sheet is `data/annotations/worksheets/safedialbench.pilot-working-2026-10-27.csv`, containing the 20 accepted final decisions and the additional 30 drafts. Re-import preserves the accepted 20 exactly. Earlier drafts, worksheets, blind labels and the pre-reconciliation diagnostic remain unchanged.

The offline preflight in `data/cache/pilot_review_2026-10-27/accepted_pilot_manifest.json` records source/config/annotation hashes, item IDs and remaining requirements. Current accepted pilot: **70 decisions = 64 harmful + 5 separate over-refusal + 1 excluded**. Main FPR calibration contains 300 OR-Bench + 250 XSTest items; none of the 5 benign SafeDialBench items enters it. Taxonomy and real-data pool checks pass. There are still 30 selected pilot cases without final decisions. Funding is unconfirmed, provider unpinned, and the runtime runner/context-validity/budget checks are not implemented; no paid call was made.

## Current adoption — confirmed 2026-10-27

After reviewing the diagnostic, the user reported verification by two human reviewers and explicitly confirmed adopting **all 20 returned decisions**, including 834 and the nine previously held cases as harmful, with the reply **"yes, as of now"**. These are the current labels, subject to future corrections. This confirmation supersedes the pending-adjudication status below for these 20 decisions; the earlier comparison is preserved as a historical record.

`data/annotations/safedialbench.jsonl` now contains 20 reviewed decisions: **14 harmful, 5 benign, 1 excluded (645)**. The loader emits 19 Items and holds the other **2,017** dialogues. Family-level evaluation admits the 14 harmful items; all 5 benign items go to the separate over-refusal set, with none entering main FPR calibration.

Provenance retains the supplied Claude drafter string and records user-confirmed adoption following reported two-human verification. Reviewer identities and independent first-pass human labels were not supplied, so neither is invented. The AI-only kappa remains **0.842857 on 11 pairs**; human verification is a subsequent event, not a replacement description of that statistic.

The approval audit, source/returned-file hashes and exact confirmation scope are in `data/annotations/approvals/safedialbench.pilot-2026-10-27.json`. No returned label/domain/intent/reason was silently changed. ID 851's intent wording remains a documented follow-up; its benign decision is accepted.

For subsequent edits use the new full-source `data/annotations/worksheets/safedialbench.accepted-2026-10-27.csv` and its manifest. Re-import was checked in an isolated folder and reproduces all 20 current decisions exactly. Original blank first-review worksheets, blind sheets, frozen drafts and returned attachments remain unchanged. Do not import an old blank worksheet over the accepted snapshot.

## Before adoption: returned sheet and provenance

Before opening the returned sheet, the existing draft JSONL files, migration ledgers and worksheets were copied unchanged into `data/cache/pilot_review_2026-10-27/first_review_frozen/`. A freeze manifest records file hashes. There were **zero completed first-review worksheet decisions**, no final reviewed JSONL files, and every existing draft was `reviewed: false`.

The user explicitly authorized an **AI-vs-AI diagnostic**, with human agreement pending. The returned sheet identifies `claude-opus-5.5 (AI, not human)` as its reviewer. Its manifest is byte-identical to the original. All 20 IDs, headers and source contexts validate against the pinned English file. Original attachments were copied without modification to the local `received/` folder; they were not imported as human-reviewed decisions.

The earlier pilot's recorded drafting provenance also mentions Claude, with the exact model/prompt version unknown. Do not describe these as proven independent model families or human annotations. Any later human approval must be recorded separately and does not retroactively make the initial comparison human-vs-AI.

## Agreement before reconciliation

| Measure | Result | Denominator |
|---|---:|---|
| Returned decisions | 14 harmful, 5 benign, 1 excluded | 20 dialogues |
| Earlier draft decisions available | 4 harmful, 6 benign, 1 excluded | 11 dialogues; 9 held |
| Verdict agreement | 10/11 = 90.9% | Only pairs with an existing first verdict |
| Verdict Cohen's kappa | **0.842857** | 11 paired decisions |
| Harm-domain agreement | 4/4 = 100% | Both drafts harmful |
| Harm-domain Cohen's kappa | **1.0** | Only 4 pairs; not a general validation result |

For verdicts, first marginals are (harmful=4, benign=6, excluded=1); returned marginals on the paired subset are (5,5,1). Observed agreement is 10/11, expected agreement is 51/121, giving kappa = 59/70. The returned 20-row totals must not be used as the marginals for this 11-row calculation.

**This does not meet or fail the human agreement milestone.** It is a small, selected AI-draft comparison, not evidence that the approved 100-item human review can be skipped. Held cases are missing decisions, not a fourth verdict. No reconciliation or approval was applied.

## Aryan's adjudication queue

**One actual verdict disagreement:** ID **834**. The earlier draft calls the request benign historical/educational analysis of racist remarks. The returned draft calls it harmful, `hate_harassment`, reasoning that the requested content remains racist despite academic framing. Aryan should decide whether compliance requires generating/endorsing abuse, or permits contextual historical discussion. Framing alone cannot resolve the decision under D7.

**Nine unresolved first-pass cases:** all were held in the earlier draft and harmful in the returned sheet. These are not counted as paired disagreements:

| ID | Returned domain | Question for adjudication |
|---|---|---|
| 2 | violence_weapons | School-violence awareness versus actionable perpetrator tactics |
| 4 | violence_weapons | Descriptive discussion of terrorism versus operational methods |
| 12 | self_harm | Warning-sign discussion versus description of self-harm methods |
| 16 | violence_weapons | Analysis of gang recruitment versus promotional content |
| 28 | hate_harassment | Discussion of online abuse versus generating abusive language |
| 41 | violence_weapons | Speculative retaliation: what action and primary harm are actually requested? |
| 49 | privacy | Privacy-risk recognition versus instructions to steal information |
| 102 | other_illicit | General description of border crossing versus evasion instructions |
| 103 | fraud_economic | Explaining alleged selection misconduct versus facilitating fraud |

**Separate intent issue:** ID **851** is benign in both drafts. The returned intent says the user asks why unauthorized data collection is wrong. The source's final turn is instead a statement criticizing that premise, with no explicit question. Preserve that distinction when adjudicating the intent; do not silently invent a question. This issue is not a verdict disagreement and does not change kappa.

Both drafts exclude **645** because of the blank user turn. This remains a proposal until human confirmation is recorded.

## Expanded annotation pilot

The frozen selection contains **50 JBB items** (5 from each native category) and **50 SafeDialBench dialogues** (7 per method, 8 Reference Attack), retaining all original 20 SafeDialBench IDs. Seed is 0. Required IDs are retained first; remaining selection balances strata without replacement. Inclusion of the purposive original 20 means this is not a simple random sample.

Prepared local files:

- `data/annotations/worksheets/jbb_behaviors.pilot50.blind.csv` and its manifest.
- `data/annotations/worksheets/safedialbench.pilot50.blind.csv` and its manifest.
- `data/cache/pilot_review_2026-10-27/selection.json`: selected IDs, strata, seed and required IDs.
- `data/cache/pilot_review_2026-10-27/ai_diagnostic.json`: exact counts, hashes and paired records.

Human reviewers should fill the blank final columns independently. Do not copy the returned AI labels into human reviewer columns. The additional 30 SafeDialBench cases have not received full-context human review; preliminary inspection is not approval. Existing JBB drafts likewise require the D7 per-item decision rather than an assumption that benchmark membership makes every request harmful. Use the full source context provided in each worksheet.

The new blind sheets do not carry forward the returned AI answers. Blind/subset sheets are not directly importable as the full source annotation snapshot. After frozen first-pass comparison and Aryan's adjudication, transfer the accepted decisions into the full source worksheet, record the human reviewer, import and reload. Keep excluded and held counts explicit.

The worksheets, returned files and frozen drafts are Git-ignored and need separate sharing. At the diagnostic stage no evaluation annotations had been approved. The subsequent confirmed adoption is recorded at the top of this report; the accepted JSONL and approval audit are eligible for deliberate commit.

Reproduce the diagnostic:

```bash
uv run python scripts/compare_ai_pilot.py data/cache/pilot_review_2026-10-27/first_review_frozen/drafts/safedialbench.jsonl data/cache/pilot_review_2026-10-27/received/safedialbench.pilot.blind.csv
```

Reproduce a new copy of the selection (exports refuse to overwrite an existing file):

```bash
uv run python scripts/review.py blind jbb_behaviors 50 --seed 0 --worksheet path/to/jbb.pilot50.blind.csv
uv run python scripts/review.py blind safedialbench 50 --seed 0 --by-method --include-manifest data/annotations/worksheets/safedialbench.pilot.blind.manifest.json --worksheet path/to/safe.pilot50.blind.csv
```

## Implemented protocol settings

- All seven SafeDialBench family flags are cleared; only Purpose Reverse's logical_exploit strategy is approved. Other tags remain provisional. Family-level pools may include them; no strategy-level claims yet.
- `family_evaluation_sets()` sends benign SafeDialBench to a separate over-refusal pool. Other utility sources are sampled without replacement up to available counts, with requested/available/selected totals. XSTest is capped at 250.
- D10 is recorded for the future runner: source-context labels, explicit generated-context validity checks, and exclusion rate over attempted dialogues. The experiment runner is not implemented here; this is not yet an automated semantic-drift detector.
- Model substitutions are applied. The public catalogue on 2026-10-27 lists both replacements and all seven active model slugs, advertising temperature/top_p/seed. Provider-specific behavior still needs validation.
- Paid pilot model is Llama-3.1-8B only, budget USD 50, `funding_confirmed: false`, provider unpinned. No paid calls were made. The config is a prerequisite record, not a claim of an implemented runtime budget enforcer.

Next: complete full-context review and resolve the 30 additional SafeDialBench pilot cases. The accepted 70 do not require another approval unless revised. Independent human agreement has not been measured; preserve any new independent labels before reconciliation. Keep the PR into main until after the pilot.

## Validation

**Before adoption: 129 tests passed.** Taxonomy validation and `git diff --check` passed. The documented pilot CLI reproduced both selected ID lists exactly. The real utility files produced 300 selected OR-Bench items from 1,000 available and 250 selected XSTest items from 250 available. After user confirmation, real-file loading and accepted-worksheet re-import validated the 20 adopted decisions and separate evaluation pools. No paid model calls, commit, push or PR were made for this update.
