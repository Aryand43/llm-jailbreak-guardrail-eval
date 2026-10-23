import csv
import hashlib
import json
import logging
import re

import pytest

from harmfloor.data import evaluation_pool, jbb_behaviors, load, safedialbench
from harmfloor.schema import Annotation, Item, Turn


def make_item(**over):
    base = dict(
        item_id="s:1", source="s", source_id="1", source_version="sha256:x",
        intent_id="s:1", intent="an intent", turns=[Turn(role="user", content="hi")],
        attack_family="direct", harm_domain="privacy", needs_review=[], license="MIT",
    )
    base.update(over)
    return Item(**base)


# --- JBB ---

def write_jbb(root, *, entry="harmful", domain="privacy", reviewed=True, **overrides):
    root.mkdir(parents=True, exist_ok=True)
    row = {
        "Index": "0",
        "Goal": 'Synthetic test request, with "quotes"\nand a second line.',
        "Target": "Stored target response; must not enter the prompt.",
        "Behavior": "Test behavior",
        "Category": "Privacy",
        "Source": "Original",
    }
    row.update(overrides)
    path = root / jbb_behaviors.FILENAME
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=row)
        writer.writeheader()
        writer.writerow(row)
    dispositions = {
        "harmful": {"disposition": "harmful", "domain": domain, "reviewed": reviewed},
        "benign": {"disposition": "benign", "reason": "protective", "reviewed": reviewed},
        "excluded": {"disposition": "excluded", "reason": "rude only", "reviewed": reviewed},
        None: None,
    }
    annotations = {
        "source_version": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(),
        "items": {k: v for k, v in {row["Behavior"]: dispositions[entry]}.items() if v is not None},
    }
    annotation_path = root / jbb_behaviors.ANNOTATIONS_FILENAME
    annotation_path.write_text(json.dumps(annotations), encoding="utf-8")
    return row, path, annotations, annotation_path


def test_jbb_harmful_item_uses_reviewed_domain(tmp_path):
    row, path, _, annotation_path = write_jbb(tmp_path, domain="cyber")
    item, = jbb_behaviors.load(tmp_path)

    assert item.item_id == "jbb_behaviors:Test behavior"
    assert item.intent == row["Goal"]
    assert [(t.role, t.content) for t in item.turns] == [("user", row["Goal"])]
    assert item.attack_family == "direct" and item.attack_method is None
    assert item.harm_domain == "cyber" and not item.is_benign
    assert item.license == "MIT"
    assert item.source_version == "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    assert item.native_labels == {key: row[key] for key in ("Index", "Behavior", "Category", "Source")}
    assert item.needs_review == []
    assert item.annotation == Annotation(
        version="sha256:" + hashlib.sha256(annotation_path.read_bytes()).hexdigest(),
        disposition="harmful", domain="cyber",
    )
    assert Item.model_validate_json(item.model_dump_json()) == item


def test_jbb_benign_item_has_no_domain(tmp_path):
    write_jbb(tmp_path, entry="benign")
    item, = jbb_behaviors.load(tmp_path)
    assert item.is_benign and item.harm_domain is None
    assert item.annotation.disposition == "benign" and item.annotation.reason == "protective"
    assert jbb_behaviors.coverage(tmp_path).benign == ("Test behavior",)


@pytest.mark.parametrize("entry,bucket", [("excluded", "excluded"), (None, "held")])
def test_jbb_excluded_and_held_are_not_emitted(tmp_path, entry, bucket):
    write_jbb(tmp_path, entry=entry)
    assert list(jbb_behaviors.load(tmp_path)) == []
    assert getattr(jbb_behaviors.coverage(tmp_path), bucket) == ("Test behavior",)


def test_jbb_unreviewed_is_held(tmp_path):
    write_jbb(tmp_path, reviewed=False)
    assert list(jbb_behaviors.load(tmp_path)) == []
    assert jbb_behaviors.coverage(tmp_path).held == ("Test behavior",)


def test_jbb_duplicate_id_is_rejected(tmp_path):
    row, path, _, _ = write_jbb(tmp_path)
    with path.open("a", encoding="utf-8", newline="") as stream:
        csv.DictWriter(stream, fieldnames=row).writerow(row)
    with pytest.raises(ValueError, match="duplicate Behavior"):
        list(jbb_behaviors.read_behaviors(path))


def test_jbb_unknown_domain_is_rejected(tmp_path):
    write_jbb(tmp_path, domain="not_a_domain")
    with pytest.raises(ValueError, match="is not a harm_domain"):
        list(jbb_behaviors.load(tmp_path))


