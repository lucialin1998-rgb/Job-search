import logging

from models import Job
from utils import absolute_url, extract_job_type, make_soup, normalize_text, safe_get


def parse_source(source: dict, session) -> list[Job]:
    """
    Best-effort Workday parser for static HTML snapshots.
    If no jobs are found, caller can still create a page_only entry.
    """
    jobs = []
    resp = safe_get(session, source["url"])
    soup = make_soup(resp.text)

    for a_tag in soup.select("a[href*='job']") + soup.select("a[href*='careers']"):
        title = normalize_text(a_tag.get_text(" ", strip=True))
        href = normalize_text(a_tag.get("href", ""))
        if not title or not href:
            continue

        jobs.append(
            Job(
                base_country=source.get("default_country", ""),
                company=source.get("name", ""),
                title=title,
                channel=source.get("channel", ""),
                job_type=extract_job_type(title),
                url=absolute_url(source["url"], href),
            )
        )

    logging.info("workday parser extracted %s candidates from %s", len(jobs), source["id"])
    return jobs
