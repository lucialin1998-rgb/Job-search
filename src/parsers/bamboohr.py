import json
import logging
import re

from models import Job
from utils import absolute_url, extract_job_type, make_soup, normalize_text, safe_get


def _extract_json_blob(html: str) -> list[dict]:
    # Best effort: find JS data blob used by BambooHR.
    matches = re.findall(r"opening\s*:\s*(\{.*?\})\s*,\s*departments", html, flags=re.DOTALL)
    parsed = []
    for match in matches:
        try:
            parsed.append(json.loads(match))
        except json.JSONDecodeError:
            continue
    return parsed


def parse_source(source: dict, session) -> list[Job]:
    jobs = []
    resp = safe_get(session, source["url"])

    # Primary: parse cards/links from rendered HTML.
    soup = make_soup(resp.text)
    for a_tag in soup.select("a[href*='careers']") + soup.select("a[href*='job']"):
        title = normalize_text(a_tag.get_text(" ", strip=True))
        href = normalize_text(a_tag.get("href", ""))
        if not title or not href:
            continue

        location_text = ""
        parent_text = normalize_text(a_tag.parent.get_text(" ", strip=True)) if a_tag.parent else ""
        if "remote" in parent_text.lower():
            location_text = "Remote"

        jobs.append(
            Job(
                base_country=source.get("default_country", ""),
                company=source.get("name", ""),
                title=title,
                base_city=location_text,
                channel=source.get("channel", ""),
                job_type=extract_job_type(title),
                url=absolute_url(source["url"], href),
            )
        )

    # Fallback: attempt to parse JS blob when available.
    for item in _extract_json_blob(resp.text):
        title = normalize_text(item.get("jobOpeningName", ""))
        href = normalize_text(item.get("url", ""))
        if not title or not href:
            continue
        jobs.append(
            Job(
                base_country=source.get("default_country", ""),
                company=source.get("name", ""),
                title=title,
                base_city=normalize_text(item.get("location", "")),
                channel=source.get("channel", ""),
                job_type=extract_job_type(title),
                url=absolute_url(source["url"], href),
            )
        )

    logging.info("bamboohr parser extracted %s candidates from %s", len(jobs), source["id"])
    return jobs
