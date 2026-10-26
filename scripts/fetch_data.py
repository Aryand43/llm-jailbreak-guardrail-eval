#!/usr/bin/env python3
"""Download raw benchmark files into data/raw/<source>/ from pinned revisions and verify sha256.

    uv run python scripts/fetch_data.py            # all sources below
    uv run python scripts/fetch_data.py safedialbench

A checksum mismatch aborts: annotations are tied to the exact file they were made against.
"""

import hashlib
import sys
import urllib.request
from pathlib import Path

RAW = Path(__file__).resolve().parents[1] / "data" / "raw"

FILES = {
    "jbb_behaviors": [(
        "harmful-behaviors.csv",
        "https://huggingface.co/datasets/JailbreakBench/JBB-Behaviors/resolve/"
        "886acc352a31533ffbcf4ef22c744658688086fc/data/harmful-behaviors.csv",
        "4a8ec6832056b631eb092dccc60d37a61c3d441268268888b3d006288afeffa1",
    )],
    "safedialbench": [(  # Hugging Face release (Apache-2.0); byte-identical to the GitHub copy
        "datasets_en.jsonl",
        "https://huggingface.co/datasets/HongyeCao/SafeDialBench/resolve/"
        "0d27436754b80c28d40c3748ede8e498405a63a8/datasets_en.jsonl",
        "a5429b6477ab7d3f6e47da55e0a9c889bbbba7575dd2ba7e1672379a412bc988",
    )],
    "or_bench": [(  # SoK's 1,000-prompt sample (all verbatim in or-bench-80k)
        "OR-Bench.json",
        "https://huggingface.co/datasets/xunguangwang/JailbreakGuardrailBenchmark/resolve/"
        "be32a36e0e5a34dd17ba2eda7cd54dd74dd5f25a/OR-Bench/OR-Bench.json",
        "58baab47242a1e6ee7a577525e5b8526c489a2fa9e258739e64709f1c99f2025",
    )],
    "xstest": [(
        "xstest_prompts.csv",
        "https://raw.githubusercontent.com/paul-rottger/xstest/"
        "d7bb5bd738c1fcbc36edd83d5e7d1b71a3e2d84d/xstest_prompts.csv",
        "11783fb294ed017473ee53c207d71f2161c7672c8d0b037501e78387f801cb5a",
    )],
}


def fetch(source: str) -> None:
    for name, url, sha in FILES[source]:
        dest = RAW / source / name
        if dest.exists() and hashlib.sha256(dest.read_bytes()).hexdigest() == sha:
            print(f"ok      {source}/{name}")
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        data = urllib.request.urlopen(url, timeout=120).read()
        got = hashlib.sha256(data).hexdigest()
        if got != sha:
            sys.exit(f"sha256 mismatch for {source}/{name}: expected {sha}, got {got}")
        dest.write_bytes(data)
        print(f"fetched {source}/{name}")


if __name__ == "__main__":
    for source in sys.argv[1:] or FILES:
        fetch(source)
