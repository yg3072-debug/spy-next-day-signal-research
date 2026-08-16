"""Collect public archive pages for Donald Trump's Truth Social posts.

The script reads the independent archive at trumpstruth.org, not a Truth Social
API. It writes raw and checkpoint files under a caller-supplied directory. Raw
post text is intentionally excluded from this public repository; review the
source site's terms before collecting or redistributing it.
"""

from __future__ import annotations

import argparse
import re
import time
from pathlib import Path
from urllib.parse import urlencode, urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "https://trumpstruth.org"
DEFAULT_USER_AGENT = (
    "spy-next-day-signal-research/1.0 "
    "(educational research; rate-limited public archive reader)"
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("data/raw/trump_truth"))
    parser.add_argument("--start-date", default="2024-07-13")
    parser.add_argument("--end-date", default="2026-04-23")
    parser.add_argument("--per-page", type=int, default=100)
    parser.add_argument("--max-pages", type=int, default=1000)
    parser.add_argument("--sleep-seconds", type=float, default=1.0)
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT)
    return parser.parse_args()


def make_session(user_agent: str) -> requests.Session:
    retry = Retry(
        total=4,
        connect=4,
        read=4,
        status=4,
        backoff_factor=0.75,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
    )
    session = requests.Session()
    session.headers.update({"User-Agent": user_agent})
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def atomic_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    df.to_csv(temporary, index=False)
    temporary.replace(path)


def build_search_url(start_date: str, end_date: str, per_page: int, page: int) -> str:
    params = {
        "query": "",
        "start_date": start_date,
        "end_date": end_date,
        "sort": "date_asc",
        "removed": "include",
        "per_page": per_page,
        "page": page,
    }
    return f"{BASE_URL}/search?{urlencode(params)}"


def status_links(session: requests.Session, page_url: str) -> list[str]:
    response = session.get(page_url, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")
    links = {
        urljoin(BASE_URL, anchor["href"])
        for anchor in soup.find_all("a", href=True)
        if "/statuses/" in anchor["href"]
    }
    return sorted(links)


def discover_status_urls(
    session: requests.Session,
    start_date: str,
    end_date: str,
    per_page: int,
    max_pages: int,
    sleep_seconds: float,
) -> list[str]:
    discovered: set[str] = set()
    for page in range(1, max_pages + 1):
        links = status_links(
            session,
            build_search_url(start_date, end_date, per_page, page),
        )
        before = len(discovered)
        discovered.update(links)
        added = len(discovered) - before
        print(f"archive page {page}: {len(links)} links, {added} new")
        if not links or added == 0:
            break
        time.sleep(sleep_seconds)
    return sorted(discovered)


def parse_post_page(session: requests.Session, url: str) -> dict[str, str | None]:
    response = session.get(url, timeout=30)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "lxml")
    page_text = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))

    status_match = re.search(r"/statuses/(\d+)", url)
    original_match = re.search(
        r"Original URL (https://truthsocial\.com/\S+)", page_text
    )
    date_match = re.search(r"Original Post Date (.*?) Capture Date", page_text)

    post_text = None
    for pattern in (
        r"Original Post (.*?) Share:",
        r"Original Post (.*?) Information",
        r"Original Post (.*?) Original Post Date",
    ):
        match = re.search(pattern, page_text)
        if match:
            candidate = re.sub(r"\s+", " ", match.group(1)).strip()
            if candidate and not candidate.startswith("Share: Copy link"):
                post_text = candidate
                break

    return {
        "status_id": status_match.group(1) if status_match else None,
        "archive_url": url,
        "original_truthsocial_url": original_match.group(1) if original_match else None,
        "created_at_raw": date_match.group(1).strip() if date_match else None,
        "text_raw": post_text,
    }


def scrape_posts(
    session: requests.Session,
    urls: list[str],
    checkpoint_path: Path,
    sleep_seconds: float,
) -> pd.DataFrame:
    if checkpoint_path.exists():
        checkpoint = pd.read_csv(checkpoint_path, dtype={"status_id": "string"})
        rows = checkpoint.to_dict("records")
        completed = set(checkpoint["archive_url"].dropna().astype(str))
    else:
        rows = []
        completed = set()

    remaining = [url for url in urls if url not in completed]
    print(f"checkpoint rows: {len(rows)}; remaining pages: {len(remaining)}")

    for index, url in enumerate(remaining, start=1):
        try:
            rows.append(parse_post_page(session, url))
            print(f"post {index}/{len(remaining)}: {url}")
        except requests.RequestException as error:
            print(f"request failed: {url} | {error}")
        if index % 10 == 0:
            atomic_csv(pd.DataFrame(rows), checkpoint_path)
        time.sleep(sleep_seconds)

    result = pd.DataFrame(rows)
    atomic_csv(result, checkpoint_path)
    return result


def main() -> None:
    args = parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    session = make_session(args.user_agent)

    discovered_path = args.output_dir / "discovered_status_urls.csv"
    if discovered_path.exists():
        urls = pd.read_csv(discovered_path)["status_url"].dropna().astype(str).tolist()
    else:
        urls = discover_status_urls(
            session,
            args.start_date,
            args.end_date,
            args.per_page,
            args.max_pages,
            args.sleep_seconds,
        )
        atomic_csv(pd.DataFrame({"status_url": urls}), discovered_path)

    raw = scrape_posts(
        session,
        urls,
        args.output_dir / "trump_archive_partial.csv",
        args.sleep_seconds,
    )
    atomic_csv(raw, args.output_dir / "trump_archive_raw.csv")
    print(f"saved {len(raw):,} archive rows to {args.output_dir}")


if __name__ == "__main__":
    main()
