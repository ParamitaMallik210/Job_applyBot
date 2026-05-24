"""Notification dispatcher.

Reads the configured channel (whatsapp / telegram / both) and routes each
digest through the matching backend. New backends just need send_digest().
"""

from __future__ import annotations

import logging

from . import telegram, whatsapp

log = logging.getLogger(__name__)


def send_digest(matches: list[tuple[dict, object]], channel: str = "whatsapp") -> int:
    channel = (channel or "whatsapp").lower()
    sent = 0
    if channel in ("whatsapp", "both"):
        sent += whatsapp.send_digest(matches)
    if channel in ("telegram", "both"):
        sent += telegram.send_digest(matches)
    if channel not in ("whatsapp", "telegram", "both"):
        log.error("Unknown notify channel %r — falling back to whatsapp", channel)
        sent += whatsapp.send_digest(matches)
    return sent


__all__ = ["send_digest"]
