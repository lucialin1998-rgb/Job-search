import logging
import os
from typing import Callable

import requests
import yaml

from models import Job
from parsers import bamboohr, generic, mbw, musicweek, workday
from state import load_state, save_state
from utils import dedupe_by_url, job_matches_keywords, setup_logging, write_jobs_csv

CONFIG_PATH = "config/sources.yaml"
OUTPUT_LATEST = "output/jobs_latest.csv"
OUTPUT_NEW = "output/jobs_new.csv"


def parse_page_only(source: dict, _session) -> list[Job]:
    return [
        Job(
            base_country=source.get("default_country", ""),
            company=source.get("name", ""),
            title="",
            channel=source.get("channel", ""),
            url=source.get("url", ""),
        )
    ]


PARSER_MAP: dict[str, Callable] = {
    "generic": generic.parse_source,
    "bamboohr": bamboohr.parse_source,
    "mbw": mbw.parse_source,
    "musicweek": musicweek.parse_source,
    "workday": workday.parse_source,
    "page_only": parse_page_only,
}


def load_sources(path: str = CONFIG_PATH) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    return cfg.get("sources", [])


def run() -> None:
    setup_logging()
    os.makedirs("output", exist_ok=True)
    os.makedirs("data", exist_ok=True)

    state = load_state()
    seen_urls = state["seen_urls"]
    seen_fingerprints = state["seen_fingerprints"]

    sources = load_sources()
    all_jobs: list[Job] = []
    new_jobs: list[Job] = []

    with requests.Session() as session:
        for source in sources:
            source_id = source.get("id", "unknown")
            parser_type = source.get("parser_type", "page_only")
            parser = PARSER_MAP.get(parser_type)
            if not parser:
                logging.warning("Unknown parser_type=%s for source=%s. Skipping.", parser_type, source_id)
                continue

            try:
                parsed_jobs = parser(source, session)
            except Exception as exc:
                logging.warning("Source failed: %s (%s)", source_id, exc)
                parsed_jobs = []

            fetched_count = len(parsed_jobs)
            kept_jobs = [job for job in parsed_jobs if job_matches_keywords(job, parser_type)]
            kept_count = len(kept_jobs)

            source_new = []
            for job in kept_jobs:
                key_url = job.url.strip()
                key_fp = job.fingerprint()
                is_new = False

                if key_url and key_url not in seen_urls:
                    seen_urls.add(key_url)
                    is_new = True
                elif key_fp and key_fp not in seen_fingerprints:
                    seen_fingerprints.add(key_fp)
                    if not key_url:
                        is_new = True

                if is_new:
                    source_new.append(job)

            all_jobs.extend(kept_jobs)
            new_jobs.extend(source_new)
            logging.info(
                "source=%s fetched_count=%s kept_count=%s new_count=%s",
                source_id,
                fetched_count,
                kept_count,
                len(source_new),
            )

    all_jobs = dedupe_by_url(all_jobs)
    new_jobs = dedupe_by_url(new_jobs)

    write_jobs_csv(OUTPUT_LATEST, all_jobs)
    write_jobs_csv(OUTPUT_NEW, new_jobs)
    save_state(seen_urls, seen_fingerprints)
    logging.info("Done. latest=%s new=%s", len(all_jobs), len(new_jobs))


if __name__ == "__main__":
    run()
