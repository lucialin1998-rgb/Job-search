import logging

from models import Job
from utils import absolute_url, make_soup, normalize_text, safe_get


def parse_source(source: dict, session) -> list[Job]:
    jobs = []
    resp = safe_get(session, source["url"])
    soup = make_soup(resp.text)

    for card in soup.select("article") + soup.select(".job") + soup.select("li"):
        a_tag = card.select_one("a[href]")
        if not a_tag:
            continue
        title = normalize_text(a_tag.get_text(" ", strip=True))
        href = normalize_text(a_tag.get("href", ""))
        date_node = card.select_one("time")

        if not title or not href:
            continue

        jobs.append(
            Job(
                base_country=source.get("default_country", ""),
                company=source.get("name", ""),
                title=title,
                posting_date=normalize_text(date_node.get_text(" ", strip=True)) if date_node else "",
                channel=source.get("channel", ""),
                url=absolute_url(source["url"], href),
            )
        )

    logging.info("mbw parser extracted %s candidates from %s", len(jobs), source["id"])
    return jobs
