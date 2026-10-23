"""Gate between loaded Items and the evaluation set."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from harmfloor.schema import Item

# Mappings that place an item on a reported axis: an unreviewed one would move a bound.
# strategy_tags are a secondary axis and do not block (team decision, rule 5).
BLOCKING_FIELDS = frozenset({"attack_family", "harm_domain"})


def evaluation_pool(items: Iterable[Item]) -> list[Item]:
    """Admit items for sampling only if no primary-axis label rests on an unreviewed mapping.

    Flagged items are refused, not dropped: dropping them would silently skew the pool.
    Validate the `review: true` mappings in configs/taxonomy.yaml, then reload.
    """
    items = list(items)
    pending = Counter(
        f"{item.source}.{field}"
        for item in items
        for field in item.needs_review
        if field in BLOCKING_FIELDS
    )
    if pending:
        detail = ", ".join(f"{key} ({count})" for key, count in sorted(pending.items()))
        raise ValueError(
            f"unreviewed taxonomy mappings: {detail}; validate the review: true entries in "
            "configs/taxonomy.yaml before building the evaluation set"
        )
    return items
