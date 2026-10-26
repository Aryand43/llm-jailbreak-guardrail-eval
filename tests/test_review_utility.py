import csv
import json
import math
import pytest
from harmfloor.data import review, utility
from harmfloor.data.annotations import load_annotations, sha256_file


def fill(path, **updates):
    with path.open(encoding="utf-8", newline="") as f:
        reader=csv.DictReader(f); fields=reader.fieldnames; rows=list(reader)
    rows[0].update(updates)
    with path.open("w", encoding="utf-8", newline="") as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(rows)


def sheet(data_case, tmp_path):
    _, raw, root, _, _ = data_case(); ws=tmp_path/"worksheet.csv"
    review.export_worksheet("jbb_behaviors",raw,ws,root)
    fill(ws, verdict="harmful", harm_domain="privacy", reviewer="aniket")
    return raw,root,ws


def test_withdrawing_last_approval_replaces_with_empty(data_case,tmp_path):
    raw,root,ws=sheet(data_case,tmp_path)
    assert review.import_worksheet("jbb_behaviors",ws,raw,root)==(1,[])
    fill(ws,verdict="")
    assert review.import_worksheet("jbb_behaviors",ws,raw,root)==(0,[])
    assert (root/"jbb_behaviors.jsonl").read_text()==""
    assert len(list((root/"history"/"jbb_behaviors").glob("*.jsonl")))==1


def test_changed_source_rejects_old_worksheet(data_case,tmp_path):
    raw,root,ws=sheet(data_case,tmp_path); review.import_worksheet("jbb_behaviors",ws,raw,root)
    before=(root/"jbb_behaviors.jsonl").read_bytes()
    with raw.open("a") as f: f.write("\n")
    with pytest.raises(ValueError,match="changed since"): review.import_worksheet("jbb_behaviors",ws,raw,root)
    assert (root/"jbb_behaviors.jsonl").read_bytes()==before


@pytest.mark.parametrize("updates", [{"verdict":"benign","harm_domain":"privacy"}, {"reviewer":" "},
                                    {"harm_domain":"invalid"}, {"intent":"invented"}])
def test_bad_completed_rows_do_not_replace_prior_snapshot(data_case,tmp_path,updates):
    raw,root,ws=sheet(data_case,tmp_path); review.import_worksheet("jbb_behaviors",ws,raw,root)
    before=(root/"jbb_behaviors.jsonl").read_bytes(); fill(ws,**updates)
    count,problems=review.import_worksheet("jbb_behaviors",ws,raw,root)
    assert count==0 and problems and (root/"jbb_behaviors.jsonl").read_bytes()==before


@pytest.mark.parametrize("updates", [{"source_id":"99"},{"source_id":"1"},{"context":"changed"}])
def test_worksheet_identity_cannot_be_edited(data_case,tmp_path,updates):
    raw,root,ws=sheet(data_case,tmp_path); fill(ws,**updates)
    with pytest.raises(ValueError): review.import_worksheet("jbb_behaviors",ws,raw,root)


def test_existing_worksheet_is_preserved(data_case,tmp_path):
    raw,root,ws=sheet(data_case,tmp_path); before=ws.read_bytes()
    with pytest.raises(FileExistsError): review.export_worksheet("jbb_behaviors",raw,ws,root)
    assert ws.read_bytes()==before


def test_blind_subset_never_replaces_reviewed_set(data_case,tmp_path):
    raw,root,ws=sheet(data_case,tmp_path); blind=tmp_path/"blind.csv"
    review.export_worksheet("jbb_behaviors",raw,blind,root,ids=["0"],blind=True)
    assert "draft_verdict" not in blind.read_text()
    with pytest.raises(ValueError,match="full first-reviewer"):
        review.import_worksheet("jbb_behaviors",blind,raw,root)


def test_export_includes_prior_assistant_but_not_final(data_case,tmp_path):
    _,raw,root,_,_=data_case("safedialbench"); ws=tmp_path/"safe.csv"
    review.export_worksheet("safedialbench",raw,ws,root)
    assert "Earlier context" in ws.read_text() and "FINAL BOT MUST NOT LEAK" not in ws.read_text()


