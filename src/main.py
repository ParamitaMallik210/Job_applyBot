"""Entry point. Wires scrapers → filter → dedup → ATS scoring → notify."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Allow `python -m src.main` and `python src/main.py` from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import config, filters, state  # noqa: E402
from src.ats import load_resume_text, score_job  # noqa: E402
from src.notify import send_digest  # noqa: E402
from src.sources import fetch_linkedin, fetch_naukri  # noqa: E402


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
log = logging.getLogger("jobbot")


def _gather_jobs(cfg: dict) -> list[dict]:
    profile = cfg["profile"]
    keywords = cfg["title_whitelist"]
    locations = profile["locations"]
    experience = profile["experience_years"]

    jobs: list[dict] = []
    sources_cfg = cfg.get("sources", {})

    if sources_cfg.get("naukri", {}).get("enabled", True):
        log.info("Fetching Naukri...")
        try:
            jobs.extend(
                fetch_naukri(
                    keywords=keywords,
                    locations=locations,
                    experience=experience,
                    pages=sources_cfg["naukri"].get("pages_per_query", 3),
                )
            )
        except Exception as exc:
            log.exception("Naukri source crashed: %s", exc)

    if sources_cfg.get("linkedin", {}).get("enabled", True):
        log.info("Fetching LinkedIn (best-effort)...")
        try:
            jobs.extend(
                fetch_linkedin(
                    keywords=keywords[:5],  # keep LinkedIn calls modest to dodge blocks
                    locations=locations,
                    pages=sources_cfg["linkedin"].get("pages_per_query", 2),
                )
            )
        except Exception as exc:
            log.warning("LinkedIn source crashed (expected sometimes): %s", exc)

    return jobs


def run() -> int:
    cfg = config.load()
    resume_text = load_resume_text(cfg["resume"]["path"])
    log.info("Loaded resume (%d chars)", len(resume_text))

    seen = state.load()
    log.info("State: %d previously-seen job ids", len(seen))

    jobs = _gather_jobs(cfg)
    log.info("Gathered %d raw postings", len(jobs))

    matches: list[tuple[dict, object]] = []
    min_score = cfg.get("notify", {}).get("min_score_to_notify", 40)
    ats_cfg = cfg["ats"]

    for job in jobs:
        if job["id"] in seen:
            continue
        ok, reason = filters.passes(job, cfg)
        if not ok:
            log.debug("Skip %s: %s", job["title"], reason)
            seen.add(job["id"])
            continue
        ats = score_job(
            resume_text=resume_text,
            jd=job,
            my_skills=ats_cfg["my_skills"],
            use_llm=ats_cfg.get("llm_suggestions", True),
            llm_model=ats_cfg.get("llm_model", "claude-sonnet-4-6"),
        )
        seen.add(job["id"])
        if ats.score < min_score:
            log.info("Skip (low score %d): %s @ %s", ats.score, job["title"], job["company"])
            continue
        matches.append((job, ats))
        log.info("Match (%d%%): %s @ %s", ats.score, job["title"], job["company"])

    matches.sort(key=lambda m: m[1].score, reverse=True)
    channel = cfg.get("notify", {}).get("channel", "whatsapp")
    sent = send_digest(matches, channel=channel)
    log.info("Sent %d notifications via %s", sent, channel)

    state.save(seen)
    return 0


if __name__ == "__main__":
    sys.exit(run())
