"""Indeed (in.indeed.com) search scraper.

Indeed embeds a JSON blob `window.mosaic.providerData['mosaic-provider-jobcards']`
inside each search results HTML page. We extract that rather than parsing cards
out of the DOM — far less brittle.

Anti-bot: Indeed sometimes Cloudflare-challenges GitHub Actions IPs. When it
does, we silently bail on the failed query; other sources still run.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Iterable

import requests

log = logging.getLogger(__name__)

_BASE = "https://in.indeed.com/jobs"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}

_JSON_RE = re.compile(
    r'window\.mosaic\.providerData\["mosaic-provider-jobcards"\]\s*=\s*(\{.*?\});',
    re.DOTALL,
)


def _normalize(raw: dict) -> dict | None:
    job_key = raw.get("jobkey")
    title = raw.get("title")
    if not job_key or not title:
        return None
    company = raw.get("company", "")
    salary_obj = raw.get("salarySnippet") or {}
    salary = salary_obj.get("text") or ""
    location = (raw.get("formattedLocation") or "").strip()
    snippet = (raw.get("snippet") or "").replace("<b>", "").replace("</b>", "")
    return {
        "id": f"indeed:{job_key}",
        "source": "indeed",
        "title": title,
        "company": company,
        "location": location,
        "experience": "",
        "salary": salary,
        "description": snippet,
        "tags": "",
        "url": f"https://in.indeed.com/viewjob?jk={job_key}",
        "posted": raw.get("formattedRelativeTime", ""),
    }


def fetch(
    keywords: list[str],
    locations: list[str],
    pages: int = 2,
    delay_sec: float = 2.0,
) -> Iterable[dict]:
    seen_ids: set[str] = set()
    session = requests.Session()
    session.headers.update(_HEADERS)

    for keyword in keywords:
        for location in locations:
            for page in range(pages):
                params = {
                    "q": keyword,
                    "l": location,
                    "fromage": "14",  # last 14 days
                    "start": page * 10,
                }
                try:
                    resp = session.get(_BASE, params=params, timeout=20)
                except requests.RequestException as exc:
                    log.warning("Indeed fetch failed for %s/%s p%d: %s", keyword, location, page, exc)
                    break

                if resp.status_code != 200 or "cf-chl-bypass" in resp.text.lower():
                    log.info("Indeed returned %s for %s/%s p%d — likely Cloudflare", resp.status_code, keyword, location, page)
                    break

                match = _JSON_RE.search(resp.text)
                if not match:
                    log.info("Indeed: no embedded JSON for %s/%s p%d", keyword, location, page)
                    break

                try:
                    payload = json.loads(match.group(1))
                except json.JSONDecodeError:
                    break

                results = (
                    payload.get("metaData", {})
                    .get("mosaicProviderJobCardsModel", {})
                    .get("results", [])
                )
                if not results:
                    break

                for raw in results:
                    job = _normalize(raw)
                    if not job or job["id"] in seen_ids:
                        continue
                    seen_ids.add(job["id"])
                    yield job

                time.sleep(delay_sec)
