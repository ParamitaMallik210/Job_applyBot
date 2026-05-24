"""Decide whether a job posting matches the user's criteria."""

from __future__ import annotations

import re


def _haystack(job: dict) -> str:
    return f"{job.get('title', '')} {job.get('description', '')} {job.get('tags', '')}".lower()


def _title_matches_whitelist(title: str, whitelist: list[str]) -> bool:
    t = title.lower()
    return any(w.lower() in t for w in whitelist)


def _title_hits_blocklist(title: str, blocklist: list[str]) -> bool:
    t = title.lower()
    return any(re.search(rf"\b{re.escape(b.lower())}\b", t) for b in blocklist)


def _jd_matches(text: str, phrases: list[str], min_hits: int) -> bool:
    hits = sum(1 for p in phrases if p.lower() in text)
    return hits >= min_hits


def _location_matches(job_loc: str, locations: list[str]) -> bool:
    if not locations:
        return True
    jl = job_loc.lower()
    if not jl:
        return False
    return any(loc.lower() in jl for loc in locations)


def _extract_experience_range(text: str) -> tuple[float, float] | None:
    """Pull (min, max) years from strings like '2-4 Yrs' / '5 - 7 years' / '0-3 Yrs'."""
    if not text:
        return None
    s = text.lower()
    m = re.search(r"(\d+(?:\.\d+)?)\s*[-–to]+\s*(\d+(?:\.\d+)?)", s)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = re.search(r"(\d+(?:\.\d+)?)\s*\+?\s*y", s)
    if m:
        v = float(m.group(1))
        return v, v + 5
    return None


def _extract_max_lpa(text: str) -> float | None:
    """Pull the upper bound of a salary range from a Naukri/LinkedIn string.

    Examples this handles:
      "₹ 12,00,000 - 20,00,000 PA"   -> 20.0
      "12-20 Lacs PA"                -> 20.0
      "Not disclosed"                -> None
    """
    if not text:
        return None
    s = text.lower().replace(",", "")
    if "not disclosed" in s or "not specified" in s:
        return None

    rng = re.search(r"(\d+(?:\.\d+)?)\s*[-–to]+\s*(\d+(?:\.\d+)?)", s)
    if rng:
        hi = float(rng.group(2))
    else:
        single = re.search(r"(\d+(?:\.\d+)?)", s)
        if not single:
            return None
        hi = float(single.group(1))

    if "lac" in s or "lakh" in s or "lpa" in s:
        return hi
    if hi >= 100000:  # raw rupees
        return hi / 100000
    return hi


def passes(job: dict, cfg: dict) -> tuple[bool, str]:
    """Return (matches, reason). Reason is informational for logging."""
    title = job.get("title", "")
    if not title:
        return False, "no title"

    blocklist = cfg.get("title_blocklist") or []
    if _title_hits_blocklist(title, blocklist):
        return False, f"title hit blocklist"

    whitelist = cfg.get("title_whitelist") or []
    title_ok = _title_matches_whitelist(title, whitelist)
    if not title_ok:
        jd_cfg = cfg.get("jd_match") or {}
        if not _jd_matches(
            _haystack(job),
            jd_cfg.get("phrases", []),
            jd_cfg.get("min_hits", 3),
        ):
            return False, "title not whitelisted and JD lacks enough matches"

    locations = cfg.get("profile", {}).get("locations") or []
    if not _location_matches(job.get("location", ""), locations):
        return False, f"location {job.get('location')!r} off-target"

    # Drop postings whose minimum required experience is more than 1 year above
    # the user's profile — those are not realistic targets.
    user_exp = cfg.get("profile", {}).get("experience_years") or 0
    if user_exp:
        exp_range = _extract_experience_range(job.get("experience", ""))
        if exp_range and exp_range[0] > user_exp + 1:
            return False, f"experience {exp_range} too senior for {user_exp} yrs"

    min_lpa = cfg.get("profile", {}).get("min_ctc_lpa")
    if min_lpa:
        salary_str = job.get("salary", "")
        max_lpa = _extract_max_lpa(salary_str)
        # Skip the filter entirely when salary is undisclosed — most Naukri
        # postings hide it, so dropping those would discard 80%+ of matches.
        if max_lpa is not None and max_lpa < min_lpa:
            return False, f"salary {max_lpa} LPA < {min_lpa}"

    return True, "ok"
