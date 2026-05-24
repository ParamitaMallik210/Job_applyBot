"""ATS-style matching between resume and JD.

Two layers:
  1. Cheap keyword score (always runs) — % of your declared skills that appear
     in the JD, plus a list of JD-mentioned skills missing from your resume.
  2. Optional LLM critique (Claude) — short, actionable bullet suggestions to
     bump your match score for this specific JD.
"""

from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


# Broad pool of skill tokens we look for in JDs. Used to detect JD-mentioned
# skills the user's resume doesn't claim, so we can flag them.
_COMMON_SKILLS = {
    "java", "python", "javascript", "typescript", "go", "golang", "c++", "c#",
    "ruby", "rust", "kotlin", "swift", "scala", "php",
    "spring", "spring boot", "hibernate", "django", "flask", "fastapi",
    "node", "node.js", "nodejs", "express", "react", "next.js", "angular", "vue",
    "rest", "rest api", "graphql", "grpc", "microservices", "soap",
    "mysql", "postgresql", "postgres", "mongodb", "redis", "cassandra", "dynamodb",
    "elasticsearch", "kafka", "rabbitmq", "sqs",
    "aws", "gcp", "azure", "ec2", "s3", "lambda", "ecs", "eks",
    "docker", "kubernetes", "k8s", "terraform", "helm",
    "jenkins", "github actions", "gitlab ci", "circleci", "ci/cd",
    "junit", "mockito", "pytest", "selenium", "cypress",
    "git", "linux", "unix", "bash", "shell",
    "agile", "scrum", "jira",
    "machine learning", "ml", "data structures", "algorithms",
}


@dataclass
class AtsResult:
    score: int  # 0-100
    matched: list[str] = field(default_factory=list)
    missing_from_resume: list[str] = field(default_factory=list)
    missing_from_jd: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


def _tokens(text: str) -> str:
    return re.sub(r"[^a-z0-9+#./\- ]", " ", text.lower())


def _contains(haystack: str, needle: str) -> bool:
    pattern = r"(?<![a-z0-9])" + re.escape(needle) + r"(?![a-z0-9])"
    return re.search(pattern, haystack) is not None


def _keyword_score(resume_text: str, jd_text: str, my_skills: list[str]) -> AtsResult:
    resume = _tokens(resume_text)
    jd = _tokens(jd_text)

    matched = [s for s in my_skills if _contains(resume, s) and _contains(jd, s)]
    missing_from_resume = sorted({
        s for s in _COMMON_SKILLS
        if _contains(jd, s) and not _contains(resume, s)
    })
    missing_from_jd = [s for s in my_skills if _contains(resume, s) and not _contains(jd, s)]

    jd_skills = [s for s in my_skills if _contains(jd, s)]
    score = round(100 * len(matched) / max(1, len(jd_skills))) if jd_skills else 50

    return AtsResult(
        score=score,
        matched=matched,
        missing_from_resume=missing_from_resume[:8],
        missing_from_jd=missing_from_jd[:8],
    )


def _llm_suggestions(resume_text: str, jd: dict, model: str) -> list[str]:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.info("ANTHROPIC_API_KEY not set — skipping LLM suggestions")
        return []

    try:
        import anthropic
    except ImportError:
        log.warning("anthropic SDK not installed — skipping LLM suggestions")
        return []

    client = anthropic.Anthropic(api_key=api_key)
    prompt = (
        "You are an ATS resume coach. Given a job description and a candidate "
        "resume, output exactly 3 short, specific, actionable bullet edits the "
        "candidate could make to their resume to better match THIS job. Each "
        "bullet should be one sentence, concrete (e.g. 'rephrase X as Y' or "
        "'add a bullet about Z'), and grounded in skills they likely have based "
        "on the resume. No fluff, no preamble.\n\n"
        f"=== JOB TITLE ===\n{jd.get('title', '')}\n"
        f"=== COMPANY ===\n{jd.get('company', '')}\n"
        f"=== JOB DESCRIPTION ===\n{jd.get('description', '')[:3000]}\n"
        f"=== RESUME ===\n{resume_text[:4000]}\n"
        "Output only the 3 bullets, one per line, each starting with '- '."
    )

    try:
        resp = client.messages.create(
            model=model,
            max_tokens=400,
            messages=[{"role": "user", "content": prompt}],
        )
        text = resp.content[0].text if resp.content else ""
    except Exception as exc:
        log.warning("Claude call failed: %s", exc)
        return []

    bullets = [
        line.lstrip("-• ").strip()
        for line in text.splitlines()
        if line.strip().startswith(("-", "•"))
    ]
    return bullets[:3]


def score_job(
    resume_text: str,
    jd: dict,
    my_skills: list[str],
    use_llm: bool = True,
    llm_model: str = "claude-sonnet-4-6",
) -> AtsResult:
    result = _keyword_score(resume_text, jd.get("description", ""), my_skills)
    if use_llm:
        result.suggestions = _llm_suggestions(resume_text, jd, llm_model)
    return result
