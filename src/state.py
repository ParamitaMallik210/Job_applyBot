"""Persist the set of job IDs we've already notified about.

The file is committed back to the repo by GitHub Actions so dedup survives
between runs.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

log = logging.getLogger(__name__)

_DEFAULT_PATH = "state.json"
_MAX_IDS = 5000  # cap to keep the file small; older IDs are unlikely to recur


def load(path: str = _DEFAULT_PATH) -> set[str]:
    p = Path(path)
    if not p.exists():
        return set()
    try:
        data = json.loads(p.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("Failed to read state file %s: %s — starting fresh", path, exc)
        return set()
    return set(data.get("seen_ids", []))


def save(seen_ids: set[str], path: str = _DEFAULT_PATH) -> None:
    trimmed = list(seen_ids)[-_MAX_IDS:]
    Path(path).write_text(json.dumps({"seen_ids": trimmed}, indent=2))
