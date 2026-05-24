"""Hirist tech-jobs search — HTML scraping.

Hirist doesn't expose a clean JSON endpoint, but their search pages are small
and the markup is stable. We parse job cards directly.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Iterable

import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
}


def _slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def _parse_card(card) -> dict | None:
    title_el = card.select_one("h2, .job-title, a.title")
    if not title_el:
        return None
    title = title_el.get_text(strip=True)

    link_el = card.select_one("a[href]")
    href = link_el["href"] if link_el else ""
    if href and not href.startswith("http"):
        href = "https://www.hirist.tech" + href

    match = re.search(r"-(\d{5,})\.html", href or "")
    if not match:
        return None
    job_id = match.group(1)

    company = ""
    company_el = card.select_one(".company-name, .recruiter")
    if company_el:
        company = company_el.get_text(strip=True)

    loc_el = card.select_one(".location, .job-location")
    location = loc_el.get_text(strip=True) if loc_el else ""

    exp_el = card.select_one(".experience, .job-exp")
    experience = exp_el.get_text(strip=True) if exp_el else ""

    desc_el = card.select_one(".job-description, .desc")
    description = desc_el.get_text(" ", strip=True) if desc_el else ""

    return {
        "id": f"hirist:{job_id}",
        "source": "hirist",
        "title": title,
        "company": company,
        "location": location,
        "experience": experience,
        "salary": "",
        "description": description,
        "tags": "",
        "url": href,
        "posted": "",
    }


def fetch(
    keywords: list[str],
    locations: list[str],
    pages: int = 1,
    delay_sec: float = 2.0,
) -> Iterable[dict]:
    seen_ids: set[str] = set()
    session = requests.Session()
    session.headers.update(_HEADERS)

    for keyword in keywords:
        for location in locations:
            slug_kw = _slugify(keyword)
            slug_loc = _slugify(location)
            for page in range(1, pages + 1):
                url = f"https://www.hirist.tech/k/{slug_kw}-jobs-in-{slug_loc}-1l-{page}.html"
                try:
                    resp = session.get(url, timeout=20)
                except requests.RequestException as exc:
                    log.warning("Hirist fetch failed for %s/%s p%d: %s", keyword, location, page, exc)
                    break

                if resp.status_code != 200:
                    log.info("Hirist returned %s for %s/%s p%d", resp.status_code, keyword, location, page)
                    break

                soup = BeautifulSoup(resp.text, "html.parser")
                cards = soup.select(".job-block, .job-card, .listing-item")
                if not cards:
                    break

                for card in cards:
                    job = _parse_card(card)
                    if not job or job["id"] in seen_ids:
                        continue
                    seen_ids.add(job["id"])
                    yield job

                time.sleep(delay_sec)
