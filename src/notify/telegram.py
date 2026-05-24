"""Telegram Bot API client with inline-button job cards.

Each match is sent as a compact one-line message with two inline buttons:
  • 🚀 Apply  → opens the job page in your browser (you tap Apply there)
  • 📋 Details → opens the same page in Telegram's in-app web preview

Auto-submission is intentionally not supported — Naukri/LinkedIn ban auto-apply.
"""

from __future__ import annotations

import json
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


def _short_role(title: str) -> str:
    """Trim long titles for the compact card."""
    if not title:
        return ""
    cleaned = re.sub(r"\s*\([^)]*\)\s*", " ", title).strip()
    return cleaned[:55] + "…" if len(cleaned) > 55 else cleaned


def _format_card(job: dict, ats) -> tuple[str, dict]:
    """Build the compact message text + inline-button keyboard for one job."""
    company = _escape(job.get("company") or "Unknown")
    role = _escape(_short_role(job.get("title") or ""))
    score = ats.score
    loc = _escape(job.get("location") or "")
    salary = _escape(job.get("salary") or "")

    line1 = f"🏢 *{company}* · 💼 {role}"
    line2_bits = [f"📊 {score}% match"]
    if salary:
        line2_bits.append(f"💰 {salary}")
    if loc:
        line2_bits.append(f"📍 {loc}")
    text = line1 + "\n" + " · ".join(line2_bits)

    if ats.matched:
        text += f"\n✅ {_escape(', '.join(ats.matched[:5]))}"
    if ats.missing_from_resume:
        text += f"\n⚠️ Missing: {_escape(', '.join(ats.missing_from_resume[:5]))}"

    keyboard = {
        "inline_keyboard": [
            [
                {"text": "🚀 Apply", "url": job["url"]},
                {"text": "📋 Details", "url": job["url"]},
            ]
        ]
    }
    return text, keyboard


def send_message(text: str, reply_markup: dict | None = None) -> bool:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        log.error("TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set")
        return False

    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "MarkdownV2",
        "disable_web_page_preview": True,
    }
    if reply_markup is not None:
        payload["reply_markup"] = json.dumps(reply_markup)

    try:
        resp = requests.post(_API.format(token=token), data=payload, timeout=15)
    except requests.RequestException as exc:
        log.error("Telegram send failed: %s", exc)
        return False

    if resp.status_code != 200:
        log.error("Telegram returned %s: %s", resp.status_code, resp.text)
        return False
    return True


def send_digest(matches: list[tuple[dict, object]]) -> int:
    if not matches:
        send_message(_escape("🤖 Job bot ran — no new matches this cycle."))
        return 0

    n = len(matches)
    header = _escape(f"🤖 {n} new match{'es' if n > 1 else ''} — tap Apply to open the listing:")
    send_message(header)
    time.sleep(0.4)

    sent = 0
    for job, ats in matches:
        text, keyboard = _format_card(job, ats)
        if send_message(text, reply_markup=keyboard):
            sent += 1
        time.sleep(0.4)
    return sent
