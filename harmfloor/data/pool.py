"""Gate between loaded Items and the evaluation set."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
import random

from harmfloor.schema import Item

BLOCKING_FIELDS = frozenset({"attack_family", "harm_domain", "strategy_tags"})


def evaluation_pool(items: Iterable[Item], *, allow_provisional_strategies: bool = False) -> list[Item]:
    """Require reviewed mappings; D9 allows the explicit exception for family analysis only.

    Flagged items are refused, not dropped: dropping them would silently skew the pool.
    Validate the `review: true` mappings in configs/taxonomy.yaml, then reload.
    """
    items = list(items)
    duplicates = [key for key, count in Counter(i.item_id for i in items).items() if count > 1]
    if duplicates:
        raise ValueError(f"duplicate evaluation item IDs: {duplicates[:10]}")
    blocking = BLOCKING_FIELDS - ({"strategy_tags"} if allow_provisional_strategies else set())
    pending = Counter(
        f"{item.source}.{field}"
        for item in items
        for field in set(item.needs_review) | ({"strategy_tags"} if item.provisional_tags else set())
        if field in blocking
    )
    if pending:
        detail = ", ".join(f"{key} ({count})" for key, count in sorted(pending.items()))
        raise ValueError(
            f"unreviewed taxonomy mappings: {detail}; validate the review: true entries in "
            "configs/taxonomy.yaml before building the evaluation set"
        )
    return items


@dataclass
class FamilyEvaluationSets:
    harmful: list[Item]
    fpr_calibration: list[Item]
    over_refusal: list[Item]
    sampling_counts: dict[str, dict[str, int]]


def family_evaluation_sets(items: Iterable[Item], *, benign_per_source: int = 300,
                           seed: int = 0) -> FamilyEvaluationSets:
    """D8/D9/D12: family-level pools, separate SafeDialBench benign, capped utility.

    Provisional tags are retained for audit, not approved for strategy-level claims.
    Sampling is without replacement and deterministic for a given input set and seed.
    """
    if type(benign_per_source) is not int or benign_per_source < 0:
        raise ValueError("benign_per_source must be a nonnegative integer")
    accepted = evaluation_pool(items, allow_provisional_strategies=True)
    harmful, over_refusal, benign = [], [], {}
    for item in accepted:
        if not item.is_benign:
            harmful.append(item)
        elif item.source == "safedialbench":
            over_refusal.append(item)
        else:
            benign.setdefault(item.source, []).append(item)
    rng = random.Random(seed)
    calibration, counts = [], {}
    for source, rows in sorted(benign.items()):
        rows = sorted(rows, key=lambda item: item.item_id)
        count = min(benign_per_source, len(rows))
        calibration.extend(rng.sample(rows, count))
        counts[source] = {"requested": benign_per_source, "available": len(rows), "selected": count}
    return FamilyEvaluationSets(harmful, calibration, over_refusal, counts)
