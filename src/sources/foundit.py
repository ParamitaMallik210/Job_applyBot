"""Foundit (formerly Monster India) job search.

Foundit's frontend talks to a JSON middleware endpoint. The schema is similar
to Naukri's but flatter.
"""

from __future__ import annotations

import logging
import time
from typing import Iterable

import requests

log = logging.getLogger(__name__)

_BASE = "https://www.foundit.in/middleware/jobsearch"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": "https://www.foundit.in/",
    "Origin": "https://www.foundit.in",
}


def _normalize(raw: dict) -> dict | None:
    job_id = raw.get("jobId") or raw.get("id")
    title = raw.get("title") or raw.get("jobTitle")
    if not job_id or not title:
        return None

    company = raw.get("companyName") or (raw.get("company") or {}).get("name", "")
    location = ", ".join(raw.get("locations") or []) if isinstance(raw.get("locations"), list) else raw.get("location", "")
    exp = raw.get("experience") or ""
    if isinstance(exp, dict):
        exp = f"{exp.get('min', '')}-{exp.get('max', '')} yrs"
    salary = raw.get("salary") or ""
    if isinstance(salary, dict):
        salary = f"{salary.get('min', '')}-{salary.get('max', '')} {salary.get('currency', '')}"

    url = raw.get("seoJobDetailUrl") or raw.get("url") or f"https://www.foundit.in/job/{job_id}"
    if not url.startswith("http"):
        url = f"https://www.foundit.in{url}"

    return {
        "id": f"foundit:{job_id}",
        "source": "foundit",
        "title": title,
        "company": company,
        "location": location,
        "experience": str(exp),
        "salary": str(salary),
        "description": raw.get("description", "") or raw.get("jobDescription", "") or "",
        "tags": ", ".join(raw.get("skills") or []) if isinstance(raw.get("skills"), list) else "",
        "url": url,
        "posted": raw.get("postedDate", ""),
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
                    "query": keyword,
                    "locations": location.lower(),
                    "limit": "20",
                    "start": page * 20,
                    "sort": "1",
                }
                try:
                    resp = session.get(_BASE, params=params, timeout=20)
                except requests.RequestException as exc:
                    log.warning("Foundit fetch failed for %s/%s p%d: %s", keyword, location, page, exc)
                    break

                if resp.status_code != 200:
                    log.info("Foundit returned %s for %s/%s p%d", resp.status_code, keyword, location, page)
                    break

                try:
                    data = resp.json()
                except ValueError:
                    log.info("Foundit: non-JSON response")
                    break

                jobs = data.get("jobSearchResponse", {}).get("data") or data.get("jobs") or data.get("data") or []
                if not jobs:
                    break

                for raw in jobs:
                    job = _normalize(raw)
                    if not job or job["id"] in seen_ids:
                        continue
                    seen_ids.add(job["id"])
                    yield job

                time.sleep(delay_sec)
