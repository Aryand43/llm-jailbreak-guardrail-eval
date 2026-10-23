import csv
import json

import pytest

from harmfloor.data import review, utility
from harmfloor.data.annotations import load_annotations, sha256_file


def test_or_bench_and_xstest_are_benign(tmp_path):
    ob = tmp_path / "or_bench"
    ob.mkdir()
    (ob / "OR-Bench.json").write_text(json.dumps([{"index": 7, "category": "deception", "goal": "benign ask"}]))
    xs = tmp_path / "xstest"
    xs.mkdir()
    with (xs / "xstest_prompts.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "prompt", "type", "label", "focus", "note"])
        w.writeheader()
        w.writerow({"id": "1", "prompt": "safe ask", "type": "homonyms", "label": "safe", "focus": "x", "note": ""})
        w.writerow({"id": "2", "prompt": "unsafe ask", "type": "contrast_homonyms", "label": "unsafe", "focus": "x", "note": ""})
    (o,) = utility.load_or_bench(ob).items
    assert o.is_benign and o.harm_domain is None and o.item_id == "or_bench:7" and o.attack_family == "direct"
    xitems = utility.load_xstest(xs).items
    assert [i.source_id for i in xitems] == ["1"]  # unsafe contrast prompts excluded


def test_worksheet_round_trip(tmp_path):
    raw = tmp_path / "raw.csv"
    raw.write_text("placeholder\n")
    root = tmp_path / "ann"
    (root / "drafts").mkdir(parents=True)
    (root / "drafts" / "src.jsonl").write_text(json.dumps(
        {"source_id": "a", "verdict": "harmful", "harm_domain": "cyber", "drafted_by": "model:x prompt:v0"}) + "\n")
    ws = tmp_path / "ws.csv"
    review.export_worksheet("src", {"a": "ctx a", "b": "ctx b", "c": "ctx c"}, ws, root)
    rows = list(csv.DictReader(ws.open()))
    assert rows[0]["draft_harm_domain"] == "cyber" and rows[1]["draft_verdict"] == ""
    rows[0] |= {"verdict": "harmful", "harm_domain": "cyber", "reviewer": "aniket"}
    rows[1] |= {"verdict": "benign", "harm_domain": "cyber", "reviewer": "aniket"}  # contradictory
    with ws.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=review.FIELDS)
        w.writeheader()
        w.writerows(rows)
    n, problems = review.import_worksheet("src", ws, raw, root)
    assert n == 1 and len(problems) == 2  # b rejected, c not reviewed
    (a,) = load_annotations("src", sha256_file(raw), root).values()
    assert a.reviewed and a.reviewer == "aniket" and a.drafted_by == "model:x prompt:v0"


def test_blind_worksheet_hides_drafts(tmp_path):
    ws = tmp_path / "blind.csv"
    review.export_worksheet("src", {"a": "ctx"}, ws, tmp_path, blind=True)
    assert "draft_verdict" not in ws.read_text()


def test_blind_sample_spreads_across_strata():
    ids = review.blind_sample({"m1": list("abcdef"), "m2": list("gh"), "m3": list("ij")}, 6, seed=1)
    assert len(ids) == len(set(ids)) == 6
    assert sum(i in "gh" for i in ids) == 2 and sum(i in "ij" for i in ids) == 2


def test_cohen_kappa():
    assert review.cohen_kappa(list("aabb"), list("aabb")) == pytest.approx(1.0)
    assert review.cohen_kappa(list("aabb"), list("abab")) == pytest.approx(0.0)
    with pytest.raises(ValueError):
        review.cohen_kappa([], [])
