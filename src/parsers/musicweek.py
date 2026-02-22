import logging

from models import Job
from utils import absolute_url, make_soup, normalize_text, safe_get


def parse_source(source: dict, session) -> list[Job]:
    jobs = []
    resp = safe_get(session, source["url"])
    soup = make_soup(resp.text)

    selectors = [".jobs-listing a[href]", "article a[href]", "a[href*='job']"]
    for selector in selectors:
        for a_tag in soup.select(selector):
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
                    url=absolute_url(source["url"], href),
                )
            )

    logging.info("musicweek parser extracted %s candidates from %s", len(jobs), source["id"])
    return jobs
