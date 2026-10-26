"""Gate between loaded Items and the evaluation set."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from harmfloor.schema import Item

BLOCKING_FIELDS = frozenset({"attack_family", "harm_domain", "strategy_tags"})


def evaluation_pool(items: Iterable[Item], *, allow_provisional_strategies: bool = False) -> list[Item]:
    """Require reviewed mappings. Aryan must approve any primary-axis-only strategy exception.

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
