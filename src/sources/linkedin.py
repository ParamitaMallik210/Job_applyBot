"""Best-effort scraper for LinkedIn's public guest-job-search endpoint.

LinkedIn aggressively rate-limits and blocks GitHub Actions runners — expect
this source to fail intermittently. The bot treats LinkedIn as a bonus channel:
failures here don't break the run.

We hit the unauthenticated `seeMoreJobPostings/search` endpoint, which returns
HTML cards. No login or cookies needed, but no JD body either — we re-fetch the
JD page per card.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Iterable

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

_SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
_JD_URL_TEMPLATE = "https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{job_id}"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}

# LinkedIn's f_E (experience level) filter values: 1=internship, 2=entry,
# 3=associate, 4=mid-senior, 5=director, 6=executive. For 2-yr profile we
# target entry + associate.
_EXPERIENCE_FILTER = "2,3"


def _fetch_jd_body(session: requests.Session, job_id: str) -> str:
    try:
        resp = session.get(_JD_URL_TEMPLATE.format(job_id=job_id), timeout=15)
        if resp.status_code != 200:
            return ""
        soup = BeautifulSoup(resp.text, "html.parser")
        desc = soup.select_one(".description__text, .show-more-less-html__markup")
        return desc.get_text(" ", strip=True) if desc else ""
    except requests.RequestException:
        return ""


def _parse_card(card, session: requests.Session) -> dict | None:
    link_el = card.select_one("a.base-card__full-link, a.base-card__title-link")
    if not link_el:
        return None
    href = link_el.get("href", "")
    match = re.search(r"-(\d{8,})", href)
    if not match:
        return None
    job_id = match.group(1)

    title_el = card.select_one("h3.base-search-card__title")
    company_el = card.select_one("h4.base-search-card__subtitle a, h4.base-search-card__subtitle")
    location_el = card.select_one("span.job-search-card__location")
    posted_el = card.select_one("time")

    return {
        "id": f"linkedin:{job_id}",
        "source": "linkedin",
        "title": title_el.get_text(strip=True) if title_el else "",
        "company": company_el.get_text(strip=True) if company_el else "",
        "location": location_el.get_text(strip=True) if location_el else "",
        "experience": "",
        "salary": "",
        "description": _fetch_jd_body(session, job_id),
        "tags": "",
        "url": href.split("?")[0],
        "posted": posted_el.get_text(strip=True) if posted_el else "",
    }


def fetch(
    keywords: list[str],
    locations: list[str],
    pages: int = 2,
    delay_sec: float = 2.0,
) -> Iterable[dict]:
    """Yield deduped normalized job dicts. Silently skips if LinkedIn blocks us."""
    seen_ids: set[str] = set()
    session = requests.Session()
    session.headers.update(_HEADERS)

    for keyword in keywords:
        for location in locations:
            for page in range(pages):
                params = {
                    "keywords": keyword,
                    "location": location,
                    "f_E": _EXPERIENCE_FILTER,
                    "f_TPR": "r1209600",  # last 14 days (covers the 10-day backfill)
                    "start": page * 25,
                }
                try:
                    resp = session.get(_SEARCH_URL, params=params, timeout=20)
                except requests.RequestException as exc:
                    log.warning("LinkedIn fetch failed for %s/%s p%d: %s", keyword, location, page, exc)
                    break

                if resp.status_code != 200 or not resp.text.strip():
                    log.info("LinkedIn returned %s for %s/%s p%d — moving on", resp.status_code, keyword, location, page)
                    break

                soup = BeautifulSoup(resp.text, "html.parser")
                cards = soup.select("li, div.base-card")
                if not cards:
                    break

                for card in cards:
                    job = _parse_card(card, session)
                    if not job or job["id"] in seen_ids:
                        continue
                    seen_ids.add(job["id"])
                    yield job
                    time.sleep(0.5)

                time.sleep(delay_sec)
