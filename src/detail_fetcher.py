import json
import logging
import re
import time

from bs4 import BeautifulSoup

from models import Job
from utils import GLOBAL_EXCLUDE_PATTERNS, normalize_text, safe_get

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

LOCATION_LABELS = [
    "location",
    "job location",
    "based in",
    "office",
    "city",
    "remote",
    "hybrid",
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


def _heading_block_lines(soup: BeautifulSoup, heading_keywords: list[str], max_siblings: int = 5) -> list[str]:
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
            if sibling.name in ["p", "div", "span"]:
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


def _dedupe_lines(lines: list[str]) -> list[str]:
    seen = set()
    out = []
    for line in lines:
        key = normalize_text(line).lower()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(normalize_text(line))
    return out


def _remove_overlap(primary: list[str], secondary: list[str]) -> list[str]:
    secondary_keys = {normalize_text(x).lower() for x in secondary}
    return [x for x in primary if normalize_text(x).lower() not in secondary_keys]


def _extract_location_from_json_ld(soup: BeautifulSoup) -> str:
    for node in soup.find_all("script", attrs={"type": "application/ld+json"}):
        raw = (node.string or node.get_text() or "").strip()
        if not raw:
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            continue

        items = payload if isinstance(payload, list) else [payload]
        for item in items:
            if not isinstance(item, dict):
                continue
            job_location = item.get("jobLocation")
            if isinstance(job_location, dict):
                address = job_location.get("address", {})
                locality = address.get("addressLocality") if isinstance(address, dict) else ""
                region = address.get("addressRegion") if isinstance(address, dict) else ""
                place = ", ".join([x for x in [locality, region] if x])
                if place:
                    return place[:80]
            if isinstance(job_location, list):
                for loc_item in job_location:
                    if not isinstance(loc_item, dict):
                        continue
                    address = loc_item.get("address", {})
                    locality = address.get("addressLocality") if isinstance(address, dict) else ""
                    region = address.get("addressRegion") if isinstance(address, dict) else ""
                    place = ", ".join([x for x in [locality, region] if x])
                    if place:
                        return place[:80]
    return ""


def _extract_location_from_text(lines: list[str], location_hints: list[str] | None = None) -> str:
    for line in lines[:220]:
        lowered = line.lower()
        if "remote" in lowered:
            return "Remote"
        if "hybrid" in lowered:
            return "Hybrid"
        if any(label in lowered for label in LOCATION_LABELS):
            cleaned = re.sub(r"^(location|job location|based in|office|city)\s*[:\-]?\s*", "", line, flags=re.I)
            cleaned = normalize_text(cleaned)
            if cleaned and len(cleaned) <= 80:
                return cleaned

    for hint in location_hints or []:
        if any(hint.lower() in line.lower() for line in lines[:220]):
            return hint[:80]

    return ""


def _looks_like_non_job(title: str, text: str, bullets: list[str]) -> bool:
    title_l = (title or "").lower()
    text_l = (text or "").lower()
    if any(p in title_l for p in GLOBAL_EXCLUDE_PATTERNS):
        return True
    matches = sum(1 for p in GLOBAL_EXCLUDE_PATTERNS if p in text_l)
    if matches >= 3:
        return True
    if not bullets and "job" not in text_l and "career" not in text_l and "apply" not in text_l:
        return True
    return False


def enrich_job_details(job: Job, session, source: dict | None = None) -> tuple[bool, bool, bool]:
    if not job.url:
        return False, False, False

    try:
        time.sleep(0.5)
        response = safe_get(session, job.url, timeout=20, retries=3)
    except Exception as exc:
        logging.warning("Detail fetch failed for %s: %s", job.url, exc)
        return False, False, False

    soup = BeautifulSoup(response.text, "html.parser")
    _clean_soup(soup)

    full_text = normalize_text(soup.get_text("\n", strip=True))
    all_lines = _to_lines(full_text)
    all_bullets = _extract_all_bullets(soup)

    if _looks_like_non_job(job.title, full_text, all_bullets):
        return True, False, False

    location_hints = (source or {}).get("location_hints") or []
    location = _extract_location_from_json_ld(soup) or _extract_location_from_text(all_lines, location_hints)
    location_extracted = False
    if location and not job.base_city:
        job.base_city = location
        location_extracted = True

    responsibility_lines = _heading_block_lines(soup, RESPONSIBILITY_HEADINGS)
    if not responsibility_lines and all_bullets:
        responsibility_lines = all_bullets[:6]

    if responsibility_lines:
        job.responsibilities = _join_limited(_dedupe_lines(responsibility_lines), 1200)
    elif all_lines:
        job.responsibilities = normalize_text(" ".join(all_lines))[:800]

    requirement_lines = _heading_block_lines(soup, REQUIREMENT_HEADINGS)
    candidate_lines = requirement_lines or all_bullets or all_lines
    hard_lines, soft_lines = _split_hard_soft(candidate_lines)

    hard_lines = _dedupe_lines(hard_lines)
    soft_lines = _dedupe_lines(_remove_overlap(soft_lines, hard_lines))

    if hard_lines:
        job.hard_skills = _join_limited(hard_lines, 800)
    if soft_lines:
        job.soft_skills = _join_limited(soft_lines, 800)

    emails = sorted(set(EMAIL_REGEX.findall(full_text)))
    if emails:
        job.contact = ";".join(emails)

    return True, True, location_extracted
