import pytest

from harmfloor import taxonomy as t


def test_taxonomy_is_consistent():
    assert t.validate() == []


def test_lookups():
    assert t.attack_family("jailbreakradar", "PAIR").value == "feedback_based"
    assert t.attack_family("harmbench", "anything").value == "direct"
    assert t.attack_family("sok_guardrails", "ActorAttack").value == "multi_turn"
    assert t.strategy_tag("safedialbench", "Purpose Reverse").needs_review
    assert t.harm_domain("multibreak", "ChemBio").value == "cbrn"
    assert t.harm_domain("safedialbench", "Satire") is None


def test_unknown_label_fails_loudly():
    with pytest.raises(KeyError, match="taxonomy.yaml"):
        t.attack_family("jailbreakradar", "NotAnAttack")
