import logging

from models import Job
from utils import absolute_url, extract_job_type, make_soup, normalize_text, safe_get

PREFERRED_URL_HINTS = [
    "/job",
    "/jobs",
    "/career",
    "/careers",
    "/vacancy",
    "/vacancies",
    "/opening",
    "/openings",
    "/position",
    "/positions",
    "/apply",
]

REJECT_URL_HINTS = [
    "/privacy",
    "/cookies",
    "/policy",
    "/terms",
    "/news",
    "/blog",
    "/press",
]

ROLE_KEYWORDS = ["intern", "internship", "assistant", "coordinator", "administrator", "associate"]


def parse_source(source: dict, session) -> list[Job]:
    jobs = []
    resp = safe_get(session, source["url"])
    soup = make_soup(resp.text)

    for a_tag in soup.select("a[href]"):
        href = normalize_text(a_tag.get("href", ""))
        title = normalize_text(a_tag.get_text(" ", strip=True))
        if not href or not title:
            continue

        url = absolute_url(source["url"], href)
        lowered_url = url.lower()
        lowered_title = title.lower()

        if any(hint in lowered_url for hint in REJECT_URL_HINTS):
            continue

        preferred_link = any(hint in lowered_url for hint in PREFERRED_URL_HINTS)
        title_has_role_keyword = any(keyword in lowered_title for keyword in ROLE_KEYWORDS)
        if not preferred_link and not title_has_role_keyword:
            continue

        jobs.append(
            Job(
                base_country=source.get("default_country", ""),
                company=source.get("name", ""),
                title=title,
                channel=source.get("channel", ""),
                job_type=extract_job_type(title),
                url=url,
            )
        )

    logging.info("generic parser extracted %s candidates from %s", len(jobs), source["id"])
    return jobs
