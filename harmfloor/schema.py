"""Unified record schema for the aggregated benchmark and for run outputs.

Every benchmark loader (harmfloor/data/) emits `Item`s. Runs emit `PooledSample`s, then
`GuardScore`s and `HarmLabel`s keyed on (item_id, model, sample_idx). Bounds are computed only
from these records, so any analysis can be recomputed from the logs alone.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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

# Item fields whose values come from configs/taxonomy.yaml crosswalks.
MappedField = Literal["attack_family", "strategy_tags", "harm_domain"]

# What our review decided about an item the source did not label for us.
Disposition = Literal["harmful", "benign", "excluded"]


class Record(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class Turn(Record):
    role: Literal["system", "user", "assistant"]
    content: str


class Annotation(Record):
    """What our review decided for an item the source did not label for us. Never upstream data."""

    version: str  # sha256 of the reviewed annotation file
    disposition: Disposition
    domain: str | None = None  # the reviewed harm_domain; set iff disposition == "harmful"
    reason: str | None = None  # why benign or excluded; a reviewer note otherwise


class Item(Record):
    """One evaluation prompt (single- or multi-turn) after normalisation."""

    item_id: str  # "<source>:<source_id>", unique across the aggregate
    source: str  # key in configs/benchmarks.yaml
    source_id: str
    source_version: str  # dataset revision, commit or file sha256
    intent_id: str  # cross-benchmark dedupe cluster; the bootstrap unit
    intent: str  # the underlying request in plain form (for dedupe and judging)
    turns: list[Turn]  # target-bound conversation; the last turn is the user's
    is_benign: bool = False  # utility / over-refusal items (OR-Bench, XSTest, AlpacaEval)
    attack_family: AttackFamily
    attack_method: str | None = None  # e.g. "PAIR", "Base64", "ActorAttack"
    attack_target_model: str | None = None  # model the attack was optimised on (transfer tracking)
    strategy_tags: list[str] = Field(default_factory=list)
    harm_domain: str | None  # unified coarse domain, configs/taxonomy.yaml; None iff is_benign
    native_labels: dict[str, str] = Field(default_factory=dict)  # original labels, verbatim
    needs_review: list[MappedField]  # explicit, even when empty; legacy caches must be rebuilt
    annotation: Annotation | None = None  # set when the intent and harm domain come from our review
    license: str

    @field_validator("native_labels")
    @classmethod
    def reject_legacy_review_flags(cls, labels: dict[str, str]) -> dict[str, str]:
        legacy = sorted(key for key in labels if key.endswith("_needs_review"))
        if legacy:
            raise ValueError(
                f"legacy review flags in native_labels: {', '.join(legacy)}; "
                "rebuild the cache from raw data with the current loader"
            )
        return labels

    @model_validator(mode="after")
    def check_benign_has_no_domain(self) -> "Item":
        if self.is_benign != (self.harm_domain is None):
            raise ValueError("harm_domain must be set for harmful items and None for benign items")
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
