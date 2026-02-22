import logging

from models import Job
from utils import absolute_url, extract_job_type, make_soup, normalize_text, safe_get


def parse_source(source: dict, session) -> list[Job]:
    jobs = []
    resp = safe_get(session, source["url"])
    soup = make_soup(resp.text)

    for a_tag in soup.select("a[href]"):
        href = normalize_text(a_tag.get("href", ""))
        title = normalize_text(a_tag.get_text(" ", strip=True))
        if not href:
            continue
        url = absolute_url(source["url"], href)
        if not title:
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