def test_jbb_unknown_behavior_in_annotations_is_rejected(tmp_path):
    _, _, annotations, annotation_path = write_jbb(tmp_path)
    annotations["items"]["ghost"] = {"disposition": "harmful", "domain": "cyber", "reviewed": True}
    annotation_path.write_text(json.dumps(annotations), encoding="utf-8")
    with pytest.raises(ValueError, match="Behavior ids not in the CSV"):
        list(jbb_behaviors.load(tmp_path))


@pytest.mark.parametrize("field", ["Goal", "Behavior", "Category", "Index", "Source"])
def test_jbb_missing_required_value_is_rejected(tmp_path, field):
    write_jbb(tmp_path, **{field: " "})
    with pytest.raises(ValueError, match="must be a nonempty string"):
        list(jbb_behaviors.load(tmp_path))


def test_jbb_invalid_header_is_rejected(tmp_path):
    path = tmp_path / jbb_behaviors.FILENAME
    path.write_text("Goal\nExample\n", encoding="utf-8")
    with pytest.raises(ValueError, match="invalid CSV header"):
        list(jbb_behaviors.read_behaviors(path))


def test_jbb_missing_file_is_actionable(tmp_path):
    with pytest.raises(FileNotFoundError, match="harmful-behaviors.csv"):
        list(jbb_behaviors.load(tmp_path))


def test_jbb_missing_annotations_is_actionable(tmp_path):
    _, _, _, annotation_path = write_jbb(tmp_path)
    annotation_path.unlink()
    with pytest.raises(FileNotFoundError, match="reviewed annotations are required"):
        list(jbb_behaviors.load(tmp_path))


# --- SafeDialBench ---

def write_safedial(root, *, disposition="harmful", domain="privacy", intent="Reviewed test intent",
                   reviewed=True, method="Scence Construct"):
    root.mkdir(parents=True, exist_ok=True)
    row = {
        "task": "Privacy", "method": method, "model_type": "ChatGPT", "scene": "Privacy and Security",
        "id": 7,
        "history": [
            {"user": "First test question", "bot": "First stored reply"},
            {"user": "Second test question", "bot": "Second stored reply"},
            {"user": "Final test question", "bot": "FINAL ANSWER MUST NOT LEAK"},
        ],
    }
    path = root / safedialbench.FILENAME
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    entry = {"harmful": {"disposition": "harmful", "domain": domain, "intent": intent, "reviewed": reviewed},
             "benign": {"disposition": "benign", "intent": intent, "reason": "protective", "reviewed": reviewed},
             "excluded": {"disposition": "excluded", "reason": "rude only", "reviewed": reviewed}}[disposition]
    annotations = {
        "source_version": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(),
        "items": {"7": entry},
    }
    annotation_path = root / safedialbench.ANNOTATIONS_FILENAME
    annotation_path.write_text(json.dumps(annotations), encoding="utf-8")
    return row, path, annotations, annotation_path


def write_safedial_rows(root, entries):
    """One dialogue per native ID in entries; an entry of None leaves that ID unannotated."""
    root.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "task": "Privacy", "method": "Role Play", "model_type": "ChatGPT", "scene": "Daily Life",
            "id": int(source_id),
            "history": [{"user": f"Question {source_id}", "bot": "Reply"}, {"user": "Final", "bot": "Stored"}],
        }
        for source_id in entries
    ]
    path = root / safedialbench.FILENAME
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    annotations = {
        "source_version": "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest(),
        "items": {source_id: entry for source_id, entry in entries.items() if entry is not None},
    }
    (root / safedialbench.ANNOTATIONS_FILENAME).write_text(json.dumps(annotations), encoding="utf-8")


def test_registry_loads_builtins_from_raw_root(tmp_path):
    write_jbb(tmp_path / "jbb_behaviors")
    write_safedial(tmp_path / "safedialbench")
    assert len(list(load("jbb_behaviors", tmp_path))) == 1
    assert len(list(load("safedialbench", tmp_path))) == 1
    with pytest.raises(KeyError, match="no loader registered"):
        list(load("unknown_source", tmp_path))


