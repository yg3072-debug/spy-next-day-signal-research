"""Resolve what the archive's empty `text` rows actually are.

The collector that produced the frozen snapshot extracts a post body by matching
regular expressions against the whole page flattened to one string. When no pattern
matches it writes nothing, so an empty field conflates two different things: a post
that carried no text, and a post whose text the extractor missed. 26.5% of rows are
empty and `docs/scraping_notes.md` can only call that an upper bound.

The archive's markup is structured, so the question is answerable directly rather
than by inference. The post body is `div.status__content`; if that element exists
and is empty, the post had no text, and no regular expression is involved in
saying so.

This samples rather than re-scrapes. Resolving the ambiguity needs a proportion, and
a few hundred pages estimate a proportion about as well as fourteen thousand would.
A full re-scrape would cost four hours of requests to move the smallest detectable
Sharpe difference on this source from 2.40 to 2.16, which changes no conclusion,
so it is not done.

**Non-empty rows are sampled too, as a control.** A new extractor that disagreed
with the old one where the old one succeeded would be measuring itself, not the
archive.

    python scripts/diagnose_empty_posts.py --empty 120 --nonempty 40
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get("ALT_DATA_SOURCE", ROOT / "data" / "raw")) \
    / "trump_archive_full_cleaned.csv"
BASE = "https://trumpstruth.org/statuses"
CONTACT = os.environ.get("SCRAPER_CONTACT", "")
HEADERS = {"User-Agent": "Mozilla/5.0 (academic research"
                         + (f"; {CONTACT}" if CONTACT else "") + ")"}
SLEEP = 1.0          # the site's robots.txt permits crawling; this is courtesy
SEED = 20260824


def extract(html: str) -> dict:
    """Everything the page says, by element rather than by pattern.

    `status__content` is the post body. The remaining fields are text that exists on
    the page but is not the post: a link preview's title, and a transcript the
    archive generates for video attachments. The old extractor could see none of
    them, and they are recorded separately rather than merged into the body, since
    a transcript is not something the author wrote.

    Only lengths are returned. Whether a body exists is answerable from a count, and
    keeping the words would redistribute content this project has decided not to.
    """
    soup = BeautifulSoup(html, "lxml")

    def text_of(selector: str) -> str:
        el = soup.select_one(selector)
        return el.get_text(" ", strip=True) if el else ""

    content_el = soup.select_one("div.status__content")
    attachments = soup.select_one("div.status__attachments")
    kinds = []
    if attachments:
        for el in attachments.select("[class*=status-attachment--]"):
            kinds += [c.split("--", 1)[1] for c in el.get("class", [])
                      if "status-attachment--" in c]

    # Lengths, not words. The question is whether a body exists, and the answer is
    # a count; retaining the text would redistribute third-party content that the
    # rest of this project deliberately does not commit, for no analytical gain.
    body = content_el.get_text(" ", strip=True) if content_el else ""
    return {
        "body_element_present": content_el is not None,
        "body_chars": len(body.strip()),
        "attachment_kinds": ",".join(sorted(set(kinds))),
        "card_title_chars": len(text_of("div.status-card__title").strip()),
        "card_description_chars": len(text_of("div.status-card__description").strip()),
        "video_transcript_chars": len(text_of("div.status-details-attachment__text").strip()),
        "is_repost": bool(soup.select_one("div.status__body div.status-info")),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--empty", type=int, default=120)
    ap.add_argument("--nonempty", type=int, default=40)
    ap.add_argument("--out", default="results/empty_post_diagnosis.csv")
    args = ap.parse_args()

    frame = pd.read_csv(SOURCE)
    text = frame.text.fillna("").astype(str).str.strip()
    is_empty = (text == "") | (text.str.lower() == "nan")

    rng = random.Random(SEED)
    empty_ids = rng.sample(frame.loc[is_empty, "status_id"].tolist(),
                           min(args.empty, int(is_empty.sum())))
    full_ids = rng.sample(frame.loc[~is_empty, "status_id"].tolist(),
                          min(args.nonempty, int((~is_empty).sum())))
    old_text = dict(zip(frame.status_id, text))

    rows = []
    session = requests.Session()
    todo = [(i, True) for i in empty_ids] + [(i, False) for i in full_ids]
    print(f"sampling {len(todo)} pages at {SLEEP:.1f}s intervals "
          f"({len(empty_ids)} empty, {len(full_ids)} non-empty control)\n")

    for n, (status_id, was_empty) in enumerate(todo, 1):
        try:
            r = session.get(f"{BASE}/{status_id}", headers=HEADERS, timeout=30)
            r.raise_for_status()
            got = extract(r.text)
            got.update({"status_id": status_id, "was_empty_in_snapshot": was_empty,
                        "old_text_len": len(old_text.get(status_id, "")), "error": ""})
        except Exception as exc:                                  # noqa: BLE001
            got = {"status_id": status_id, "was_empty_in_snapshot": was_empty,
                   "old_text_len": len(old_text.get(status_id, "")),
                   "error": f"{type(exc).__name__}: {exc}"}
        rows.append(got)
        if n % 20 == 0:
            print(f"  {n}/{len(todo)}", flush=True)
        time.sleep(SLEEP)

    out = pd.DataFrame(rows)
    dest = ROOT / args.out
    dest.parent.mkdir(parents=True, exist_ok=True)
    out.to_csv(dest, index=False)

    ok = out[out.error == ""]
    print(f"\nfetched {len(ok)} of {len(out)}; {int((out.error != '').sum())} failed\n")

    control = ok[~ok.was_empty_in_snapshot]
    if len(control):
        agree = (control.body_chars > 0).mean()
        print("CONTROL — rows the old extractor did find text for")
        print(f"  the structural extractor also finds a body: {agree:.1%} of {len(control)}")
        if agree < 0.95:
            print("  WARNING: disagreement here means the new extractor is the problem.")

    sample = ok[ok.was_empty_in_snapshot]
    if len(sample):
        has_body = sample.body_chars > 0
        n = len(sample)
        share = has_body.mean()
        se = (share * (1 - share) / n) ** 0.5
        print(f"\nSAMPLE — rows the old extractor returned nothing for  (n = {n})")
        # A page either has no body element at all or has an empty one; both mean
        # the post carried no typed text, so they are reported as one number.
        print(f"  carries typed text the old extractor missed: {share:.1%}"
              f" +/- {1.96 * se:.1%}")
        print(f"  genuinely text-free:                        {1 - share:.1%}")
        print(f"    (body element absent on {1 - sample.body_element_present.mean():.1%},"
              f" present but empty on {sample.body_element_present.mean():.1%})")
        print(f"\n  attachment kinds among them: "
              f"{sample.attachment_kinds.replace('', 'none').value_counts().head(5).to_dict()}")
        print(f"  carry a link-card title:     {(sample.card_title_chars > 0).mean():.1%}")
        print(f"  carry a video transcript:    "
              f"{(sample.video_transcript_chars > 0).mean():.1%}")

        total_empty = int(is_empty.sum())
        print(f"\n  Scaled to all {total_empty:,} empty rows: roughly "
              f"{share * total_empty:,.0f} are extraction misses and "
              f"{(1 - share) * total_empty:,.0f} are genuinely text-free.")

    (dest.with_suffix(".json")).write_text(json.dumps({
        "sampled": len(out), "fetched": len(ok), "seed": SEED,
        "empty_sampled": int(len(sample)), "control_sampled": int(len(control)),
    }, indent=2), encoding="utf-8")
    print(f"\nwritten to {dest.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
