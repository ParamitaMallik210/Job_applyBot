"""Telegram Bot API client.

Reads TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID from env. Sends one MarkdownV2
message per job (or batches into a digest if the run produced many matches).
"""

from __future__ import annotations

import logging
import os
import re
import time

import requests

log = logging.getLogger(__name__)

_API = "https://api.telegram.org/bot{token}/sendMessage"
_MD_RESERVED = r"_*[]()~`>#+-=|{}.!\\"


def _escape(text: str) -> str:
    return "".join("\\" + c if c in _MD_RESERVED else c for c in text or "")


def _format_job(job: dict, ats) -> str:
    parts = [
        f"🔔 *{_escape(job['title'])}*",
        f"🏢 {_escape(job['company'] or 'Unknown')}",
    ]
    if job.get("location"):
        parts.append(f"📍 {_escape(job['location'])}")
    if job.get("salary"):
        parts.append(f"💰 {_escape(job['salary'])}")
    if job.get("experience"):
        parts.append(f"🎯 {_escape(job['experience'])}")
    parts.append(f"📊 ATS Match: *{ats.score}%*")
    if ats.matched:
        parts.append(f"✅ Strong: {_escape(', '.join(ats.matched[:6]))}")
    if ats.missing_from_resume:
        parts.append(f"⚠️ JD wants \\(missing from your resume\\): {_escape(', '.join(ats.missing_from_resume[:6]))}")
    if ats.suggestions:
        parts.append("💡 *Resume tweaks:*")
        for s in ats.suggestions:
            parts.append(f"  • {_escape(s)}")
    desc = (job.get("description") or "").strip()
    if desc:
        snippet = desc[:280].rsplit(" ", 1)[0]
        parts.append(f"\n📄 _{_escape(snippet)}\\.\\.\\._")
    parts.append(f"\n🔗 [Open posting]({job['url']})")
    parts.append(f"🗂 Source: {_escape(job['source'])}")
    return "\n".join(parts)


def send_message(text: str) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        log.error("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set")
        return False

    try:
        resp = requests.post(
            _API.format(token=token),
            json={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "MarkdownV2",
                "disable_web_page_preview": True,
            },
            timeout=15,
        )
    except requests.RequestException as exc:
        log.error("Telegram send failed: %s", exc)
        return False

    if resp.status_code != 200:
        log.error("Telegram returned %s: %s", resp.status_code, resp.text)
        return False
    return True


def send_digest(matches: list[tuple[dict, object]]) -> int:
    """Send one Telegram message per match. Returns count of successful sends.

    Telegram's per-message limit is 4096 chars and per-chat rate limit is ~30/s,
    so we space sends out lightly.
    """
    if not matches:
        send_message(_escape("🤖 Job bot ran — no new matches this cycle."))
        return 0

    sent = 0
    header = _escape(f"🤖 {len(matches)} new match{'es' if len(matches) > 1 else ''} this cycle:")
    send_message(header)
    time.sleep(0.5)
    for job, ats in matches:
        body = _format_job(job, ats)
        if send_message(body):
            sent += 1
        time.sleep(0.4)
    return sent
