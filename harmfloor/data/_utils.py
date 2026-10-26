"""Small validation and provenance helpers for local dataset loaders."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
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


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def read_json(text: str) -> Any:
    return json.loads(text, object_pairs_hook=unique_object)


def atomic_write(path: Path, text: str) -> None:
    """Replace a complete UTF-8 snapshot, including an intentionally empty snapshot."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                     dir=path.parent, delete=False) as stream:
        temp = Path(stream.name)
        try:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        except BaseException:
            stream.close()
            temp.unlink(missing_ok=True)
            raise
    try:
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)
