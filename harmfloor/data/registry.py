"""Loader registry: one module per benchmark, registered here.

A loader reads the raw files under data/raw/<source>/ (fetched by scripts/fetch_data.py) and
returns the items that may enter evaluation plus the ones held back, each with a reason. It must:
  - set item_id = f"{source}:{source_id}" and record source_version (revision or sha256);
  - keep every native label verbatim in native_labels;
  - map labels with harmfloor.taxonomy (never hard-code a family or domain in the loader);
  - take harmful / benign / domain from harmfloor.data.annotations where the source's own labels
    do not fit, holding anything unreviewed;
  - set intent_id = item_id; cross-benchmark dedupe assigns the shared clusters later.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from harmfloor.schema import Item

RAW_ROOT = Path(__file__).resolve().parents[2] / "data" / "raw"


@dataclass(frozen=True)
class Held:
    source_id: str
    reason: str


@dataclass
class LoadResult:
    items: list[Item] = field(default_factory=list)
    held: list[Held] = field(default_factory=list)


Loader = Callable[[Path], LoadResult]
LOADERS: dict[str, Loader] = {}


def register(source: str) -> Callable[[Loader], Loader]:
    def deco(fn: Loader) -> Loader:
        if source in LOADERS:
            raise ValueError(f"duplicate loader for {source}")
        LOADERS[source] = fn
        return fn

    return deco


def load(source: str, raw_root: Path = RAW_ROOT) -> LoadResult:
    from harmfloor.data import jbb, safedialbench, utility  # noqa: F401  (registers the loaders)

    if source not in LOADERS:
        raise KeyError(f"no loader registered for {source!r}")
    return LOADERS[source](raw_root / source)