def test_draft_snapshot_checked_and_authorship_preserved(data_case,tmp_path):
    _,raw,root,_,_=data_case(); (root/"drafts").mkdir()
    draft={"source_id":"0","source_sha256":sha256_file(raw),"verdict":"harmful",
           "harm_domain":"privacy","drafted_by":"model:example prompt:v1","reviewed":False,"note":"CHECK"}
    p=root/"drafts"/"jbb_behaviors.jsonl";p.write_text(json.dumps(draft)+"\n")
    ws=tmp_path/"ws.csv";review.export_worksheet("jbb_behaviors",raw,ws,root)
    assert "CHECK" in ws.read_text(); fill(ws,verdict="harmful",harm_domain="privacy",reviewer="aniket")
    draft["drafted_by"]="changed after export";p.write_text(json.dumps(draft)+"\n")
    review.import_worksheet("jbb_behaviors",ws,raw,root)
    assert load_annotations("jbb_behaviors",sha256_file(raw),root)["0"].drafted_by=="model:example prompt:v1"


def test_blind_sampling_and_degenerate_agreement():
    assert len(review.blind_sample({"a":list("abc"),"b":list("de")},4))==4
    with pytest.raises(ValueError): review.blind_sample({"a":["x"]},0)
    with pytest.raises(ValueError): review.blind_sample({"a":["x"],"b":["x"]},2)
    assert review.cohen_kappa(list("aabb"),list("aabb"))==1
    assert review.cohen_kappa(list("aabb"),list("abab"))==0
    assert math.isnan(review.cohen_kappa(["a"],["a"]))


def test_utility_safe_subset_and_duplicate_ids(tmp_path):
    ob=tmp_path/"or";ob.mkdir()
    (ob/"OR-Bench.json").write_text(json.dumps([{"index":7,"category":"deception","goal":"safe ask"}]))
    item=utility.load_or_bench(ob).items[0]
    assert item.is_benign and item.harm_domain is None and not item.needs_review
    xs=tmp_path/"xs";xs.mkdir(); path=xs/"xstest_prompts.csv"
    rows=[{"id":str(i),"prompt":"Example","label":label,"type":"homonyms","focus":"x"}
          for i,label in enumerate(["safe","unsafe"])]
    with path.open("w",newline="") as f:
        w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows)
    assert [i.source_id for i in utility.load_xstest(xs).items]==["0"]
    with path.open("a",newline="") as f: csv.DictWriter(f,fieldnames=rows[0]).writerow(rows[0])
    with pytest.raises(ValueError,match="duplicate"):utility.load_xstest(xs)


def test_missing_worksheet_row_cannot_silently_withdraw_approval(data_case,tmp_path):
    raw,root,ws=sheet(data_case,tmp_path)
    review.import_worksheet("jbb_behaviors",ws,raw,root)
    before=(root/"jbb_behaviors.jsonl").read_bytes()
    with ws.open(newline="") as f:
        reader=csv.DictReader(f); fields=reader.fieldnames; rows=list(reader)
    with ws.open("w",newline="") as f:
        writer=csv.DictWriter(f,fieldnames=fields); writer.writeheader(); writer.writerows(rows[:1])
    with pytest.raises(ValueError,match="rows are missing"):
        review.import_worksheet("jbb_behaviors",ws,raw,root)
    assert (root/"jbb_behaviors.jsonl").read_bytes()==before


def test_failed_atomic_replace_preserves_previous_annotations(data_case,tmp_path,monkeypatch):
    from harmfloor.data import _utils
    raw,root,ws=sheet(data_case,tmp_path)
    review.import_worksheet("jbb_behaviors",ws,raw,root)
    destination=root/"jbb_behaviors.jsonl"; before=destination.read_bytes()
    fill(ws,verdict="")
    replace=_utils.os.replace
    def fail_destination(src,dst):
        if dst==destination: raise OSError("simulated write failure")
        return replace(src,dst)
    monkeypatch.setattr(_utils.os,"replace",fail_destination)
    with pytest.raises(OSError,match="simulated"):
        review.import_worksheet("jbb_behaviors",ws,raw,root)
    assert destination.read_bytes()==before


def test_agreement_reports_denominators_and_undefined_kappa(data_case,tmp_path):
    raw,root,ws=sheet(data_case,tmp_path)
    review.import_worksheet("jbb_behaviors",ws,raw,root)
    first=load_annotations("jbb_behaviors",sha256_file(raw),root)
    blind=tmp_path/"blind.csv"
    review.export_worksheet("jbb_behaviors",raw,blind,root,blind=True)
    fill(blind,verdict="harmful",harm_domain="privacy",reviewer="independent reviewer")
    result=review.agreement(first,blind,source="jbb_behaviors",raw_file=raw)
    assert result["sampled"]==2 and result["second_completed"]==1
    assert result["verdict"]["n"]==1 and result["domain"]["n"]==1
    assert result["verdict"]["agreement"]==1 and result["verdict"]["kappa"] is None
