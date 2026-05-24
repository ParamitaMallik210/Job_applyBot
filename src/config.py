from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def load(path: str | Path = "config.yml") -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)
