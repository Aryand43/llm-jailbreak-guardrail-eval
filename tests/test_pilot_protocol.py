import csv
import json
from pathlib import Path

import pytest
import yaml

from harmfloor import taxonomy
from harmfloor.data import family_evaluation_sets, safedialbench
from harmfloor.data.annotations import sha256_file
from harmfloor.data.pilot import compare_ai_drafts
from harmfloor.data.review import blind_sample, export_worksheet
from harmfloor.schema import Item, Turn


def test_required_pilot_ids_preserved_and_strata_balanced():
    strata={"a":[str(i) for i in range(10)], "b":[str(i) for i in range(10,20)]}
    ids=blind_sample(strata,10,seed=0,required_ids=["0","1","2"])
    assert ids[:3]==["0","1","2"] and len(set(ids))==10
    assert sum(i in strata["a"] for i in ids)==5
    assert ids==blind_sample(strata,10,seed=0,required_ids=["0","1","2"])
    for required in [["0","0"],["unknown"],list(map(str,range(6)))]:
        with pytest.raises(ValueError): blind_sample(strata,5,required_ids=required)


def test_sampling_metadata_is_written_in_initial_manifest(data_case,tmp_path):
    _,raw,root,_,_=data_case()
    ws=tmp_path/"sample.csv"
    sampling={"seed":0,"required_ids":["0"]}
    export_worksheet("jbb_behaviors",raw,ws,root,ids=["0"],blind=True,sampling=sampling)
    manifest=json.loads(ws.with_suffix(".manifest.json").read_text())
    assert manifest["sampling"]==sampling and manifest["ids"]==["0"]


def test_family_sets_separate_safe_benign_and_cap_utility(data_case):
    raw,_,root,_,notes=data_case("safedialbench")
    notes(verdict="benign",harm_domain=None,reason="protective")
    safe=safedialbench.load(raw,root).items
    utility=[Item(item_id=f"xstest:{i}",source="xstest",source_id=str(i),source_version="test",
                  intent_id=str(i),intent="safe",turns=[Turn(role="user",content="safe")],
                  is_benign=True,harm_domain=None,attack_family="direct",needs_review=[],license="CC-BY-4.0")
             for i in range(250)]
    result=family_evaluation_sets(safe+utility)
    assert result.harmful==[] and result.over_refusal==safe
    assert len(result.fpr_calibration)==250
    assert result.sampling_counts=={"xstest":{"requested":300,"available":250,"selected":250}}
    assert family_evaluation_sets(list(reversed(utility))).fpr_calibration==result.fpr_calibration
    assert len(family_evaluation_sets(utility,benign_per_source=12).fpr_calibration)==12
    with pytest.raises(ValueError): family_evaluation_sets(utility,benign_per_source=-1)


def test_only_recorded_taxonomy_approvals_are_cleared():
    for method in taxonomy.load()["attack_crosswalk"]["safedialbench"]:
        assert not taxonomy.attack_family("safedialbench",method).needs_review
        assert taxonomy.strategy_tag("safedialbench",method).needs_review == (method != "Purpose Reverse")


def test_funded_generation_remains_disabled_and_pilot_model_is_limited():
    config=yaml.safe_load(Path("configs/experiment.yaml").read_text(encoding="utf-8"))
    assert config["pilot"]["funding_confirmed"] is False
    assert config["pilot"]["budget_usd"]==50
    assert config["pilot"]["model"]=="meta-llama/llama-3.1-8b-instruct"
    slugs=[s for group in config["models"].values() for s in group]
    assert "nvidia/nemotron-3-super-120b-a12b" in slugs and "qwen/qwen3-14b" in slugs
    assert not any("distill" in s or "ultra" in s for s in slugs)


def test_ai_comparison_does_not_count_held_as_verdict_or_approve(data_case,tmp_path):
    _,raw,root,_,_=data_case("safedialbench")
    ws=tmp_path/"blind.csv"; export_worksheet("safedialbench",raw,ws,root,blind=True)
    with ws.open(newline="") as stream:
        reader=csv.DictReader(stream); fields=reader.fieldnames; rows=list(reader)
    drafts=[]
    for i,row in enumerate(rows):
        row.update(verdict="benign",intent="protective",reason="protection",reviewer="example AI")
        drafts.append({"source_id":row["source_id"],"source_sha256":sha256_file(raw),
                       "verdict":"benign" if i==0 else None,"harm_domain":None,"intent":"protective",
                       "reason":"protection","drafted_by":"earlier AI","reviewed":False,"reviewer":None})
    with ws.open("w",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    first=tmp_path/"frozen.jsonl";first.write_text("".join(json.dumps(r)+"\n" for r in drafts))
    before=first.read_bytes()
    result=compare_ai_drafts(first,ws,raw)
    assert result["sampled"]==2 and result["verdict"]["n"]==1
    assert result["verdict"]["kappa"] is None and result["human_agreement_pending"]
    assert result["first_held_ids"]==[rows[1]["source_id"]]
    assert first.read_bytes()==before and not (root/"safedialbench.jsonl").exists()
