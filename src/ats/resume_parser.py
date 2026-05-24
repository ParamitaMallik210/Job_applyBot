"""Extract plain text from the user's PDF resume."""

from __future__ import annotations

import logging
from pathlib import Path

from pypdf import PdfReader

log = logging.getLogger(__name__)


def load_resume_text(path: str) -> str:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"Resume not found at {path}. Drop your PDF there and commit it to the private repo."
        )
    reader = PdfReader(str(p))
    parts = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except Exception as exc:
            log.warning("PDF page extraction failed: %s", exc)
    return "\n".join(parts).strip()
