import csv
import json
import pytest
from harmfloor.data import evaluation_pool, jbb, safedialbench
from harmfloor.data.annotations import sha256_file
from harmfloor.data.sources import read_jbb, read_safedial
from harmfloor.schema import Item


@pytest.mark.parametrize("source", ["jbb_behaviors", "safedialbench"])
def test_missing_notes_hold_every_record(data_case, source):
    raw, _, ann, _, _ = data_case(source)
    module = jbb if source == "jbb_behaviors" else safedialbench
    assert module.load(raw, ann).coverage == dict(harmful=0, benign=0, held=2, excluded=0)


@pytest.mark.parametrize("value", ["true", "false", 1, 0, None])
def test_review_flag_is_strict(data_case, value):
    raw, _, ann, _, notes = data_case(); notes(reviewed=value)
    with pytest.raises(ValueError): jbb.load(raw, ann)


@pytest.mark.parametrize("reviewer", ["", " ", "\n", None])
def test_review_requires_identity(data_case, reviewer):
    raw, _, ann, _, notes = data_case(); notes(reviewer=reviewer)
    with pytest.raises(ValueError): jbb.load(raw, ann)


@pytest.mark.parametrize("source", ["jbb_behaviors", "safedialbench"])
def test_unknown_annotation_id_fails(data_case, source):
    raw, _, ann, _, notes = data_case(source); notes(source_id="999")
    with pytest.raises(ValueError, match="not in source"):
        (jbb if source == "jbb_behaviors" else safedialbench).load(raw, ann)


@pytest.mark.parametrize("source", ["jbb_behaviors", "safedialbench"])
def test_duplicate_raw_ids_fail_without_annotations(data_case, source):
    raw, path, ann, rows, _ = data_case(source)
    if source == "jbb_behaviors":
        with path.open("a", newline="") as f: csv.DictWriter(f, fieldnames=rows[0]).writerow(rows[0])
    else:
        with path.open("a") as f: f.write(json.dumps(rows[0]) + "\n")
    with pytest.raises(ValueError, match="duplicate"):
        (jbb if source == "jbb_behaviors" else safedialbench).load(raw, ann)


@pytest.mark.parametrize("field", ["Index", "Behavior", "Goal", "Category", "Source"])
def test_jbb_missing_text(data_case, field):
    _, path, _, rows, _ = data_case(); rows[0][field] = " "
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0]); w.writeheader(); w.writerows(rows)
    with pytest.raises(ValueError, match="nonempty"): read_jbb(path)


@pytest.mark.parametrize("change", ["id_bool", "history_short", "missing_bot", "bad_json", "duplicate_key"])
def test_safe_raw_structure(data_case, change):
    _, path, _, rows, _ = data_case("safedialbench")
    if change == "id_bool": rows[0]["id"] = True
    elif change == "history_short": rows[0]["history"] = []
    elif change == "missing_bot": del rows[0]["history"][0]["bot"]
    text = json.dumps(rows[0]) + "\n"
    if change == "bad_json": text = "{broken}\n"
    if change == "duplicate_key": text = '{"id": 1, "id": 2}\n'
    path.write_text(text)
    with pytest.raises(ValueError): read_safedial(path)


def test_all_methods_checked_while_held(data_case):
    raw, path, ann, rows, _ = data_case("safedialbench"); rows[0]["method"] = "Unknown"
    path.write_text("".join(json.dumps(r)+"\n" for r in rows))
    with pytest.raises(KeyError): safedialbench.load(raw, ann)


def test_blank_turn_requires_reviewed_exclusion(data_case):
    raw, path, ann, rows, notes = data_case("safedialbench")
    rows[0]["history"][0]["user"] = "\r"
    path.write_text("".join(json.dumps(r)+"\n" for r in rows))
    assert len(safedialbench.load(raw, ann).held) == 2
    notes()
    with pytest.raises(ValueError, match="blank source turn"): safedialbench.load(raw, ann)
    notes(verdict="excluded", harm_domain=None, intent=None, reason="Unusable context")
    assert len(safedialbench.load(raw, ann).excluded) == 2


def test_native_labels_and_provenance_survive_roundtrip(data_case):
    raw, _, ann, rows, notes = data_case(); notes()
    item = jbb.load(raw, ann).items[0]
    assert item.native_labels == {k: v for k,v in rows[0].items() if k not in {"Goal", "Target"}}
    assert item.annotation.version == "sha256:" + sha256_file(ann/"jbb_behaviors.jsonl")
    assert item.annotation.reviewer == "test"
    assert Item.model_validate_json(item.model_dump_json()) == item
    assert evaluation_pool([item]) == [item]
    with pytest.raises(ValueError, match="duplicate"): evaluation_pool([item,item])


@pytest.mark.parametrize("change", ["domain", "benign", "excluded", "source_id", "source_hash", "intent", "missing_review", "legacy"])
def test_cache_cannot_contradict_annotation(data_case, change):
    raw, _, ann, _, notes = data_case(); notes()
    record = jbb.load(raw, ann).items[0].model_dump()
    if change == "domain": record["annotation"]["domain"] = "cyber"
    elif change == "benign": record["annotation"].update(disposition="benign", domain=None)
    elif change == "excluded": record["annotation"]["disposition"] = "excluded"
    elif change == "source_id": record["annotation"]["source_id"] = "123"
    elif change == "source_hash": record["annotation"]["source_sha256"] = "0"*64
    elif change == "intent": record["annotation"]["intent"] = "different request"
    elif change == "missing_review": record.pop("needs_review")
    else: record["native_labels"]["harm_domain_needs_review"] = "true"
    with pytest.raises(ValueError): Item.model_validate_json(json.dumps(record))


def test_safe_reference_and_provisional_gate(data_case):
    raw, _, ann, _, notes = data_case("safedialbench"); notes()
    item = safedialbench.load(raw, ann).items[0]
    assert [t.role for t in item.turns] == ["user", "user"]
    assert [t.role for t in item.reference_turns] == ["user", "assistant", "user"]
    assert "FINAL BOT MUST NOT LEAK" not in item.model_dump_json()
    assert item.provisional_tags == ["role_scene"] and not item.strategy_tags
    with pytest.raises(ValueError): evaluation_pool([item])
    with pytest.raises(ValueError): evaluation_pool([item], allow_provisional_strategies=True)
    approved_family = item.model_copy(update={"needs_review": ["strategy_tags"]})
    with pytest.raises(ValueError): evaluation_pool([approved_family])
    assert evaluation_pool([approved_family], allow_provisional_strategies=True)


@pytest.mark.parametrize("verdict", ["benign", "excluded"])
@pytest.mark.parametrize("reason", [None, "", " "])
def test_nonharmful_decisions_need_reason(data_case, verdict, reason):
    raw, _, ann, _, notes = data_case(); notes(verdict=verdict, harm_domain=None, reason=reason)
    with pytest.raises(ValueError): jbb.load(raw, ann)
