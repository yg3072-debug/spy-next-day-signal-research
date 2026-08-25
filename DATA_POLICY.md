# Data Policy

What this repository distributes, what it does not, and why the difference is not
a technicality.

---

## The rule

**Scraping and redistribution are different questions.** Fetching a public page and
republishing what it returns are separate acts, governed by separate considerations,
and the answer to one does not settle the other. This repository fetches public
pages and does **not** republish their contents.

Concretely: the study consumes session-level aggregates — word counts, sentiment
ratios, document counts per trading day. Those aggregates are distributed. The
documents they were computed from are not.

---

## Distributed

| | |
|---|---|
| Collection and cleaning code | `scripts/collect_truth_social.py`, `scripts/freeze_alt_data.py`, `src/altdata.py` |
| Provenance | source, date range, row counts, processing rules, SHA-256 of each raw input |
| Session-level NLP aggregates | `data/alt/truth_social_session_features.csv`, `data/alt/news_session_features.csv` |
| The market snapshot and modelling inputs | `data/market_inputs_*.csv` |
| Every result, statistic and report | `results/`, `reports/` |
| Commit authorship | name and email, deliberately retained — see `PRIVACY.md` |
| Citations and source links | the Loughran–McDonald paper, the archive's own address |

The aggregates are **not reversible**. A count of negative words in a session does
not reconstruct the sentences, and no combination of the committed columns
reconstructs a document.

---

## Not distributed

| | |
|---|---|
| Truth Social post text, per post | the corpus itself |
| News headline text, per headline | likewise |
| Video transcripts | archive-generated speech, third-party content either way |
| Link-card titles and descriptions | fetched text |
| Images, video, any media | never downloaded at all |
| Per-record diagnostics carrying post identifiers | an identifier list is a **key** to the corpus: anyone holding it can refetch every record |
| The Loughran–McDonald dictionary | licensed for academic use, commercial use needs permission |

The last two deserve a note each.

**Identifiers are not a lesser form of text.** A file that dropped the words but
kept the status ids would still hand over the corpus, one request at a time. That
is why `results/empty_post_diagnosis_summary.json` is an aggregate with no ids
rather than a per-record file with the text removed.

**The dictionary is fetched, not vendored.** `scripts/fetch_lexicon.py` retrieves it
and verifies its SHA-256. Reproducibility needs the same bytes and a way to check
them, which a recorded digest provides; it does not need this repository to become
a mirror.

---

## Where raw data lives

Locally, in directories `.gitignore` excludes:

```
data/raw/      the two text corpora
vendor/        the Loughran-McDonald dictionary
local_data/    anything else you keep alongside
```

`ALT_DATA_SOURCE` and `LM_DICTIONARY` override those locations. The scripts read
from them and write nothing committable.

Automated tests enforce this rather than trusting it. A tracked CSV may not carry a
column named `text`, `body`, `headline`, `title`, `transcript`, `video_transcript`,
`card_title`, `card_description`, `status_id`, `archive_url` or similar, and may not
contain a cell over 200 characters. Both rules are verified by deliberately
committing a poisoned file and confirming the suite fails.

---

## Reproducing the alternative-data layer

The full chain is public. Only its input is not:

```
public web pages
  -> scripts/collect_truth_social.py     fetch, one host, read-only, rate-limited
  -> data/raw/*.csv                      local, gitignored
  -> scripts/freeze_alt_data.py          encoding, timezone, NYSE session mapping
  -> src/altdata.py                      Loughran-McDonald counts, topic counts
  -> data/alt/*_session_features.csv     committed
```

The news headline corpus is a published dataset; `docs/scraping_notes.md` records
its identity, row count and checksum. Obtain it, put it in `data/raw/`, and
`freeze_alt_data.py` reproduces the committed aggregates byte for byte.

---

## Collection conduct

`scripts/collect_truth_social.py` restricts itself to one host and re-checks it
after every redirect; **supplies no user credentials, authentication tokens, or
user-provided authentication cookies** — it uses a `requests.Session`, so a server
may set an ordinary session cookie of its own, which is not the same thing and is
worth distinguishing; makes no attempt to bypass access control or bot detection; requests once per second; honours
`Retry-After`; **stops on 403** rather than retrying; downloads no media; identifies
itself with a project User-Agent and adds a contact address only if you set
`SCRAPER_CONTACT`; never prints fetched text to a terminal; and reduces exceptions
to their type so a traceback cannot carry a local path into a log.

As of 2026-08-25, no Terms of Service link was found on the homepage, About page,
FAQ, or common policy paths (`/terms`, `/terms-of-service`, `/privacy`,
`/privacy-policy`, `/legal` all return 404). The current `robots.txt` declares no
disallowed paths.

**This is not legal permission and does not grant redistribution rights.** An empty
`Disallow` is the absence of a stated restriction, not a grant — an earlier draft of
this document called it an "explicit allowance", which overstates what a
`robots.txt` can convey. The absence of a published policy is likewise not consent;
it means there is nothing to read, which is a weaker position than having read
something permissive.

---

## If you use this

You are responsible for your own compliance. Before collecting or republishing
anything:

- read the target site's terms of service, which this project did not
- check `robots.txt` yourself, at the time you run it
- consider whether the content is copyrighted, and by whom
- consider whether redistribution is yours to authorise — usually it is not

**The MIT licence covers this project's code only.** It does not cover, and cannot
grant rights to, the Loughran–McDonald dictionary, the news headline dataset,
Truth Social posts, or any market data obtained through it.

---

## Outstanding

**Market data licensing is unresolved and is listed here rather than acted on.** The
market snapshot in `data/` was obtained through Yahoo Finance and FRED. FRED's
series are US government publications and carry no meaningful restriction. Yahoo's
terms restrict redistribution of their data, and this repository commits a snapshot
derived from it, which is what makes the confirmatory result reproducible.

This has not been changed as part of the alternative-data cleanup, deliberately:
removing the snapshot would break P1's reproducibility, which is the repository's
central claim, and the two questions should not be settled by the same commit
without a decision being made about the second one. **It remains open.**
