"""Fetch postings from Naukri's public search API.

Naukri's frontend talks to a JSON endpoint that returns structured listings.
We use that directly instead of HTML scraping — cleaner data, less to break.

The required headers (appid/systemid) are fixtures Naukri's web client always
sends. If they ever rotate, this module is the one place to patch.
"""

from __future__ import annotations

import logging
import time
from typing import Iterable

import requests

log = logging.getLogger(__name__)

_BASE_URL = "https://www.naukri.com/jobapi/v3/search"

# Naukri returns 406 for "incomplete" client fingerprints. The sec-ch-ua,
# sec-fetch-*, clientid, and gid headers below are what their web client sends —
# omitting any one of them frequently trips their bot detection.
_HEADERS = {
    "appid": "109",
    "systemid": "Naukri",
    "clientid": "d3skt0p",
    "gid": "LOCATION,INDUSTRY,EDUCATION,FAREA_ROLE",
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Referer": "https://www.naukri.com/",
    "Origin": "https://www.naukri.com",
    "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
}


def _build_query(keyword: str, location: str, experience: int, page: int) -> dict:
    return {
        "noOfResults": "20",
        "urlType": "search_by_key_loc",
        "searchType": "adv",
        "keyword": keyword,
        "location": location,
        "experience": str(experience),
        "pageNo": str(page),
        "k": keyword,
        "l": location,
        "seoKey": f"{keyword.lower().replace(' ', '-')}-jobs-in-{location.lower()}",
        "src": "jobsearchDesk",
        "latLong": "",
    }


def _normalize(raw: dict) -> dict | None:
    job_id = raw.get("jobId") or raw.get("jobIdEncrypted")
    title = raw.get("title")
    if not job_id or not title:
        return None

    placeholders = raw.get("placeholders") or []
    exp = next((p["label"] for p in placeholders if p.get("type") == "experience"), "")
    salary = next((p["label"] for p in placeholders if p.get("type") == "salary"), "")
    location = next((p["label"] for p in placeholders if p.get("type") == "location"), "")

    return {
        "id": f"naukri:{job_id}",
        "source": "naukri",
        "title": title,
        "company": raw.get("companyName", ""),
        "location": location,
        "experience": exp,
        "salary": salary,
        "description": raw.get("jobDescription", "") or "",
        "tags": raw.get("tagsAndSkills", "") or "",
        "url": (
            f"https://www.naukri.com{raw.get('jdURL')}"
            if raw.get("jdURL")
            else f"https://www.naukri.com/job-listings-{job_id}"
        ),
        "posted": raw.get("footerPlaceholderLabel", ""),
    }


def fetch(
    keywords: list[str],
    locations: list[str],
    experience: int,
    pages: int = 3,
    delay_sec: float = 1.5,
) -> Iterable[dict]:
    """Yield deduped normalized job dicts across the keyword × location matrix."""
    seen_ids: set[str] = set()
    session = requests.Session()
    session.headers.update(_HEADERS)

    for keyword in keywords:
        for location in locations:
            for page in range(1, pages + 1):
                params = _build_query(keyword, location, experience, page)
                try:
                    resp = session.get(_BASE_URL, params=params, timeout=20)
                except requests.RequestException as exc:
                    log.warning("Naukri fetch failed for %s/%s p%d: %s", keyword, location, page, exc)
                    break

                if resp.status_code != 200:
                    log.warning("Naukri returned %s for %s/%s p%d", resp.status_code, keyword, location, page)
                    break

                try:
                    data = resp.json()
                except ValueError:
                    log.warning("Naukri returned non-JSON for %s/%s p%d", keyword, location, page)
                    break

                jobs = data.get("jobDetails") or []
                if not jobs:
                    break

                for raw in jobs:
                    job = _normalize(raw)
                    if not job or job["id"] in seen_ids:
                        continue
                    seen_ids.add(job["id"])
                    yield job

                time.sleep(delay_sec)
