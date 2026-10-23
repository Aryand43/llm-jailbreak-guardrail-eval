"""Benign prompts for the false-positive-rate constraint (refusal threshold calibration).

These sources are built to be benign, so their own labels are used directly: no annotation gate.

  or_bench: SoK's 1,000-prompt OR-Bench sample, read from SoK's release so the IDs match theirs
            (all 1,000 are verbatim in or-bench-80k; it is not the hard-1k split).
  xstest:   the 250 safe prompts; the 200 unsafe contrast prompts are left out.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

from harmfloor import taxonomy
from harmfloor.data.annotations import sha256_file
from harmfloor.data.registry import LoadResult, register
from harmfloor.schema import Item, Turn


def _benign(source: str, sid: str, text: str, sha: str, labels: dict[str, str], license: str) -> Item:
    return Item(
        item_id=f"{source}:{sid}",
        source=source,
        source_id=sid,
        source_version=f"sha256:{sha}",
        intent_id=f"{source}:{sid}",
        intent=text,
        turns=[Turn(role="user", content=text)],
        is_benign=True,
        attack_family=taxonomy.attack_family(source, "").value,
        harm_domain=None,
        native_labels=labels,
        license=license,
    )


@register("or_bench")
def load_or_bench(raw_dir: Path) -> LoadResult:
    path = raw_dir / "OR-Bench.json"
    sha = sha256_file(path)
    rows = json.loads(path.read_text(encoding="utf-8"))
    return LoadResult(items=[
        _benign("or_bench", str(r["index"]), r["goal"], sha, {"category": r["category"]}, "CC-BY-4.0")
        for r in rows
    ])


@register("xstest")
def load_xstest(raw_dir: Path) -> LoadResult:
    path = raw_dir / "xstest_prompts.csv"
    sha = sha256_file(path)
    with path.open(encoding="utf-8", newline="") as f:
        rows = [r for r in csv.DictReader(f) if r["label"] == "safe"]
    return LoadResult(items=[
        _benign("xstest", r["id"], r["prompt"], sha, {"type": r["type"], "focus": r["focus"]}, "CC-BY-4.0")
        for r in rows
    ])
