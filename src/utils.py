import csv
import logging
import re
import time
from typing import Iterable, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from models import CSV_HEADERS, Job

ROLE_KEYWORDS = ["intern", "internship", "assistant", "coordinator"]
DOMAIN_KEYWORDS = [
    "operations",
    "operational",
    "royalties",
    "royalty",
    "rights",
    "copyright",
    "distribution",
    "digital",
    "publishing",
    "label services",
    "metadata",
]

STRONG_DOMAIN_KEYWORDS = [
    "rights",
    "royalties",
    "royalty",
    "copyright",
    "licensing",
    "publishing",
    "distribution",
    "metadata",
]

JUNIOR_INCLUDE_KEYWORDS = [
    "intern",
    "internship",
    "assistant",
    "coordinator",
    "administrator",
    "associate",
]

SENIOR_EXCLUDE_KEYWORDS = [
    "manager",
    "senior",
    "lead",
    "head",
    "director",
    "vp",
    "principal",
    "chief",
    "executive",
    "consultant",
]

GLOBAL_EXCLUDE_PATTERNS = [
    "privacy",
    "cookie",
    "cookies",
    "policy",
    "terms",
    "legal",
    "gdpr",
    "sitemap",
    "accessibility",
    "press",
    "news",
    "blog",
    "article",
    "academy",
    "read full article",
    "california privacy",
    "your california privacy rights",
    "reservation of rights",
]

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36 JobSearchBot/1.2"
    )
}


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )


def normalize_text(text: Optional[str]) -> str:
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def absolute_url(base_url: str, link: str) -> str:
    if not link:
        return ""
    return urljoin(base_url, link)


def safe_get(
    session: requests.Session,
    url: str,
    timeout: int = 20,
    retries: int = 3,
    backoff_seconds: float = 1.5,
):
    last_error = None
    for attempt in range(1, retries + 1):
        try:
            resp = session.get(url, timeout=timeout, headers=DEFAULT_HEADERS)
            resp.raise_for_status()
            return resp
        except requests.RequestException as exc:
            last_error = exc
            logging.warning("Request failed (%s/%s) for %s: %s", attempt, retries, url, exc)
            if attempt < retries:
                time.sleep(backoff_seconds * attempt)
    raise last_error


def make_soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "html.parser")


def extract_job_type(text: str) -> str:
    lowered = text.lower()
    if "intern" in lowered:
        return "internship"
    if "part-time" in lowered or "part time" in lowered:
        return "part-time"
    if "full-time" in lowered or "full time" in lowered:
        return "full-time"
    if "contract" in lowered:
        return "contract"
    return ""


def _any_pattern_match(text: str, patterns: list[str]) -> bool:
    lowered = (text or "").lower()
    return any(pattern.lower() in lowered for pattern in patterns if pattern)


def _count_pattern_matches(text: str, patterns: list[str]) -> int:
    lowered = (text or "").lower()
    return sum(1 for pattern in patterns if pattern and pattern.lower() in lowered)


def is_job_candidate_allowed(job: Job, source: dict) -> bool:
    combined_text = f"{job.title} {job.url}".lower()

    source_exclude_patterns = source.get("exclude_patterns") or []
    if _any_pattern_match(combined_text, GLOBAL_EXCLUDE_PATTERNS):
        return False
    if _any_pattern_match(combined_text, source_exclude_patterns):
        return False

    include_patterns = source.get("include_patterns")
    if include_patterns and not _any_pattern_match(combined_text, include_patterns):
        return False

    return True


def job_matches_keywords(job: Job, parser_type: str) -> bool:
    text = f"{job.title} {job.responsibilities} {job.hard_skills} {job.soft_skills}".lower()
    if parser_type == "page_only" and not job.title:
        return True
    keywords = ROLE_KEYWORDS + DOMAIN_KEYWORDS
    return any(keyword in text for keyword in keywords)


def _title_is_junior(title: str) -> bool:
    title_l = (title or "").lower()
    if "senior associate" in title_l:
        return False
    return any(keyword in title_l for keyword in JUNIOR_INCLUDE_KEYWORDS)


def _title_is_senior(title: str) -> bool:
    title_l = (title or "").lower()
    return any(keyword in title_l for keyword in SENIOR_EXCLUDE_KEYWORDS)


def _is_job_board_source(source: dict) -> bool:
    source_id = (source.get("id") or "").lower()
    name = (source.get("name") or "").lower()
    return source_id in {"mbw_jobs", "musicweek_jobs", "cmu_jobs"} or "job board" in (source.get("channel", "").lower())


def assess_seniority_relevance(job: Job, source: dict) -> tuple[bool, str]:
    parser_type = source.get("parser_type", "")
    if parser_type == "page_only":
        return True, "kept"

    if source.get("seniority_mode", "junior_focus") != "junior_focus":
        return True, "kept"

    text = f"{job.title} {job.responsibilities} {job.hard_skills}".lower()
    domain_match_count = _count_pattern_matches(text, DOMAIN_KEYWORDS)
    strong_domain_match_count = _count_pattern_matches(text, STRONG_DOMAIN_KEYWORDS)

    if _title_is_junior(job.title):
        return True, "kept"

    is_senior = _title_is_senior(job.title)
    allow_senior_if_domain = source.get("allow_senior_if_domain_match", True) is not False

    if is_senior:
        if allow_senior_if_domain and strong_domain_match_count >= 2:
            return True, "kept"
        return False, "too_senior"

    if domain_match_count >= 1 or _is_job_board_source(source):
        return True, "kept"

    return False, "too_senior"


def dedupe_by_url(jobs: Iterable[Job]) -> list[Job]:
    seen = set()
    unique = []
    for job in jobs:
        key = job.url or job.fingerprint()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(job)
    return unique


def write_jobs_csv(path: str, jobs: Iterable[Job]) -> None:
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        for job in jobs:
            writer.writerow(job.to_csv_row())
