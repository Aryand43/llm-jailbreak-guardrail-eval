import json
import pytest
from harmfloor.data.migration import migrate_drafts
from harmfloor.data.annotations import sha256_file
from harmfloor.data.review import read_drafts


def test_migration_is_one_to_one_and_preserves_uncertainty(data_case,tmp_path):
    _,raw,root,_,_=data_case()
    old=tmp_path/"old.json"
    entry={"disposition":"harmful","domain":"privacy","reviewed":False,"reason":"ambiguous"}
    old.write_text(json.dumps({"source_version":"sha256:"+sha256_file(raw),"items":{"B0":entry,"B1":entry}}))
    before=old.read_bytes()
    out=root/"drafts"/"jbb_behaviors.jsonl"
    report=migrate_drafts("jbb_behaviors",raw,old,out,drafted_by="legacy unknown",check_ids={"B0"})
    assert report["migrated"]==2 and report["approved"]==0
    drafts=read_drafts("jbb_behaviors",root)
    assert set(drafts)=={"0","1"} and drafts["0"]["note"].startswith("CHECK")
    assert drafts["0"]["legacy_entry"]==entry and old.read_bytes()==before
    assert all(d["reviewed"] is False for d in drafts.values())
    with pytest.raises(FileExistsError):migrate_drafts("jbb_behaviors",raw,old,out,drafted_by="legacy")


@pytest.mark.parametrize("change",["stale","unknown","reviewed"])
def test_bad_legacy_draft_cannot_be_migrated(data_case,tmp_path,change):
    _,raw,root,_,_=data_case()
    old=tmp_path/"old.json"
    data={"source_version":"sha256:"+sha256_file(raw),"items":{"B0":{"reviewed":False}}}
    if change=="stale":data["source_version"]="wrong"
    elif change=="unknown":data["items"]={"missing":{"reviewed":False}}
    else:data["items"]["B0"]["reviewed"]=True
    old.write_text(json.dumps(data))
    with pytest.raises(ValueError):migrate_drafts("jbb_behaviors",raw,old,root/"drafts.jsonl",drafted_by="legacy")
