"""Collect the Truth Social archive into a local, gitignored directory.

This is the public, auditable version of the collector that produced the frozen
snapshot. It exists so a reader can see exactly how the corpus was obtained and
obtain it themselves — **the corpus itself is not distributed with this
repository**, because whether to redistribute a publisher's content is that
publisher's decision and public accessibility does not make it otherwise.

Output goes to `ALT_DATA_SOURCE` (default `data/raw/`), which `.gitignore` excludes.
Nothing this writes is committable.

What it does, and what it refuses to do:

* one host only, `trumpstruth.org`, checked again **after** any redirect
* read-only `GET`; no credentials, cookies, tokens or login of any kind
* no attempt to bypass access control, rate limits or bot detection
* one request per second, with `Retry-After` honoured on 429
* **stops on 403** rather than retrying — the right answer to being refused is to
  stop asking
* text only; images, video and other media are never downloaded
* a transparent project User-Agent, with a contact address only if you set
  `SCRAPER_CONTACT`
* post text is never printed to the terminal, and exceptions are reduced to their
  type so a traceback cannot carry a local path into a log

**Scraping and redistribution are different questions.** That this fetches public
pages says nothing about your right to republish what it returns. See
`DATA_POLICY.md`.

    SCRAPER_CONTACT="you@example.org" python scripts/collect_truth_social.py --limit 500
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
DEST_DIR = Path(os.environ.get("ALT_DATA_SOURCE", ROOT / "data" / "raw"))

ALLOWED_HOST = "trumpstruth.org"
BASE = f"https://{ALLOWED_HOST}"
CONTACT = os.environ.get("SCRAPER_CONTACT", "")
HEADERS = {
    "User-Agent": "spy-next-day-signal-research/1.0 (academic research"
                  + (f"; {CONTACT}" if CONTACT else "") + ")"
}
SLEEP = 1.0
TIMEOUT = 30
MAX_RETRIES = 3
START_DATE = "2024-07-13"
PER_PAGE = 100

FIELDS = ["status_id", "archive_url", "original_truthsocial_url",
          "created_at_raw", "text"]


def same_host(url: str) -> bool:
    host = requests.utils.urlparse(url).hostname or ""
    return host == ALLOWED_HOST or host.endswith("." + ALLOWED_HOST)


def get(session: requests.Session, url: str) -> requests.Response | None:
    """One polite request. Returns None when the page should be skipped."""
    if not same_host(url):
        raise SystemExit(f"refusing to request a host other than {ALLOWED_HOST}")
    for attempt in range(MAX_RETRIES):
        try:
            r = session.get(url, headers=HEADERS, timeout=TIMEOUT)
        except Exception as exc:                                  # noqa: BLE001
            print(f"  {type(exc).__name__}, attempt {attempt + 1}", file=sys.stderr)
            time.sleep(SLEEP * (attempt + 2))
            continue
        if not same_host(r.url):
            print("  redirected off the archive; skipping", file=sys.stderr)
            return None
        if r.status_code == 403:
            raise SystemExit("403 from the archive. Stopping: being refused is an "
                             "answer, not an obstacle.")
        if r.status_code == 429:
            wait = min(int(r.headers.get("Retry-After", "60")), 300)
            print(f"  rate limited; waiting {wait}s", file=sys.stderr)
            time.sleep(wait)
            continue
        if r.status_code >= 500:
            time.sleep(SLEEP * (attempt + 2))
            continue
        r.raise_for_status()
        return r
    return None


def discover(session: requests.Session, max_pages: int) -> list[str]:
    """Status URLs from the archive's own search pages, newest first."""
    seen: set[str] = set()
    for page in range(1, max_pages + 1):
        url = (f"{BASE}/search?query=&start_date={START_DATE}&end_date="
               f"&sort=date_desc&removed=include&per_page={PER_PAGE}"
               + (f"&page={page}" if page > 1 else ""))
        r = get(session, url)
        if r is None:
            break
        found = {BASE + a["href"] if a["href"].startswith("/") else a["href"]
                 for a in BeautifulSoup(r.text, "lxml").find_all("a", href=True)
                 if "/statuses/" in a["href"]}
        new = found - seen
        if not new:
            print(f"  page {page}: nothing new, stopping")
            break
        seen |= new
        print(f"  page {page}: {len(new)} new, {len(seen)} total", flush=True)
        time.sleep(SLEEP)
    return sorted(seen)


def parse(html: str, url: str) -> dict:
    """Fields by element, not by matching patterns against a flattened page.

    The body is `div.status__content`. Where the element is absent or empty, the
    post carried no text; that is a fact about the post rather than a parse failure,
    and the two are not merged.
    """
    soup = BeautifulSoup(html, "lxml")
    content = soup.select_one("div.status__content")

    def value_of(selector: str) -> str:
        el = soup.select_one(selector)
        return el.get_text(" ", strip=True) if el else ""

    original = ""
    link = soup.select_one("a.status__external-link")
    if link and link.get("href", "").startswith("https://truthsocial.com/"):
        original = link["href"]

    date_cell = ""
    for row in soup.select("table.status-details-table tr"):
        cells = row.find_all("td")
        if len(cells) == 2 and "Original Post Date" in cells[0].get_text():
            date_cell = cells[1].get_text(" ", strip=True)
            break

    match = re.search(r"/statuses/(\d+)", url)
    return {
        "status_id": match.group(1) if match else "",
        "archive_url": url,
        "original_truthsocial_url": original,
        "created_at_raw": date_cell,
        "text": content.get_text(" ", strip=True) if content else "",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=None, help="stop after N posts")
    ap.add_argument("--max-pages", type=int, default=1000)
    ap.add_argument("--out", default="trump_archive_full_cleaned.csv")
    args = ap.parse_args()

    DEST_DIR.mkdir(parents=True, exist_ok=True)
    dest = DEST_DIR / args.out
    if not CONTACT:
        print("note: SCRAPER_CONTACT is unset, so the User-Agent carries no address.\n"
              "      Setting it lets the site operator reach you instead of blocking.\n")

    session = requests.Session()
    print(f"discovering status URLs from {BASE}")
    urls = discover(session, args.max_pages)
    if args.limit:
        urls = urls[:args.limit]
    print(f"\nfetching {len(urls)} posts at {SLEEP:.1f}s intervals")

    done = set()
    if dest.exists():
        with dest.open(encoding="utf-8", newline="") as fh:
            done = {row["archive_url"] for row in csv.DictReader(fh)}
        print(f"resuming: {len(done)} already collected")

    with dest.open("a", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        if not done:
            writer.writeheader()
        for n, url in enumerate(u for u in urls if u not in done):
            r = get(session, url)
            if r is not None:
                writer.writerow(parse(r.text, url))
                fh.flush()
            # Counts only. Printing the text would put the corpus in a terminal log.
            if (n + 1) % 25 == 0:
                print(f"  {n + 1} fetched", flush=True)
            time.sleep(SLEEP)

    print(f"\nwritten to {dest.name} in {DEST_DIR}")
    print(f"collected {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    print("\nThis directory is gitignored. The corpus is not redistributed with this")
    print("repository; see DATA_POLICY.md before republishing any of it.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
