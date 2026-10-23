#!/usr/bin/env python3
"""Annotation review CLI (see harmfloor/data/review.py).

    uv run python scripts/review.py export  jbb_behaviors     # worksheet with drafts, for the first reviewer
    uv run python scripts/review.py import  jbb_behaviors     # reviewed worksheet rows -> data/annotations/
    uv run python scripts/review.py blind   safedialbench 50  # blind sample for the second annotator
    uv run python scripts/review.py kappa   safedialbench     # agreement, before any reconciliation
"""

import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

from harmfloor.data import review
from harmfloor.data.annotations import ANNOTATIONS_DIR, load_annotations, sha256_file
from harmfloor.data.registry import RAW_ROOT

RAW = {"jbb_behaviors": RAW_ROOT / "jbb_behaviors" / "harmful-behaviors.csv",
       "safedialbench": RAW_ROOT / "safedialbench" / "datasets_en.jsonl"}
WS = ANNOTATIONS_DIR / "worksheets"


def rows(source):
    """(source_id, stratum, context) per item. Context = what the reviewer needs to judge it."""
    if source == "jbb_behaviors":
        with RAW[source].open(encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f):
                yield r["Index"], r["Category"], f"[{r['Category']}] {r['Goal']}"
    else:
        with RAW[source].open(encoding="utf-8") as f:
            for line in f:
                r = json.loads(line)
                turns = " || ".join(f"U{i + 1}: {t['user']}" for i, t in enumerate(r["history"]))
                yield str(r["id"]), r["method"], f"[{r['task']} / {r['method']}] {turns}"


def main(cmd, source, *args):
    if cmd == "export":
        ctx = {sid: c for sid, _, c in rows(source)}
        n = review.export_worksheet(source, ctx, WS / f"{source}.csv")
        print(f"wrote {n} rows to {WS / f'{source}.csv'}")
    elif cmd == "import":
        n, problems = review.import_worksheet(source, WS / f"{source}.csv", RAW[source])
        print(f"{n} reviewed annotations written; {len(problems)} rows skipped")
        for p in problems[:20]:
            print("  ", p)
    elif cmd == "blind":
        strata, ctx = defaultdict(list), {}
        for sid, stratum, c in rows(source):
            strata[stratum].append(sid)
            ctx[sid] = c
        ids = review.blind_sample(strata, int(args[0]) if args else 50)
        review.export_worksheet(source, ctx, WS / f"{source}.blind.csv", ids=ids, blind=True)
        print(f"wrote {len(ids)} blind rows to {WS / f'{source}.blind.csv'}")
    elif cmd == "kappa":
        first = load_annotations(source, sha256_file(RAW[source]))
        print(review.agreement(first, WS / f"{source}.blind.csv"))
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(*sys.argv[1:]) if len(sys.argv) >= 3 else sys.exit(__doc__)
