"""Instahyre tech-jobs search.

Instahyre exposes a public JSON search endpoint that doesn't require login for
basic listing data (full apply requires auth). Good signal for mid-senior
Indian tech roles with disclosed compensation.
"""

from __future__ import annotations

import logging
import time
from typing import Iterable

import requests

log = logging.getLogger(__name__)

_BASE = "https://www.instahyre.com/api/v1/job_search/"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.instahyre.com/",
}


def _normalize(raw: dict) -> dict | None:
    job_id = raw.get("id")
    title = raw.get("title")
    if not job_id or not title:
        return None
    employer = raw.get("employer") or {}
    company = employer.get("company_name", "")
    locations = raw.get("locations") or []
    location = ", ".join(loc.get("city", "") for loc in locations if isinstance(loc, dict)) if locations else ""
    salary = ""
    if raw.get("min_ctc") or raw.get("max_ctc"):
        salary = f"{raw.get('min_ctc', '')}-{raw.get('max_ctc', '')} LPA"
    skills = ", ".join(s.get("name", "") for s in (raw.get("skills") or []) if isinstance(s, dict))

    return {
        "id": f"instahyre:{job_id}",
        "source": "instahyre",
        "title": title,
        "company": company,
        "location": location,
        "experience": f"{raw.get('min_year', '')}-{raw.get('max_year', '')} yrs",
        "salary": salary,
        "description": raw.get("description", "") or raw.get("overview", "") or "",
        "tags": skills,
        "url": f"https://www.instahyre.com/job/{job_id}/",
        "posted": raw.get("created_on", ""),
    }


def fetch(
    keywords: list[str],
    locations: list[str],
    pages: int = 2,
    delay_sec: float = 1.5,
) -> Iterable[dict]:
    seen_ids: set[str] = set()
    session = requests.Session()
    session.headers.update(_HEADERS)

    for keyword in keywords:
        for location in locations:
            for page in range(pages):
                params = {
                    "q": keyword,
                    "city": location,
                    "fp_first_publish_dt": "1209600",  # last 14 days, seconds
                    "offset": page * 20,
                    "limit": "20",
                }
                try:
                    resp = session.get(_BASE, params=params, timeout=20)
                except requests.RequestException as exc:
                    log.warning("Instahyre fetch failed for %s/%s p%d: %s", keyword, location, page, exc)
                    break

                if resp.status_code != 200:
                    log.info("Instahyre returned %s for %s/%s p%d", resp.status_code, keyword, location, page)
                    break

                try:
                    data = resp.json()
                except ValueError:
                    break

                jobs = data.get("objects") or data.get("results") or []
                if not jobs:
                    break

                for raw in jobs:
                    job = _normalize(raw)
                    if not job or job["id"] in seen_ids:
                        continue
                    seen_ids.add(job["id"])
                    yield job

                time.sleep(delay_sec)
