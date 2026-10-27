"""Export/import source-bound worksheets and compare independent reviews before reconciliation."""
import argparse
import json
from pathlib import Path
from harmfloor.data import review
from harmfloor.data.annotations import ANNOTATIONS_DIR, sha256_file
from harmfloor.data.registry import RAW_ROOT
from harmfloor.data.sources import contexts, read_safedial

RAW = {"jbb_behaviors": RAW_ROOT / "jbb_behaviors" / "harmful-behaviors.csv",
       "safedialbench": RAW_ROOT / "safedialbench" / "datasets_en.jsonl"}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("command", choices=["export", "import", "blind", "kappa"])
    p.add_argument("source", choices=RAW)
    p.add_argument("n", nargs="?", type=int, default=50)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--worksheet", type=Path)
    p.add_argument("--include-manifest", type=Path,
                   help="For blind samples: retain every ID from an earlier source-bound manifest")
    p.add_argument("--by-method", action="store_true",
                   help="Stratify SafeDialBench blind selection by method only (D8 pilot)")
    p.add_argument("--first-labels", type=Path,
                   help="Frozen first-reviewer JSONL snapshot for agreement")
    args = p.parse_args()
    raw = RAW[args.source]
    if (args.include_manifest or args.by_method) and args.command != "blind":
        p.error("--include-manifest and --by-method apply only to blind sampling")
    if args.by_method and args.source != "safedialbench":
        p.error("--by-method applies only to SafeDialBench")
    blind = args.command in {"blind", "kappa"}
    ws = args.worksheet or ANNOTATIONS_DIR / "worksheets" / f"{args.source}{'.blind' if blind else ''}.csv"
    if args.command in {"export", "blind"}:
        ctx, strata = contexts(args.source, raw)
        if args.by_method:
            strata = {}
            for row in read_safedial(raw):
                strata.setdefault(row["method"], []).append(str(row["id"]))
        required = []
        if args.include_manifest:
            from harmfloor.data._utils import read_json
            previous = read_json(args.include_manifest.read_text(encoding="utf-8"))
            if previous.get("source") != args.source or previous.get("source_sha256") != sha256_file(raw):
                raise ValueError("required IDs manifest belongs to a different source snapshot")
            required = previous["ids"]
        ids = review.blind_sample(strata, args.n, args.seed, required_ids=required) if blind else None
        sampling = {"seed": args.seed, "strata": strata, "required_ids": required,
                    "include_manifest_sha256": sha256_file(args.include_manifest) if args.include_manifest else None} if blind else None
        count = review.export_worksheet(args.source, raw, ws, ids=ids, blind=blind, sampling=sampling)
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