def test_safedial_harmful_preserves_context_without_final_answer(tmp_path):
    row, path, annotations, annotation_path = write_safedial(tmp_path, domain="cyber")
    item, = safedialbench.load(tmp_path)

    assert item.item_id == item.intent_id == "safedialbench:7"
    assert item.source == "safedialbench" and item.source_id == "7"
    assert item.intent == "Reviewed test intent"
    assert [(t.role, t.content) for t in item.turns] == [
        ("user", "First test question"), ("assistant", "First stored reply"),
        ("user", "Second test question"), ("assistant", "Second stored reply"),
        ("user", "Final test question"),
    ]
    assert "FINAL ANSWER MUST NOT LEAK" not in item.model_dump_json()
    assert item.source_version == annotations["source_version"]
    assert item.annotation == Annotation(
        version="sha256:" + hashlib.sha256(annotation_path.read_bytes()).hexdigest(),
        disposition="harmful", domain="cyber",
    )
    assert item.attack_family == "multi_turn" and item.attack_method == "Scence Construct"
    assert item.attack_target_model is None
    assert item.strategy_tags == ["role_scene"]
    assert item.harm_domain == "cyber" and not item.is_benign
    assert item.license == "Apache-2.0"
    assert item.needs_review == ["strategy_tags"]  # Scence Construct strategy still provisional
    assert item.native_labels == {
        **{key: row[key] for key in ("task", "method", "model_type", "scene")}, "id": "7",
    }
    assert Item.model_validate_json(item.model_dump_json()) == item


def test_safedial_benign_item_kept_without_domain(tmp_path):
    write_safedial(tmp_path, disposition="benign")
    item, = safedialbench.load(tmp_path)
    assert item.is_benign and item.harm_domain is None
    assert item.intent == "Reviewed test intent"
    assert safedialbench.coverage(tmp_path).benign == ("7",)


def test_safedial_approved_method_is_not_flagged(tmp_path):
    write_safedial(tmp_path, method="Purpose Reverse")
    item, = safedialbench.load(tmp_path)
    assert item.strategy_tags == ["logical_exploit"]
    assert item.needs_review == []  # family and strategy both approved for this method


def test_safedial_excluded_is_not_emitted(tmp_path):
    write_safedial(tmp_path, disposition="excluded")
    assert list(safedialbench.load(tmp_path)) == []
    assert safedialbench.coverage(tmp_path).excluded == ("7",)


def test_safedial_requires_annotations_without_guessing(tmp_path):
    _, _, _, annotation_path = write_safedial(tmp_path)
    annotation_path.unlink()
    with pytest.raises(FileNotFoundError, match="reviewed annotations are required"):
        list(safedialbench.load(tmp_path))


def test_safedial_rejects_annotations_for_different_data(tmp_path):
    _, path, _, _ = write_safedial(tmp_path)
    with path.open("a", encoding="utf-8") as stream:
        stream.write("\n")
    with pytest.raises(ValueError, match="source_version must match"):
        list(safedialbench.load(tmp_path))


def test_safedial_partial_annotations_split_into_four_buckets(tmp_path, caplog):
    write_safedial_rows(tmp_path, {
        "1": {"disposition": "harmful", "domain": "privacy", "intent": "x", "reviewed": True},
        "2": {"disposition": "benign", "intent": "y", "reviewed": True},
        "3": {"disposition": "harmful", "domain": "", "intent": "", "reviewed": False},
        "4": None,
        "5": {"disposition": "excluded", "reason": "rude", "reviewed": True},
    })
    caplog.set_level(logging.INFO)

    assert sorted(i.source_id for i in safedialbench.load(tmp_path)) == ["1", "2"]
    assert "Coverage(harmful=1, benign=1, held=2, excluded=1)" in caplog.text
    report = safedialbench.coverage(tmp_path)
    assert (report.harmful, report.benign, report.held, report.excluded) == (("1",), ("2",), ("3", "4"), ("5",))


@pytest.mark.parametrize("change", ["missing", "unreviewed", "unreviewed_draft"])
def test_safedial_missing_or_unreviewed_are_held(tmp_path, change):
    _, _, annotations, annotation_path = write_safedial(tmp_path)
    if change == "missing":
        annotations["items"].clear()
    elif change == "unreviewed":
        annotations["items"]["7"]["reviewed"] = False
    else:  # a messy draft is held, not validated, until reviewed
        annotations["items"]["7"] = {"disposition": "harmful", "domain": "nope", "reviewed": False}
    annotation_path.write_text(json.dumps(annotations), encoding="utf-8")

    assert list(safedialbench.load(tmp_path)) == []
    assert safedialbench.coverage(tmp_path).held == ("7",)


@pytest.mark.parametrize("change", ["unknown_id", "string_reviewed", "not_object", "bad_disposition",
                                    "blank_intent", "unknown_domain", "domain_on_benign",
                                    "intent_on_excluded", "unknown_key"])
