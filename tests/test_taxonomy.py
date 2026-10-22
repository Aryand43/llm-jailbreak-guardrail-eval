from copy import deepcopy

import pytest
import yaml

from harmfloor import taxonomy as t


def test_taxonomy_is_consistent():
    assert t.validate() == []


def test_lookups():
    assert t.attack_family("jailbreakradar", "PAIR").value == "feedback_based"
    assert t.attack_family("harmbench", "anything").value == "direct"
    assert t.attack_family("sok_guardrails", "ActorAttack").value == "multi_turn"
    assert t.attack_family("neurips_curated_cyber", "curated_cyber").value == "human_based"
    assert t.strategy_tag("safedialbench", "Purpose Reverse").needs_review
    assert t.harm_domain("multibreak", "ChemBio").value == "cbrn"
    assert t.harm_domain("safedialbench", "Satire") is None


def test_unknown_label_fails_loudly():
    with pytest.raises(KeyError, match="taxonomy.yaml"):
        t.attack_family("jailbreakradar", "NotAnAttack")


def test_legacy_source_name_is_rejected():
    tax = deepcopy(t.load())
    tax["attack_crosswalk"]["neurips_legacy"] = tax["attack_crosswalk"].pop("neurips_curated_cyber")

    assert t.validate(tax) == [
        "attack_crosswalk.neurips_legacy: source not registered in configs/benchmarks.yaml"
    ]


def test_unregistered_direct_source_is_rejected():
    tax = deepcopy(t.load())
    tax["attack_crosswalk"]["direct_sources"].append("advbench")

    assert t.validate(tax) == [
        "attack_crosswalk.direct_sources.advbench: source not registered in configs/benchmarks.yaml"
    ]
    with pytest.raises(KeyError, match="no attack-family mapping"):
        t.attack_family("advbench", "anything")


@pytest.mark.parametrize("path", [
    ("strategy_crosswalk",),
    ("harm_crosswalk",),
    ("harm_crosswalk", "excluded"),
])
def test_unregistered_source_in_other_crosswalks_is_rejected(path):
    tax = deepcopy(t.load())
    table = tax
    for key in path:
        table = table[key]
    table["unregistered_source"] = table.pop("safedialbench")

    assert t.validate(tax) == [
        f"{'.'.join(path)}.unregistered_source: source not registered in configs/benchmarks.yaml"
    ]


def test_source_checks_follow_supplied_registry():
    with t.BENCHMARKS_PATH.open(encoding="utf-8") as f:
        benchmarks = yaml.safe_load(f)
    benchmarks["prompts"].pop("neurips_curated_cyber")

    assert t.validate(benchmarks=benchmarks) == [
        "attack_crosswalk.neurips_curated_cyber: source not registered in configs/benchmarks.yaml"
    ]
