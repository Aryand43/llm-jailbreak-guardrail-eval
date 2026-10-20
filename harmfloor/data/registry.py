"""Loader registry. Aniket: add one module per benchmark and register it here (docs/TASKS.md A2).

A loader reads the raw files that A1 recorded under data/raw/<source>/ and yields Items. It must:
  - set item_id = f"{source}:{source_id}" and record source_version (revision or sha256);
  - keep every native label verbatim in native_labels;
  - map labels with harmfloor.taxonomy (never hard-code a family or domain in the loader);
  - leave intent_id empty-equal to item_id; cross-benchmark dedupe assigns the shared clusters.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

from harmfloor.schema import Item

Loader = Callable[[Path], Iterator[Item]]
LOADERS: dict[str, Loader] = {}


def register(source: str) -> Callable[[Loader], Loader]:
    def deco(fn: Loader) -> Loader:
        if source in LOADERS:
            raise ValueError(f"duplicate loader for {source}")
        LOADERS[source] = fn
        return fn

    return deco


def load(source: str, raw_root: Path = Path("data/raw")) -> Iterator[Item]:
    if source not in LOADERS:
        raise KeyError(f"no loader registered for {source!r}")
    yield from LOADERS[source](raw_root / source)
