import csv
import json

import pytest
from pydantic import ValidationError

from harmfloor.data import jbb, safedialbench
from harmfloor.data.annotations import Annotation, gate, sha256_file
from harmfloor.schema import Item, Turn

# Placeholder text only: tests never need real harmful prompts.
JBB_ROWS = [
    {"Index": "0", "Goal": "request zero", "Target": "Sure", "Behavior": "B0", "Category": "Government decision-making", "Source": "Original"},
    {"Index": "1", "Goal": "request one", "Target": "Sure", "Behavior": "B1", "Category": "Privacy", "Source": "AdvBench"},
    {"Index": "2", "Goal": "request two", "Target": "Sure", "Behavior": "B2", "Category": "Expert advice", "Source": "Original"},
]
SDB_ROWS = [
    {"task": "Ethics", "method": "Scence Construct", "model_type": "ChatGPT", "scene": "Daily Life", "id": 1,
     "history": [{"user": "u1", "bot": "b1"}, {"user": "u2", "bot": "b2"}, {"user": "u3", "bot": "final"}]},
    {"task": "Legality", "method": "Purpose Reverse", "model_type": "ChatGPT", "scene": "Law and Morality", "id": 2,
     "history": [{"user": "u1", "bot": "b1"}, {"user": " ", "bot": "b2"}, {"user": "u3", "bot": "final"}]},
    {"task": "Privacy", "method": "Role Play", "model_type": "ChatGPT", "scene": "Employment", "id": 3,
     "history": [{"user": "u1", "bot": "b1"}, {"user": "u2", "bot": "final"}]},
]


@pytest.fixture
def jbb_raw(tmp_path):
    d = tmp_path / "raw" / "jbb_behaviors"
    d.mkdir(parents=True)
    with (d / jbb.FILENAME).open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(JBB_ROWS[0]))
        w.writeheader()
        w.writerows(JBB_ROWS)
    return d


@pytest.fixture
def sdb_raw(tmp_path):
    d = tmp_path / "raw" / "safedialbench"
    d.mkdir(parents=True)
    (d / safedialbench.FILENAME).write_text("".join(json.dumps(r) + "\n" for r in SDB_ROWS))
    return d


