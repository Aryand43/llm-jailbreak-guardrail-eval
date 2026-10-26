"""Convert local legacy drafts to JSONL. Never approves labels or overwrites an existing draft."""
import argparse
import csv
from pathlib import Path
from harmfloor.data._utils import read_json
from harmfloor.data.migration import migrate_drafts


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source",choices=["jbb_behaviors","safedialbench"])
    parser.add_argument("raw",type=Path)
    parser.add_argument("legacy",type=Path)
    parser.add_argument("output",type=Path)
    parser.add_argument("--drafted-by",required=True)
    parser.add_argument("--pilot",type=Path,help="Legacy pilot JSON used only to select IDs")
    parser.add_argument("--checks",type=Path,help="Legacy JBB CSV with Behavior and needs_check columns")
    args=parser.parse_args()
    ids=list(read_json(args.pilot.read_text(encoding="utf-8-sig"))["items"]) if args.pilot else None
    checks=set()
    if args.checks:
        with args.checks.open(encoding="utf-8-sig",newline="") as stream:
            checks={r["Behavior"] for r in csv.DictReader(stream) if r["needs_check"].strip()}
    result=migrate_drafts(args.source,args.raw,args.legacy,args.output,drafted_by=args.drafted_by,
                          selected_ids=ids,check_ids=checks)
    print(f"Migrated {result['migrated']} drafts; approved 0; originals preserved")


if __name__=="__main__": main()
