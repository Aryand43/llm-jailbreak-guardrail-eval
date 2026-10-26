"""Migrate old local draft sidecars without changing or approving the original labels."""
from pathlib import Path
import json
from ._utils import read_json, atomic_write
from .annotations import sha256_file
from .sources import source_rows, source_id


def migrate_drafts(source: str, raw_file: Path, legacy_file: Path, output: Path, *,
                   drafted_by: str, selected_ids: list[str] | None = None,
                   check_ids: set[str] | None = None) -> dict:
    if output.exists():
        raise FileExistsError(f"{output}: preserve existing draft edits; choose a new output")
    if not drafted_by.strip():
        raise ValueError("record the known drafting provenance, or explicitly state it is unknown")
    sha = sha256_file(raw_file)
    payload = read_json(legacy_file.read_text(encoding="utf-8-sig"))
    if payload.get("source_version") != f"sha256:{sha}":
        raise ValueError("legacy draft belongs to a different source snapshot")
    entries = payload.get("items")
    if not isinstance(entries, dict):
        raise ValueError("legacy file needs an items object")
    rows = source_rows(source, raw_file)
    mapping = {(r["Behavior"] if source == "jbb_behaviors" else str(r["id"])): source_id(source,r) for r in rows}
    if len(mapping) != len(rows) or len(set(mapping.values())) != len(rows):
        raise ValueError("source ID migration must be one-to-one")
    if entries.keys() - mapping.keys():
        raise ValueError("legacy draft contains unknown source IDs")
    selected = list(entries) if selected_ids is None else selected_ids
    if len(set(selected)) != len(selected) or set(selected) - entries.keys():
        raise ValueError("invalid migration selection")
    out, ledger = [], []
    legacy_sha = sha256_file(legacy_file)
    for old_id in selected:
        entry = entries[old_id]
        if not isinstance(entry, dict) or entry.get("reviewed") is not False:
            raise ValueError(f"{old_id}: migration accepts only explicitly unreviewed drafts")
        sid = mapping[old_id]
        verdict = entry.get("disposition") or None
        note = entry.get("note") or ""
        if check_ids and old_id in check_ids:
            note = "CHECK: " + note
        if "harm_label" in entry:
            note += " Legacy detailed label retained for review; no automatic domain conversion."
        record = {"source_id": sid, "source_sha256": sha, "verdict": verdict,
                  "harm_domain": entry.get("domain"), "intent": entry.get("intent") or None,
                  "reason": entry.get("reason") or entry.get("exclude_reason"),
                  "note": note.strip(), "drafted_by": drafted_by, "reviewed": False,
                  "reviewer": None, "legacy_source_id": old_id, "legacy_entry": entry,
                  "legacy_file_sha256": legacy_sha}
        out.append(record)
        ledger.append({"old_id":old_id,"new_id":sid,"reviewed":False})
    report = {"source":source,"source_sha256":sha,"legacy_file_sha256":legacy_sha,
              "legacy_entries":len(entries),"selected":len(selected),"migrated":len(out),
              "unselected":len(entries)-len(selected),"approved":0,"id_mapping":ledger,
              "protocol":"Pending Aryan approval; legacy label choices preserved, not endorsed"}
    atomic_write(output, "".join(json.dumps(r,ensure_ascii=False)+"\n" for r in out))
    atomic_write(output.with_suffix(".migration.json"), json.dumps(report,indent=2)+"\n")
    return report
