"""Load configs/taxonomy.yaml and map native benchmark labels onto the unified axes."""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, get_args

import yaml

from harmfloor.schema import AttackFamily

TAXONOMY_PATH = Path(__file__).resolve().parents[1] / "configs" / "taxonomy.yaml"
BENCHMARKS_PATH = TAXONOMY_PATH.with_name("benchmarks.yaml")


@dataclass(frozen=True)
class Mapping:
    value: str
    needs_review: bool


def _entry(raw: Any, key: str) -> Mapping:
    if isinstance(raw, dict):
        return Mapping(raw[key], bool(raw.get("review", False)))
    return Mapping(raw, False)


@cache
def load(path: Path = TAXONOMY_PATH) -> dict[str, Any]:
    with path.open() as f:
        return yaml.safe_load(f)


def harm_domains() -> frozenset[str]:
    """The unified coarse domains a reviewed annotation may assign."""
    return frozenset(load()["harm_domains"])


def attack_family(source: str, method: str) -> Mapping:
    tax = load()
    if source in tax["attack_crosswalk"]["direct_sources"]:
        return Mapping("direct", False)
    try:
        return _entry(tax["attack_crosswalk"][source][method], "family")
    except KeyError:
        raise KeyError(f"no attack-family mapping for {source}:{method!r}; add it to configs/taxonomy.yaml") from None


def strategy_tag(source: str, strategy: str) -> Mapping:
    try:
        return _entry(load()["strategy_crosswalk"][source][strategy], "tag")
    except KeyError:
        raise KeyError(f"no strategy mapping for {source}:{strategy!r}") from None


def harm_domain(source: str, label: str) -> Mapping | None:
    """Unified domain for a native harm label; None if the label is excluded from harm floors."""
    tax = load()
    if label in tax["harm_crosswalk"]["excluded"].get(source, []):
        return None
    try:
        return _entry(tax["harm_crosswalk"][source][label], "domain")
    except KeyError:
        raise KeyError(f"no harm-domain mapping for {source}:{label!r}") from None


def validate(
    tax: dict[str, Any] | None = None,
    benchmarks: dict[str, Any] | None = None,
) -> list[str]:
    """Check source keys against the registry and family/domain targets against the taxonomy.

    Registered benchmarks may lack crosswalks while their loaders are still pending.
    Returns a list of problems.
    """
    if tax is None:
        tax = load()
    if benchmarks is None:
        with BENCHMARKS_PATH.open(encoding="utf-8") as f:
            benchmarks = yaml.safe_load(f)
    problems = []
    registered_sources = {source for entries in benchmarks.values() for source in entries}
    source_references = [
        ("attack_crosswalk", set(tax["attack_crosswalk"]) - {"direct_sources"}),
        ("attack_crosswalk.direct_sources", tax["attack_crosswalk"]["direct_sources"]),
        ("strategy_crosswalk", tax["strategy_crosswalk"]),
        ("harm_crosswalk", set(tax["harm_crosswalk"]) - {"excluded"}),
        ("harm_crosswalk.excluded", tax["harm_crosswalk"]["excluded"]),
    ]
    for path, sources in source_references:
        for source in sorted(sources):
            if source not in registered_sources:
                problems.append(f"{path}.{source}: source not registered in configs/benchmarks.yaml")
    families, domains = set(tax["attack_families"]), set(tax["harm_domains"])
    if families != set(get_args(AttackFamily)):
        problems.append(f"attack_families {sorted(families)} != schema.AttackFamily")
    for source, table in tax["attack_crosswalk"].items():
        if source == "direct_sources":
            continue
        for method, raw in table.items():
            if _entry(raw, "family").value not in families:
                problems.append(f"attack_crosswalk.{source}.{method}")
    for source, table in tax["harm_crosswalk"].items():
        if source == "excluded":
            continue
        for label, raw in table.items():
            if _entry(raw, "domain").value not in domains:
                problems.append(f"harm_crosswalk.{source}.{label}")
    return problems
