"""WhatsApp notifier using CallMeBot's free personal API.

CallMeBot is the cleanest free option for personal WhatsApp notifications:
no Twilio account, no WhatsApp Business application. You authorize the service
once by messaging their number, get an API key, and can then send messages to
your own phone via a simple HTTP GET.

Setup (one-time, ~3 minutes):
  1. Save +34 644 51 95 23 in your iPhone contacts as "CallMeBot".
  2. Open WhatsApp and send this exact text to that contact:
        I allow callmebot to send me messages
  3. Within minutes you'll get a reply with your API key.
  4. Add two GitHub secrets:
        WHATSAPP_PHONE   = your full number with country code, e.g. 916377849757
        WHATSAPP_API_KEY = the key CallMeBot sent you
"""

from __future__ import annotations

import logging
import os
import time
from urllib.parse import quote_plus

import requests

log = logging.getLogger(__name__)

_API = "https://api.callmebot.com/whatsapp.php"


def _format_job(job: dict, ats) -> str:
    """Plain-text job card for WhatsApp (no Markdown — CallMeBot strips it)."""
    lines = [
        f"🔔 {job['title']}",
        f"🏢 {job['company'] or 'Unknown'}",
    ]
    if job.get("location"):
        lines.append(f"📍 {job['location']}")
    if job.get("salary"):
        lines.append(f"💰 {job['salary']}")
    if job.get("experience"):
        lines.append(f"🎯 {job['experience']}")

    lines.append(f"📊 ATS Match: {ats.score}%")

    if ats.matched:
        lines.append(f"✅ Your matching skills: {', '.join(ats.matched[:8])}")

    if ats.missing_from_resume:
        lines.append(f"⚠️ Skills they want (you'd need to add): {', '.join(ats.missing_from_resume[:8])}")

    # Pull a few skill keywords directly from the JD/tags as the "what they want" list.
    tags = (job.get("tags") or "").strip()
    if tags:
        lines.append(f"🔧 Tech in JD: {tags[:200]}")

    if ats.suggestions:
        lines.append("💡 Resume tweaks:")
        for s in ats.suggestions:
            lines.append(f"  • {s}")

    desc = (job.get("description") or "").strip()
    if desc:
        snippet = desc[:250].rsplit(" ", 1)[0]
        lines.append(f"\n📄 {snippet}...")

    lines.append(f"\n🔗 Apply: {job['url']}")
    lines.append(f"🗂 Source: {job['source']}")
    return "\n".join(lines)


def send_message(text: str) -> bool:
    phone = os.environ.get("WHATSAPP_PHONE")
    api_key = os.environ.get("WHATSAPP_API_KEY")
    if not phone or not api_key:
        log.error("WHATSAPP_PHONE / WHATSAPP_API_KEY not set")
        return False

    try:
        resp = requests.get(
            _API,
            params={"phone": phone, "text": text, "apikey": api_key},
            timeout=30,
        )
    except requests.RequestException as exc:
        log.error("WhatsApp send failed: %s", exc)
        return False

    # CallMeBot returns 200 with a confirmation message on success; 209 or 4xx
    # bodies usually mean throttling or invalid key.
    body_lc = (resp.text or "").lower()
    if resp.status_code == 200 and ("message queued" in body_lc or "message sent" in body_lc):
        return True
    log.error("WhatsApp returned %s: %s", resp.status_code, resp.text[:200])
    return False


def send_digest(matches: list[tuple[dict, object]]) -> int:
    if not matches:
        send_message("🤖 Job bot ran — no new matches this cycle.")
        return 0

    sent = 0
    send_message(f"🤖 {len(matches)} new job match{'es' if len(matches) > 1 else ''} this cycle:")
    # CallMeBot enforces a ~7-second gap between messages to the same number.
    time.sleep(8)

    for job, ats in matches:
        body = _format_job(job, ats)
        if send_message(body):
            sent += 1
        time.sleep(8)
    return sent
