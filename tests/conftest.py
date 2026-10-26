import csv
import json
import pytest
from harmfloor.data.annotations import sha256_file


@pytest.fixture
def data_case(tmp_path):
    def build(source="jbb_behaviors"):
        raw = tmp_path / source; raw.mkdir(exist_ok=True)
        ann = tmp_path / "annotations"; ann.mkdir(exist_ok=True)
        if source == "jbb_behaviors":
            path = raw / "harmful-behaviors.csv"
            rows = [{"Index": str(i), "Goal": f"Synthetic request {i}", "Target": "not a prompt",
                     "Behavior": f"B{i}", "Category": "Privacy", "Source": "Original"} for i in (0, 1)]
            with path.open("w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=rows[0]); w.writeheader(); w.writerows(rows)
            ids = ["0", "1"]
        else:
            path = raw / "datasets_en.jsonl"
            rows = [{"id": i, "task": "Privacy", "method": "Scence Construct", "model_type": "ChatGPT",
                     "scene": "Daily Life", "history": [{"user": "First", "bot": "Earlier context"},
                       {"user": "Final", "bot": "FINAL BOT MUST NOT LEAK"}]} for i in (1, 2)]
            path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
            ids = ["1", "2"]
        def notes(**updates):
            records = [{"source_id": sid, "source_sha256": sha256_file(path), "verdict": "harmful",
                        "harm_domain": "privacy", "intent": None if source == "jbb_behaviors" else "Standalone intent",
                        "drafted_by": "human:test", "reviewed": True, "reviewer": "test", **updates} for sid in ids]
            (ann / f"{source}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
            return records
        return raw, path, ann, rows, notes
    return build
