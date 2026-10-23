"""Unified record schema for the aggregated benchmark and for run outputs.

Every benchmark loader (harmfloor/data/) emits `Item`s. Runs emit `PooledSample`s, then
`GuardScore`s and `HarmLabel`s keyed on (item_id, model, sample_idx). Bounds are computed only
from these records, so any analysis can be recomputed from the logs alone.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# Vertical axis of the study: JailbreakRadar's six mechanism families, a no-attack reference,
# and multi-turn (our extension; JailbreakRadar has no multi-turn family). See configs/taxonomy.yaml.
AttackFamily = Literal[
    "direct",
    "human_based",
    "obfuscation_based",
    "heuristic_based",
    "feedback_based",
    "fine_tuning_based",
    "generation_parameter_based",
    "multi_turn",
]


class Record(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Turn(Record):
    role: Literal["system", "user", "assistant"]
    content: str


class Item(Record):
    """One evaluation prompt (single- or multi-turn) after normalisation."""

    item_id: str  # "<source>:<source_id>", unique across the aggregate
    source: str  # key in configs/benchmarks.yaml
    source_id: str
    source_version: str  # dataset revision, commit or file sha256
    intent_id: str  # cross-benchmark dedupe cluster; the bootstrap unit
    intent: str  # the underlying request in plain form (for dedupe and judging)
    # Target-bound turns; the last is the user's. Multi-turn items carry user turns only: the
    # runner generates the assistant turns with the target model (METHODOLOGY §7).
    turns: list[Turn]
    # The source's own full dialogue, including its assistant replies. Never sent to a target in
    # the main setup; kept for the replay ablation.
    reference_turns: list[Turn] = Field(default_factory=list)
    is_benign: bool = False  # utility / over-refusal items (OR-Bench, XSTest, AlpacaEval)
    attack_family: AttackFamily
    attack_method: str | None = None  # e.g. "PAIR", "Base64", "ActorAttack"
    attack_target_model: str | None = None  # model the attack was optimised on (transfer tracking)
    strategy_tags: list[str] = Field(default_factory=list)
    provisional_tags: list[str] = Field(default_factory=list)  # mappings still marked review: true
    harm_domain: str | None  # unified coarse domain (configs/taxonomy.yaml); None for benign items
    native_labels: dict[str, str] = Field(default_factory=dict)  # original labels, verbatim
    license: str

    @model_validator(mode="after")
    def _domain_matches_benign(self) -> "Item":
        if self.is_benign != (self.harm_domain is None):
            raise ValueError("benign items have no harm_domain; harmful items need one")
        if not self.turns or self.turns[-1].role != "user":
            raise ValueError("turns must end with a user turn")
        return self


class PooledSample(Record):
    """One of the n samples drawn per (item, model) for the best-of-q pool."""

    item_id: str
    model: str  # OpenRouter slug, pinned
    upstream_provider: str | None = None
    sample_idx: int
    text: str
    finish_reason: str | None = None
    request_id: str | None = None
    decoding: dict[str, float | int | None]


class GuardScore(Record):
    item_id: str
    model: str
    sample_idx: int
    guard: str  # key in configs/experiment.yaml defenses
    risk: float  # higher = riskier; guard-native score (e.g. P(unsafe))
    stage: Literal["pre", "intra", "post"]


class HarmLabel(Record):
    item_id: str
    model: str
    sample_idx: int
    judge: str  # judge key, or "human:<annotator>"
    harmful: bool
    score: float | None = None  # rubric score where the judge gives one