def test_safedial_invalid_reviewed_entries_fail_before_yield(tmp_path, change):
    _, _, annotations, annotation_path = write_safedial(tmp_path)
    entry = annotations["items"]["7"]
    if change == "unknown_id":
        annotations["items"]["99"] = dict(entry)
    elif change == "string_reviewed":
        entry["reviewed"] = "true"
    elif change == "not_object":
        annotations["items"]["7"] = "privacy"
    elif change == "bad_disposition":
        entry["disposition"] = "maybe"
    elif change == "blank_intent":
        entry["intent"] = " "
    elif change == "unknown_domain":
        entry["domain"] = "nope"
    elif change == "domain_on_benign":
        annotations["items"]["7"] = {"disposition": "benign", "intent": "y", "domain": "privacy", "reviewed": True}
    elif change == "intent_on_excluded":
        annotations["items"]["7"] = {"disposition": "excluded", "reason": "r", "intent": "y", "reviewed": True}
    else:
        entry["harm_label"] = "legacy key"
    annotation_path.write_text(json.dumps(annotations), encoding="utf-8")
    with pytest.raises((ValueError, KeyError)):
        next(safedialbench.load(tmp_path))


def test_safedial_unknown_method_is_not_guessed(tmp_path):
    write_safedial(tmp_path, method="New strategy")
    with pytest.raises(KeyError, match="no attack-family mapping"):
        list(safedialbench.load(tmp_path))


@pytest.mark.parametrize("change", ["duplicate", "bad_json", "missing_bot", "bool_id", "short_history"])
def test_safedial_raw_structure_errors_are_actionable(tmp_path, change):
    row, path, _, _ = write_safedial(tmp_path)
    if change == "duplicate":
        path.write_text((json.dumps(row) + "\n") * 2, encoding="utf-8")
    elif change == "bad_json":
        path.write_text("{broken json}\n", encoding="utf-8")
    else:
        if change == "missing_bot":
            del row["history"][0]["bot"]
        elif change == "bool_id":
            row["id"] = True
        else:
            row["history"] = row["history"][:1]
        path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match=re.escape(str(path))):
        list(safedialbench.read_dialogues(path))


def test_safedial_duplicate_annotation_keys_are_rejected(tmp_path):
    _, _, _, annotation_path = write_safedial(tmp_path)
    annotation_path.write_text('{"items": {}, "items": {}}', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate annotation key"):
        list(safedialbench.load(tmp_path))


def test_safedial_blank_user_in_reviewed_item_requires_exclusion(tmp_path):
    row, path, annotations, annotation_path = write_safedial(tmp_path)
    row["history"][1]["user"] = "\r"
    path.write_text(json.dumps(row) + "\n", encoding="utf-8")
    annotations["source_version"] = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
    annotation_path.write_text(json.dumps(annotations), encoding="utf-8")
    with pytest.raises(ValueError, match="must be a nonempty string"):
        list(safedialbench.load(tmp_path))

    annotations["items"]["7"] = {"disposition": "excluded", "reason": "blank user turn", "reviewed": True}
    annotation_path.write_text(json.dumps(annotations), encoding="utf-8")
    assert list(safedialbench.load(tmp_path)) == []
    assert safedialbench.coverage(tmp_path).excluded == ("7",)


# --- evaluation gate and schema invariants ---

@pytest.mark.parametrize("flag,blocked", [
    ("harm_domain", True), ("attack_family", True), ("strategy_tags", False),
])
def test_evaluation_pool_blocks_only_primary_axes(flag, blocked):
    item = make_item(needs_review=[flag])
    if blocked:
        with pytest.raises(ValueError, match=re.escape(f"s.{flag} (1)")):
            evaluation_pool([item])
    else:
        assert evaluation_pool([item]) == [item]


def test_evaluation_pool_admits_reviewed_items(tmp_path):
    write_jbb(tmp_path)
    assert evaluation_pool(jbb_behaviors.load(tmp_path))  # harmful, needs_review == []


def test_benign_item_must_not_carry_a_domain():
    with pytest.raises(ValueError, match="harm_domain must be set"):
        make_item(is_benign=True, harm_domain="privacy")
    with pytest.raises(ValueError, match="harm_domain must be set"):
        make_item(is_benign=False, harm_domain=None)


def test_cache_must_record_review_state_explicitly():
    record = make_item().model_dump()
    record.pop("needs_review")
    with pytest.raises(ValueError, match="needs_review"):
        Item.model_validate_json(json.dumps(record))


def test_legacy_native_review_flags_are_rejected():
    record = make_item().model_dump()
    record["native_labels"]["harm_domain_needs_review"] = "true"
    with pytest.raises(ValueError, match="legacy review flags in native_labels"):
        Item.model_validate_json(json.dumps(record))
