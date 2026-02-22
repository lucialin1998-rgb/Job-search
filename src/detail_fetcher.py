import logging
import re
import time

from bs4 import BeautifulSoup

from models import Job
from utils import normalize_text, safe_get

RESPONSIBILITY_HEADINGS = [
    "responsibilities",
    "what you'll do",
    "what you will do",
    "duties",
    "the role",
    "key responsibilities",
]

REQUIREMENT_HEADINGS = [
    "requirements",
    "skills",
    "experience",
    "essential",
    "desirable",
    "qualifications",
    "what you'll need",
    "what you will need",
]

HARD_SKILL_KEYWORDS = [
    "excel",
    "spreadsheet",
    "crm",
    "database",
    "sql",
    "python",
    "analytics",
    "reporting",
    "royalties",
    "royalty",
    "rights",
    "copyright",
    "licensing",
    "distribution",
    "metadata",
    "contracts",
    "invoices",
    "budgeting",
    "finance",
]

SOFT_SKILL_KEYWORDS = [
    "communication",
    "stakeholder",
    "detail-oriented",
    "organisation",
    "organized",
    "teamwork",
    "proactive",
    "time management",
    "problem solving",
    "adaptability",
]

EMAIL_REGEX = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _clean_soup(soup: BeautifulSoup) -> None:
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()


def _to_lines(text: str) -> list[str]:
    return [normalize_text(x) for x in text.split("\n") if normalize_text(x)]


def _extract_all_bullets(soup: BeautifulSoup) -> list[str]:
    bullets = []
    for li in soup.find_all("li"):
        value = normalize_text(li.get_text(" ", strip=True))
        if value:
            bullets.append(value)
    return bullets


def _join_limited(items: list[str], max_chars: int) -> str:
    if not items:
        return ""
    text = "\n".join(items)
    return text[:max_chars]


def _heading_block_lines(soup: BeautifulSoup, heading_keywords: list[str], max_siblings: int = 4) -> list[str]:
    collected = []
    headings = soup.find_all(["h1", "h2", "h3", "h4", "strong", "b"])
    for heading in headings:
        heading_text = normalize_text(heading.get_text(" ", strip=True)).lower()
        if not any(key in heading_text for key in heading_keywords):
            continue

        sibling = heading
        scanned = 0
        while scanned < max_siblings:
            sibling = sibling.find_next_sibling()
            if sibling is None:
                break
            scanned += 1
            if sibling.name in ["h1", "h2", "h3", "h4"]:
                break

            for li in sibling.select("li"):
                line = normalize_text(li.get_text(" ", strip=True))
                if line:
                    collected.append(line)
            if sibling.name in ["p", "div"]:
                line = normalize_text(sibling.get_text(" ", strip=True))
                if line:
                    collected.append(line)

        if collected:
            return collected

    return []


def _split_hard_soft(lines: list[str]) -> tuple[list[str], list[str]]:
    hard, soft = [], []
    for line in lines:
        lowered = line.lower()
        hard_match = any(key in lowered for key in HARD_SKILL_KEYWORDS)
        soft_match = any(key in lowered for key in SOFT_SKILL_KEYWORDS)
        if hard_match:
            hard.append(line)
        if soft_match:
            soft.append(line)
    return hard, soft


def enrich_job_details(job: Job, session) -> bool:
    if not job.url:
        return False

    try:
        time.sleep(0.5)
        response = safe_get(session, job.url, timeout=20, retries=3)
    except Exception as exc:
        logging.warning("Detail fetch failed for %s: %s", job.url, exc)
        return False

    soup = BeautifulSoup(response.text, "html.parser")
    _clean_soup(soup)

    full_text = normalize_text(soup.get_text("\n", strip=True))
    all_lines = _to_lines(full_text)
    all_bullets = _extract_all_bullets(soup)

    responsibility_lines = _heading_block_lines(soup, RESPONSIBILITY_HEADINGS)
    if not responsibility_lines and all_bullets:
        responsibility_lines = all_bullets[:6]

    if responsibility_lines:
        job.responsibilities = _join_limited(responsibility_lines, 1200)
    elif all_lines:
        job.responsibilities = normalize_text(" ".join(all_lines))[:800]

    requirement_lines = _heading_block_lines(soup, REQUIREMENT_HEADINGS)
    candidate_lines = requirement_lines or all_bullets or all_lines
    hard_lines, soft_lines = _split_hard_soft(candidate_lines)

    if hard_lines:
        job.hard_skills = _join_limited(hard_lines, 800)
    if soft_lines:
        job.soft_skills = _join_limited(soft_lines, 800)

    emails = sorted(set(EMAIL_REGEX.findall(full_text)))
    if emails:
        job.contact = ";".join(emails)

    return True
