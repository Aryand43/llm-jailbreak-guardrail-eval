# Methodology and evaluation pipeline (ACL revision)

Status: draft, 21 Oct 2026. Method: Aryan. Data and pipeline: Aniket.
This is the source of truth for the research method. Changes after the protocol freeze go in §10.

## 1. Positioning

This is a **methodology paper**, not a benchmark paper. Aggregating existing benchmarks on its own would be a thin contribution. Instead, the benchmarks are the evidence base for the claim the NeurIPS submission made:

> Under support-preserving alignment and bounded filtering, harmful output has an **upper bound** (the ceiling an attack reaches with no defense) and a positive **lower bound** (a floor that more bounded-filter budget does not remove). The floor is a property of the regime, not of one attack type, one guardrail or one benchmark.

The revision crosses two axes:

| | Our method: bound analysis (U, L, decomposition) |
|---|---|
| **Attack taxonomy** (JailbreakRadar's six families + direct + multi-turn) | Does L > 0 hold in every family? Does its size follow what the theory predicts? |
| **Defenses** (SoK guardrails, at matched utility) | Do SOTA guardrails reach L = 0, or only lower U → ρ? |
| **Benchmarks** (JailbreakRadar, SoK sets, SafeDialBench, MultiBreak, …) | Does the conclusion survive a change of data source? |

The aggregated, taxonomy-labelled benchmark is released as a **supporting resource**, not claimed as the contribution. A public evaluation platform is a later extension (§9).

## 2. What changes from the NeurIPS submission

| NeurIPS submission | ACL revision | Why |
|---|---|---|
| 120 prompts (curated cyber + PKU) | Aggregate of ≥ 4 benchmarks, stratified by attack family | "Holds across benchmarks / taxonomy" |
| Keyword filters only | SoK guardrails (Llama Guard, WildGuard, SmoothLLM, input/session guards, optional GradientCuff) plus the NeurIPS filters as continuity baselines | The floor has to survive real defenses, not a strawman |
| Keyword harm predicate (coupled to the filter) | Independent judge (never the same family as the filter in that cell), plus human validation and judge-error correction | Removes evaluator–filter coupling, our own stated limitation |
| No utility constraint | Floors reported at matched false-positive rate on benign prompts (1 / **5** / 10 %) | Otherwise "refuse everything" trivially reaches zero |
| Plateau read off a plot | Floor estimated as a fitted asymptote with CIs, a model-free test at max budget, and an extrapolation check | A few budgets on ~100 prompts cannot separate "plateau" from "slow decay to 0" (§6.4) |
| q ∈ {1, 4, 16, 64}, independent sampling per q | One pool of n = 64 samples per prompt; best-of-q for every q ≤ 64 computed exactly from the pool | Seven budgets for the cost of one, and the curves share samples (less noise) |
| Single-turn only | Multi-turn family (SafeDialBench, MultiBreak, ActorAttack/X-Teaming via SoK) | MultiBreak's finding that multi-turn is much stronger is a direct test of the reasoning-asymmetry argument |

Every number in the ACL paper comes from fresh runs of this pipeline, logged at prompt and sample level. §5.1 re-runs the NeurIPS setting with the new pipeline.

## 3. Formal quantities

For model m, attack family a and defense f, over the prompts of cell (m, a):

- **Ceiling U(m, a):** probability that one unfiltered sample is harmful (q = 0). This is the upper bound: what the attack gets with no defense.
- **ρ(m, a, f, q):** probability that the output the defense returns at budget q is harmful.
- **Floor L(m, a, f):** asymptote of ρ in q. Fitted as

  ρ(q) = L + A · q^(−α),  q ≥ 1,  L, A ≥ 0, α > 0.

  This form nests both NeurIPS constructions. The cryptographic case gives a q-independent floor c_q = ε₀, which is L. The SQ case gives a residual decaying as Ω(d/q), which is the A·q^(−α) term with α ≈ 1. So the fitted α also says which regime a cell looks like.
- **Defense-agnostic floor L\*(m, a):** min over defenses f of L(m, a, f), at the same utility constraint.

**Interpretation of L for best-of-q (the explanatory link to the theory).** As q → n, best-of-q returns the sample the guard scores as safest. So L is the harmful mass **in the guard's most-trusted region**: harmful outputs the filter cannot tell from safe ones. That is the empirical counterpart of the indistinguishability in Thm. 2 (PRF-hidden features) and of support persistence in Thm. 1. The floor measures a filter's blind spot, not just "a number that didn't go down".

### 3.1 Interpretable safety measure: bound decomposition

Terry's proposal: say how close a model is to the upper and lower bounds. For a deployed operating point (model, defense, budget q), the observed ASR splits exactly into three parts:

```
U  =  (U − ρ)      +   (ρ − L)       +   L
      removed           reducible         irreducible
      distance to U     distance to L     floor
```

- **removed = D_U:** how far the defense has pulled the system from the unsafe bound. Larger is safer; this is the "farther from the unsafe bound" reading we agreed on.
- **reducible = D_L:** what more bounded-filter budget could still remove.
- **irreducible = L:** what no bounded filter removes; only non-support-preserving methods (unlearning, representation editing) can address it.
- **Band position p = (ρ − L)/(U − L) ∈ [0, 1]:** 1 means the defense does nothing; 0 means the defense is saturated and spending more on filtering is pointless.
- **Irreducible share L/U:** comparable across models with different ceilings.

This makes any benchmark's ASR number interpretable. Two models with the same ASR of 0.10 can differ completely: one is 0.09 irreducible, the other 0.01 irreducible and 0.09 reducible. Only the second can be fixed with more filtering.

**Visualisations** (`harmfloor/plots.py`):
1. **Bound map:** one dot per model at (U, L). The diagonal means the defense removes nothing; L = 0 is full mitigation. Distance from the diagonal is D_U. Match to the figure Terry drew in the 19 Oct call.
2. **Bound bands:** ρ(q) per model with U and L drawn as the two bounds.
3. **Decomposition bars:** removed / reducible / irreducible per model (and per attack family).
4. **Taxonomy heatmap:** L for models × attack families, with non-significant cells hatched.

## 4. Data: the aggregated benchmark

### 4.1 Sources
Core (the four papers): **JailbreakRadar** (160 forbidden questions, 16 violation categories, 17 attacks in 6 families); **SoK guardrails** (JailbreakHub IJP, JBB, MultiJail, SafeMTData, OR-Bench, AlpacaEval); **SafeDialBench** (4,053 EN/ZH dialogues, 7 attack strategies); **MultiBreak** (10,389 multi-turn prompts, 2,665 intents, 7 attack categories). Additional sources: HarmBench, StrongREJECT, MHJ, CoSafe, PKU-SafeRLHF (for continuity). Benign sources for utility: OR-Bench, XSTest, AlpacaEval. Full registry, licences and status: `configs/benchmarks.yaml`.

### 4.2 Unified schema and taxonomy
Every item becomes a `harmfloor.schema.Item`. Each carries its attack family, harm domain, strategy tags and intent cluster, with its native labels kept verbatim. Crosswalks live in `configs/taxonomy.yaml`:

- **Attack family (vertical axis):** JailbreakRadar's six (human-, obfuscation-, heuristic-, feedback-, fine-tuning-, generation-parameter-based), plus **direct** (no attack; the reference row) and **multi-turn** (our extension). SoK's attacks are re-filed under JailbreakRadar families (e.g. TAP → feedback, MultiJail → obfuscation).
- **Strategy tags (inside multi-turn):** MultiBreak's 7 categories and SafeDialBench's 7 strategies mapped to 7 shared tags. All seven SafeDialBench strategy proposals currently remain flagged pending supervisor review; see D9 below.
- **Harm domain:** 13 coarse domains that JailbreakRadar's 16, MultiBreak's 26 and SafeDialBench's second-tier labels all map onto. SafeDialBench's Impolite / Satire / Blasphemy are excluded from harm floors.

### 4.3 Deduplication and sampling
AdvBench, HarmBench, JBB and JailbreakRadar overlap heavily. Items are clustered by underlying intent (embedding similarity plus manual check of borderline pairs) into `intent_id`. This is also the bootstrap unit, so paraphrases of one intent do not count as independent evidence. The evaluation set is stratified per attack family (target sized by the power analysis in §6.4), balanced across harm domains where the sources allow it, with at most 3 items per intent per family.

**Transfer note.** Feedback- and fine-tuning-based prompts (GCG, PAIR, AdvPrompter, …) are optimised against a specific model. We use released artefacts as transfer attacks and record `attack_target_model`. On a 10% subset we run PAIR adaptively against each target, to check that transfer does not understate the ceiling.

## 5. Experiments (maps onto the Results section)

Terry's suggested order: first prove the concept, then show it holds across a wide range of benchmarks.

### 5.1 Proof of concept: the bounds exist (RQ1)
Re-run the NeurIPS setting with the new pipeline: same three models, curated cyber + PKU prompts, keyword filters + layered guardrail, plus Llama Guard best-of-q. Use pool n = 256 on this set so the floor can be checked beyond q = 64. Show U, the decay, the fitted L with CI, and the extrapolation check.

### 5.2 Across the attack taxonomy (RQ2): the vertical axis
For every model × attack family: U, L, and the decomposition, under the strongest defense at FPR ≤ 5%. Headline figure: the taxonomy heatmap of L.

### 5.3 Across defenses (RQ3): "they argue a fix, the floor remains"
For each SoK guardrail family, at its operating point and along its budget knob (scored candidates, SmoothLLM copies, GradientCuff samples): how much of U it removes, and whether L reaches 0. Report security–utility frontiers (L vs FPR), following SoK's Security-Efficiency-Utility framing.

### 5.4 Interpretation (RQ4)
Bound map and decomposition bars per model and per family. Are cross-model differences differences in ceiling, in floor, or in reducibility?

### 5.5 Robustness
Floors under each judge (primary, two secondary, and human-only on the annotated subset); judge-error-corrected floors; extrapolation from q ≤ 64 to q = 128/256; transfer vs adaptive attacks; per-benchmark breakdown, to show no single source drives the result.

## 6. Hypotheses and statistics (pre-registered before the main runs)

### 6.1 Hypotheses
- **H1 (floor persistence):** for every model × attack family, the judge-corrected harmful rate at the largest budget, under the strongest defense at FPR ≤ 5%, has a 95% lower bound above zero. This model-free test is the per-cell headline (§6.5 shows the fitted asymptote is too noisy per cell). Cells that fail are reported as counter-evidence, not dropped.
- **H2 (saturation, not slow decay):** on the n = 256 subset and on cells pooled within each attack family, the fitted floor L has a 95% lower bound above zero, and a fit on q ≤ 64 predicts the held-out q ∈ {128, 256} within CI.
- **H3 (theory-predicted ordering):** families that hide intent from a sequence-level filter (obfuscation, multi-turn) have a higher irreducible share L/U than families whose intent is lexically visible (direct, human-based). This fits JailbreakRadar's observation that heuristic attacks reach high ASR but are easy to mitigate (high U, low L/U) and MultiBreak's multi-turn results. It makes the bound analysis explanatory, not only descriptive.
- **H4 (granularity):** for multi-turn rows, session-level guards lower L relative to sequence-level guards but do not reach 0. SoK reports session-level guardrails still above 10% ASR on ActorAttack.

### 6.2 Estimation
- Per prompt, per q: exact best-of-q expectation from the pool (`bounds.best_of_q_harm`, closed form C(n−k, q−1)/C(n, q), ties averaged).
- Refusal threshold τ calibrated per defense and q on benign prompts to the FPR target (`bounds.calibrate_tau`).
- Cell rates are means over prompts. CIs come from a cluster bootstrap over `intent_id` (`bounds.estimate_bounds`).

### 6.3 Judge
- Primary judge: StrongREJECT-style rubric judge. Secondary: Qwen3Guard-Gen-8B and gpt-oss-safeguard-20b (both also used by MultiBreak). Rule: a judge never shares a model family with the scorer of the defense in the same cell.
- Human validation: 2 annotators, ~400 samples stratified by family × defense × judge label. Rubric from the NeurIPS appendix (actionability, specificity, operational detail). Report Cohen's κ.
- **Judge-error correction:** every reported rate is Rogan–Gladen corrected using the judge's sensitivity and specificity on the human sample, and that sample is resampled inside the bootstrap. Without this, a reviewer can argue the floor is just the judge's false-positive rate.

### 6.4 Two tests, not one
A positive harmful rate at the largest budget is easy to show: a rate of 0.07 on 100 prompts already has a 95% lower bound near 0.03. Showing that the *asymptote* is positive is much harder, because a slow decay to zero and a plateau look alike over a few budgets. Hence H1 uses the model-free test per cell, and H2 tests the asymptote only where there is enough data (§6.5).

### 6.5 Power analysis
Simulation: true curve ρ(q) = 0.044 + 0.156·q^(−0.43) (ρ falls from 0.20 at q = 1 to 0.07 at q = 64). Power = share of 60 simulated studies whose bootstrap 95% lower bound on the fitted L exceeds 0.001. Rates are resampled independently per budget, which is conservative: real curves share samples across q and are smoother.

| Prompts per cell | q ≤ 64 (7 budgets) | q ≤ 256 (9 budgets) | q ≤ 256, half the floor (L = 0.022) |
|---|---|---|---|
| 120 | 0.05 | 0.23 | 0.05 |
| 600 | 0.18 | 0.40 | 0.20 |
| 1200 | 0.25 | 0.50 | 0.35 |
| 2400 | 0.33 | 0.90 | 0.58 |

With no true floor (L = 0) the test fires in at most 7% of studies, so it does not invent floors. Conclusion: per-cell asymptote tests are out of reach at an affordable size. The asymptote is tested on the n = 256 subset with cells pooled within each attack family (H2), and the per-cell headline is the model-free test (H1).

## 7. Models and compute

- **Open-weight via OpenRouter only** for targets. We need n samples under fixed decoding, and the white-box guard needs weights. We keep the three NeurIPS models for continuity and add models the four papers also report (Llama-3.1-8B, Qwen3-8B, DeepSeek-R1-Distill-7B), so our ceilings can be sanity-checked against theirs. More models cover scale and family. Closed models are a later extension if their APIs expose enough (sampling control, log-probs).
- Multi-turn: replay the benchmark's user turns, generate earlier assistant turns greedily from the target, and pool only the final turn.
- **Cost is dominated by n × items × models generations plus the same number of judge calls.** Before any real run, the OpenRouter client (written fresh in this repo) logs token usage and cost per call, and a dry run estimates the total. No large run starts before the budget is approved.
- **GPU:** WildGuard and GradientCuff need local weights. If we have no GPU access, they drop to optional and Llama Guard (hosted) carries the LLM-guard rows.

## 8. Paper outline (ACL template; Terry's structure)

1. **Introduction:** jailbreak defenses keep improving on benchmarks. We show that under support-preserving alignment and bounded filters, a positive floor persists across the full attack taxonomy, SOTA guardrails and several benchmarks, and we give a decomposition that explains benchmark ASR.
2. **Related work:** jailbreak taxonomies and benchmarks (JailbreakRadar, SafeDialBench, MultiBreak, HarmBench, JBB); guardrails (SoK); alignment limits and impossibility results (carried over from NeurIPS).
3. **Method:** setting, U/L definitions, theory link (compressed theorems), estimators, decomposition.
4. **Experimental setup:** aggregate, taxonomy, models, defenses, judges, utility constraint.
5. **Results:** 5.1 proof of concept → 5.2 taxonomy → 5.3 guardrails → 5.4 interpretation → 5.5 robustness.
6. **Discussion and limitations:** scope (bounded filters, not every safety stack), transfer attacks, judge proxy, open-weight only.
7. **Resource statement:** aggregate + loaders + code.

## 9. Release and platform

- **Aggregate release:** where licences allow, items in the unified schema. Otherwise IDs plus loaders that rebuild the aggregate from the original sources. Every item records its source, version and licence.
- **Platform (later extension):** each run already produces per-model "bound cards" (U, L, decomposition per family). A platform renders these as a leaderboard and lets a user point the pipeline at their own endpoint. It is not on the critical path for the January submission.

## 10. Open decisions and deviation log

| # | Decision | Proposed | Needs |
|---|---|---|---|
| D1 | Bound-map axes | x = U, y = L, dots = models | Match Terry's figure from the 19 Oct call (Aryan has the screenshot) |
| D2 | Headline utility constraint | **Decided (Terry, 21 Oct):** FPR ≤ 5% headline; 1% and 10% as sensitivity analysis | — |
| D3 | Primary judge model | StrongREJECT rubric; model TBC | Aryan, after the judge pilot |
| D4 | GPU for WildGuard / GradientCuff | **Access confirmed (Prof. Anupam, 21 Oct; via Udayon).** GradientCuff on 70B+ targets depends on GPU memory | Aryan to check GPU specs with Udayon |
| D5 | Venue deadline | "ACL abstract, January" | confirm the ARR cycle and date |
| D6 | NeurIPS reviews | map each review point to a section here | Aryan to add reviews to `docs/` |
| D7 | Annotation inclusion and primary domain | **Pending:** operational harmful/benign/excluded rules and handling multiple domains; no automatic fixed priority order approved | Aryan to approve rubric and adjudicate ambiguous pilot items |
| D8 | Benign SafeDialBench and independent review | **Pending:** FPR eligibility, independent sample size, agreement criteria and reconciliation procedure | Aryan; preserve first reviews and compute agreement before reconciliation |
| D9 | SafeDialBench taxonomy and provisional tags | **Pending:** validate all seven family/strategy proposals; decide whether unresolved secondary tags can enter primary-axis analysis | Aryan; default gate blocks all open flags until a policy is recorded |
| D10 | Source-context annotation versus generated history | **Pending:** annotation uses source reference context while §7 generates target history; define context/intent validity checks and handling semantic drift | Aryan before evaluation; never replay source bot responses as target outputs |
| D11 | Target-model availability and pilot budget | **Pending:** four of nine configured slugs absent from public catalogue on 2026-10-26; choose replacements or omissions, provider pins and a bounded pilot budget | Aryan; catalogue parameter support is not proof of provider behavior |
