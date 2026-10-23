"""Benchmark loaders. Each loader turns one source in configs/benchmarks.yaml into schema.Item records."""

from .registry import load
from .pool import evaluation_pool
from . import jbb_behaviors, safedialbench  # Register built-in loaders on package import.

__all__ = ["evaluation_pool", "load"]
