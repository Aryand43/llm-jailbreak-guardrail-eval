"""Small validation and provenance helpers for local dataset loaders."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from harmfloor.taxonomy import Mapping


def source_version(path: Path) -> str:
    with path.open("rb") as stream:
        return f"sha256:{hashlib.file_digest(stream, 'sha256').hexdigest()}"


def require_text(row: dict[str, Any], key: str, context: str) -> str:
    value = row.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{context}: {key!r} must be a nonempty string")
    return value


def review_flags(**mappings: Mapping) -> list[str]:
    """Item fields whose values come from taxonomy proposals still marked for review."""
    return [field for field, mapping in mappings.items() if mapping.needs_review]
