"""Export/import source-bound worksheets and compare independent reviews before reconciliation."""
import argparse
import json
from pathlib import Path
from harmfloor.data import review
from harmfloor.data.annotations import ANNOTATIONS_DIR, sha256_file
from harmfloor.data.registry import RAW_ROOT
from harmfloor.data.sources import contexts

RAW = {"jbb_behaviors": RAW_ROOT / "jbb_behaviors" / "harmful-behaviors.csv",
       "safedialbench": RAW_ROOT / "safedialbench" / "datasets_en.jsonl"}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["export", "import", "blind", "kappa"])
    p.add_argument("source", choices=RAW)
    p.add_argument("n", nargs="?", type=int, default=50)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--worksheet", type=Path)
    p.add_argument("--first-labels", type=Path,
                   help="Frozen first-reviewer JSONL snapshot for agreement")
    args = p.parse_args()
    raw = RAW[args.source]
    blind = args.command in {"blind", "kappa"}
    ws = args.worksheet or ANNOTATIONS_DIR / "worksheets" / f"{args.source}{'.blind' if blind else ''}.csv"
    if args.command in {"export", "blind"}:
        ctx, strata = contexts(args.source, raw)
        ids = review.blind_sample(strata, args.n, args.seed) if blind else None
        count = review.export_worksheet(args.source, raw, ws, ids=ids, blind=blind)
        meta_path = review.manifest_path(ws)
        meta = json.loads(meta_path.read_text())
        meta.update(seed=args.seed if blind else None, strata=strata if blind else None)
        review.atomic_write(meta_path, json.dumps(meta, indent=2) + "\n")
        print(f"Exported {count} rows: {ws}")
    elif args.command == "import":
        count, problems = review.import_worksheet(args.source, ws, raw)
        if problems:
            for problem in problems:
                print(problem)
            raise SystemExit("Import aborted; prior reviewed file unchanged")
        print(f"Replaced reviewed snapshot with {count} decisions; blank verdicts are held")
    else:
        if args.first_labels is None:
            p.error("kappa requires --first-labels pointing to a frozen pre-reconciliation JSONL file")
        # Read the specified snapshot directly, retaining strict annotation parsing.
        from harmfloor.data.annotations import Annotation
        from harmfloor.data._utils import read_json
        first = {}
        for line in args.first_labels.read_text(encoding="utf-8-sig").splitlines():
            if line.strip():
                a = Annotation.model_validate(read_json(line))
                if a.source_id in first:
                    raise ValueError("duplicate first-review annotation ID")
                first[a.source_id] = a
        result = review.agreement(first, ws, source=args.source, raw_file=raw)
        result["first_snapshot_sha256"] = sha256_file(args.first_labels)
        result["second_worksheet_sha256"] = sha256_file(ws)
        print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
