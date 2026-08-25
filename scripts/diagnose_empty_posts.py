"""Resolve what the archive's empty text rows actually are, without keeping the text.

The collector that produced the frozen snapshot extracts a post body by matching
regular expressions against the whole page flattened to one string. When no pattern
matches it writes nothing, so an empty field conflates two different things: a post
that carried no text, and a post whose text the extractor missed.

The archive's markup is structured, so the question is answerable directly rather
than by inference. The post body is `div.status__content`; if that element is absent
or empty, the post had no text, and no regular expression is involved in saying so.

**Nothing fetched is retained.** Only lengths are extracted, and only an aggregate is
written. Whether a body exists is answerable from a count, so the words are never
needed -- and a per-record file would carry status identifiers, which are a
reconstruction key for a corpus this project deliberately does not distribute.

This samples rather than re-scrapes. Resolving the ambiguity needs a proportion, and
a few hundred pages estimate a proportion about as well as fourteen thousand would.

**Non-empty rows are sampled too, as a control.** A reader that disagreed with the
archive where the archive succeeded would be measuring itself, not the source.

Requests are read-only, rate-limited, and send no credentials of any kind. The
crawler identifies itself as this project; set `SCRAPER_CONTACT` to add an address
if you want the site operator to be able to reach you.

    python scripts/diagnose_empty_posts.py --empty 150 --nonempty 50
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from datetime import date
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get("ALT_DATA_SOURCE", ROOT / "data" / "raw")) \
    / "trump_archive_full_cleaned.csv"

ALLOWED_HOST = "trumpstruth.org"
BASE = f"https://{ALLOWED_HOST}/statuses"
CONTACT = os.environ.get("SCRAPER_CONTACT", "")
HEADERS = {
    "User-Agent": "spy-next-day-signal-research/1.0 (academic research"
                  + (f"; {CONTACT}" if CONTACT else "") + ")"
}
SLEEP = 1.0
TIMEOUT = 30
SEED = 20260824


def extract(html: str) -> dict:
    """Lengths of what the page holds, by element rather than by pattern.

    `status__content` is the post body. The other fields are text that exists on the
    page but is not the post: a link preview's title, and a transcript the archive
    generates for video attachments. Each is measured and none is kept -- a
    transcript is machine-produced speech rather than something the author wrote, and
    it is third-party content either way.
    """
    soup = BeautifulSoup(html, "lxml")

    def length_of(selector: str) -> int:
        el = soup.select_one(selector)
        return len(el.get_text(" ", strip=True).strip()) if el else 0

    content = soup.select_one("div.status__content")
    attachments = soup.select_one("div.status__attachments")
    kinds = []
    if attachments:
        for el in attachments.select("[class*=status-attachment--]"):
            kinds += [c.split("--", 1)[1] for c in el.get("class", [])
                      if "status-attachment--" in c]

    body = content.get_text(" ", strip=True).strip() if content else ""
    return {
        "body_element_present": content is not None,
        "body_chars": len(body),
        "attachment_kinds": ",".join(sorted(set(kinds))),
        "card_title_chars": length_of("div.status-card__title"),
        "card_description_chars": length_of("div.status-card__description"),
        "video_transcript_chars": length_of("div.status-details-attachment__text"),
        "is_repost": bool(soup.select_one("div.status__body div.status-info")),
    }


def fetch(session: requests.Session, status_id) -> tuple[str | None, str]:
    """One read-only request, with the host checked after any redirect.

    A redirect leaving the archive is treated as a failure rather than followed into
    somewhere this was never authorised to read. A 403 stops the run outright: the
    right response to being refused is to stop asking.
    """
    try:
        r = session.get(f"{BASE}/{status_id}", headers=HEADERS, timeout=TIMEOUT)
        host = requests.utils.urlparse(r.url).hostname or ""
        if not (host == ALLOWED_HOST or host.endswith("." + ALLOWED_HOST)):
            return None, f"redirected off {ALLOWED_HOST}"
        if r.status_code == 403:
            raise SystemExit("403 from the archive: stopping rather than retrying.")
        if r.status_code == 429:
            wait = min(int(r.headers.get("Retry-After", "60")), 300)
            time.sleep(wait)
            return None, "rate limited"
        r.raise_for_status()
        return r.text, ""
    except SystemExit:
        raise
    except Exception as exc:                                      # noqa: BLE001
        # The exception type only. A message or traceback can carry local paths.
        return None, type(exc).__name__


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--empty", type=int, default=150)
    ap.add_argument("--nonempty", type=int, default=50)
    ap.add_argument("--out", default="results/empty_post_diagnosis_summary.json",
                    help="aggregate output; no per-record file is written or kept")
    args = ap.parse_args()

    if not SOURCE.exists():
        print(f"{SOURCE.name} not found. The raw archive is not distributed with "
              "this repository; set ALT_DATA_SOURCE to the directory holding it.",
              file=sys.stderr)
        return 1

    frame = pd.read_csv(SOURCE)
    text = frame.text.fillna("").astype(str).str.strip()
    is_empty = (text == "") | (text.str.lower() == "nan")

    rng = random.Random(SEED)
    empty_ids = rng.sample(frame.loc[is_empty, "status_id"].tolist(),
                           min(args.empty, int(is_empty.sum())))
    full_ids = rng.sample(frame.loc[~is_empty, "status_id"].tolist(),
                          min(args.nonempty, int((~is_empty).sum())))

    todo = [(i, True) for i in empty_ids] + [(i, False) for i in full_ids]
    print(f"sampling {len(todo)} pages at {SLEEP:.1f}s intervals "
          f"({len(empty_ids)} empty, {len(full_ids)} non-empty control)")

    rows = []
    session = requests.Session()
    for n, (status_id, was_empty) in enumerate(todo, 1):
        html, error = fetch(session, status_id)
        row = extract(html) if html else {}
        row.update({"was_empty_in_archive": was_empty, "error": error})
        rows.append(row)
        if n % 25 == 0:
            print(f"  {n}/{len(todo)}", flush=True)
        time.sleep(SLEEP)

    out = pd.DataFrame(rows).fillna({"error": ""})
    ok = out[out.error == ""]
    sample = ok[ok.was_empty_in_archive]
    control = ok[~ok.was_empty_in_archive]
    kinds = sample.attachment_kinds.fillna("none").replace("", "none")

    def share(mask) -> float | None:
        return round(float(mask.mean()), 4) if len(mask) else None

    summary = {
        "purpose": ("Whether rows with an empty text field in the archive are "
                    "text-free posts or extraction misses."),
        "diagnostic_date": date.today().isoformat(),
        "seed": SEED,
        "sample_size_requested": int(len(out)),
        "successful_requests": int(len(ok)),
        "error_count": int((out.error != "").sum()),
        "control_group_size": int(len(control)),
        "control_body_found_share": share(control.body_chars > 0),
        "sample_group_size": int(len(sample)),
        "sample_with_body_text_count": int((sample.body_chars > 0).sum()),
        "sample_without_body_text_count": int((sample.body_chars == 0).sum()),
        "extraction_miss_share": share(sample.body_chars > 0),
        "attachment_counts": {str(k): int(v) for k, v in kinds.value_counts().items()},
        "transcript_present_count": int((sample.video_transcript_chars > 0).sum()),
        "transcript_present_share": share(sample.video_transcript_chars > 0),
        "link_card_present_share": share(sample.card_title_chars > 0),
        "note": ("Aggregate only. No post identifiers, URLs, body text, transcripts "
                 "or media are retained."),
    }

    dest = ROOT / args.out
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    miss = summary["extraction_miss_share"]
    print(f"\nfetched {len(ok)} of {len(out)}; {summary['error_count']} failed\n")
    print("CONTROL - rows the archive did record text for")
    print(f"  the structural reader also finds a body: "
          f"{summary['control_body_found_share']:.1%} of {len(control)}")
    print(f"\nSAMPLE - rows the archive recorded as empty (n = {len(sample)})")
    print(f"  carries text the archive missed: {miss:.1%}")
    print(f"  genuinely text-free:             {1 - miss:.1%}")
    print(f"  attachments: {summary['attachment_counts']}")
    print(f"  carry a transcript: {summary['transcript_present_share']:.1%}")
    print(f"\nwritten to {dest.relative_to(ROOT)}")
    print("Per-record rows are never persisted: an identifier list is a "
          "reconstruction key")
    print("for a corpus this project does not distribute.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
