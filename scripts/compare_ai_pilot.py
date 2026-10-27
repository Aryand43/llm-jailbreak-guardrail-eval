"""Compare a frozen SafeDialBench AI draft with a returned blind AI worksheet.

Never imports labels or declares human agreement. Freeze the first file before opening
the second worksheet; the worksheet must have its original source-bound manifest.
"""
import argparse
import json
from pathlib import Path
from harmfloor.data.pilot import compare_ai_drafts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("first_drafts", type=Path)
    parser.add_argument("returned_worksheet", type=Path)
    parser.add_argument("--raw", type=Path, default=Path("data/raw/safedialbench/datasets_en.jsonl"))
    args = parser.parse_args()
    print(json.dumps(compare_ai_drafts(args.first_drafts, args.returned_worksheet, args.raw), indent=2))


if __name__ == "__main__":
    main()
