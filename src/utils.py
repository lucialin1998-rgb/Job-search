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
    "read full article",
    "academy",
    "california privacy",
]

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0 Safari/537.36 JobSearchBot/1.0"
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


def is_job_candidate_allowed(job: Job, source: dict) -> bool:
    combined_text = f"{job.title} {job.url}".lower()

    source_exclude_patterns = source.get("exclude_patterns") or []
    if _any_pattern_match(combined_text, GLOBAL_EXCLUDE_PATTERNS):
        return False
    if _any_pattern_match(combined_text, source_exclude_patterns):
        return False

    include_patterns = source.get("include_patterns")
    if include_patterns:
        if not _any_pattern_match(combined_text, include_patterns):
            return False

    return True


def job_matches_keywords(job: Job, parser_type: str) -> bool:
    text = f"{job.title} {job.responsibilities} {job.hard_skills} {job.soft_skills}".lower()
    if parser_type == "page_only" and not job.title:
        return True
    keywords = ROLE_KEYWORDS + DOMAIN_KEYWORDS
    return any(keyword in text for keyword in keywords)


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