def write_notes(tmp_path, source, records):
    root = tmp_path / "annotations"
    root.mkdir(exist_ok=True)
    (root / f"{source}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records))
    return root


def note(source_id, sha, verdict, **kw):
    base = {"source_id": source_id, "source_sha256": sha, "verdict": verdict, "drafted_by": "human:test",
            "reviewed": True, "reviewer": "aryan"}
    return {**base, **kw}


def test_nothing_enters_without_reviewed_annotation(jbb_raw, tmp_path):
    sha = sha256_file(jbb_raw / jbb.FILENAME)
    root = write_notes(tmp_path, "jbb_behaviors", [
        note("0", sha, "harmful", harm_domain="cbrn"),
        {**note("1", sha, "harmful", harm_domain="privacy"), "reviewed": False, "reviewer": None},
    ])
    r = jbb.load(jbb_raw, root)
    assert [i.source_id for i in r.items] == ["0"]
    assert {h.source_id: h.reason for h in r.held} == {"1": "annotation not reviewed", "2": "no annotation"}
    item = r.items[0]
    assert item.harm_domain == "cbrn"  # the annotation decides, not the JBB category
    assert item.native_labels["Category"] == "Government decision-making"
    assert item.attack_family == "direct"
    assert item.intent == "request zero"


def test_benign_and_excluded_verdicts(jbb_raw, tmp_path):
    sha = sha256_file(jbb_raw / jbb.FILENAME)
    root = write_notes(tmp_path, "jbb_behaviors", [
        note("0", sha, "benign", reason="protective request"),
        note("1", sha, "excluded", reason="duplicate of 0"),
    ])
    r = jbb.load(jbb_raw, root)
    assert r.items[0].is_benign and r.items[0].harm_domain is None
    assert any(h.reason == "excluded: duplicate of 0" for h in r.excluded)


def test_annotation_for_a_different_file_is_rejected(jbb_raw, tmp_path):
    root = write_notes(tmp_path, "jbb_behaviors", [note("0", "0" * 64, "harmful", harm_domain="cbrn")])
    with pytest.raises(ValueError, match="different raw file"):
        jbb.load(jbb_raw, root)


@pytest.mark.parametrize("bad", [
    {"verdict": "harmful"},  # harmful without a domain
    {"verdict": "benign", "harm_domain": "cyber"},  # contradictory: benign with a domain
    {"verdict": "harmful", "harm_domain": "not_a_domain"},
    {"verdict": "excluded"},  # excluded without a reason
    {"verdict": "benign", "reviewed": True, "reviewer": None},
    {"verdict": "benign", "surprise_field": 1},
])
def test_contradictory_annotations_are_rejected(bad):
    with pytest.raises(ValidationError):
        Annotation.model_validate({"source_id": "0", "source_sha256": "x", "drafted_by": "human:t", **bad})


def test_duplicate_annotation_is_rejected(jbb_raw, tmp_path):
    sha = sha256_file(jbb_raw / jbb.FILENAME)
    root = write_notes(tmp_path, "jbb_behaviors", [note("0", sha, "benign", reason="safe"),
                                               note("0", sha, "benign", reason="safe")])
    with pytest.raises(ValueError, match="duplicate"):
        jbb.load(jbb_raw, root)


def test_safedialbench_turns_and_tags(sdb_raw, tmp_path):
    sha = sha256_file(sdb_raw / safedialbench.FILENAME)
    root = write_notes(tmp_path, "safedialbench", [
        note("1", sha, "harmful", harm_domain="violence_weapons", intent="intent one"),
        {**note("2", sha, "harmful", harm_domain="cyber", intent="intent two"), "reviewed": False},
        {**note("3", sha, "benign", reason="protective", intent="safe question"), "reviewed": False},
    ])
    r = safedialbench.load(sdb_raw, root)
    assert {h.source_id: h.reason for h in r.held} == {
        "2": "annotation not reviewed",
        "3": "annotation not reviewed",
    }
    (item,) = r.items
    # targets see user turns only; the runner regenerates assistant turns
    assert [t.role for t in item.turns] == ["user"] * 3
    assert [t.content for t in item.turns] == ["u1", "u2", "u3"]
    # reference keeps the source replies before the final user turn, never the final reply
    assert [t.content for t in item.reference_turns] == ["u1", "b1", "u2", "b2", "u3"]
    assert all(t.content != "final" for t in item.reference_turns)
    assert item.attack_family == "multi_turn"
    assert item.attack_method == "Scene Construct"
    assert item.native_labels["method"] == "Scence Construct"  # source typo kept verbatim
    assert item.strategy_tags == [] and item.provisional_tags == ["role_scene"]
    assert item.needs_review == ["attack_family", "strategy_tags"]


def test_provisional_strategy_tags_are_flagged(sdb_raw, tmp_path):
    rows = [dict(SDB_ROWS[0], id=9, method="Purpose Reverse")]
    (sdb_raw / safedialbench.FILENAME).write_text(json.dumps(rows[0]) + "\n")
    sha = sha256_file(sdb_raw / safedialbench.FILENAME)
    root = write_notes(tmp_path, "safedialbench", [note("9", sha, "harmful", harm_domain="cyber", intent="i")])
    (item,) = safedialbench.load(sdb_raw, root).items
    assert item.strategy_tags == [] and item.provisional_tags == ["logical_exploit"]


def test_item_rejects_benign_with_domain_and_missing_user_turn():
    base = dict(item_id="s:1", source="s", source_id="1", source_version="v", intent_id="s:1", intent="i",
                attack_family="direct", needs_review=[], license="MIT")
    with pytest.raises(ValidationError):
        Item(**base, turns=[Turn(role="user", content="x")], is_benign=True, harm_domain="cyber")
    with pytest.raises(ValidationError):
        Item(**base, turns=[Turn(role="assistant", content="x")], harm_domain="cyber")


def test_gate():
    assert gate(None) == "no annotation"
