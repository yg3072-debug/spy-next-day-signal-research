# Data Policy

What this study uses, what travels with the repository, what does not, and how to
obtain the rest yourself.

The distinction that organises all of it: **reading a source and republishing it are
separate acts.** This project reads public pages and vendor series; it republishes
neither. What it publishes is the code that consumes them, the identifiers needed to
confirm you hold the same inputs, and every result computed from them.

---

## 1. What the study uses

| Input | Source | Role |
|---|---|---|
| Daily OHLCV for SPY and reference series | Yahoo Finance | the confirmatory feature set and target |
| Treasury constant-maturity rates | Federal Reserve Board H.15 (originally via FRED) | financing, carry, the risk-free leg |
| NYSE session calendar | `pandas_market_calendars` | session boundaries, early closes |
| Truth Social posts | the public archive | exploratory NLP layer only |
| News headlines | a published dataset | exploratory NLP layer only |
| Loughran–McDonald financial lexicon | the authors' distribution | sentiment scoring |

**The confirmatory procedure uses no text data.** Both corpora belong to the
exploratory layer and cannot change the confirmatory result.

---

## 2. Distributed with this repository

| | |
|---|---|
| All research code | `src/`, `scripts/` |
| The frozen configuration | `config/p1.yaml` and its digest |
| Treasury rates | `data/treasury_rates_h15_*.csv` — a US federal government work, public domain, redistributable with attribution |
| Session-level NLP aggregates | `data/alt/truth_social_session_features.csv`, `data/alt/news_session_features.csv` |
| Provenance records | source, date range, row counts, processing rules, SHA-256 of each input |
| Every result, statistic and report | `results/`, `reports/`, `docs/` |
| A synthetic market fixture | `tests/fixtures/market_inputs_synthetic.csv`, so the suite runs without vendor data |

---

## 3. Not distributed

| | Why |
|---|---|
| **The market snapshot** `market_inputs_2026-08-21.csv` and its manifest | Yahoo's terms restrict redistribution of their data |
| The E21 second vintage | same source, same restriction |
| Truth Social post text, per post | third-party content; reading it is not a right to republish it |
| News headline text, per headline | likewise |
| Video transcripts, link-card titles and descriptions | archive-generated or fetched text, third-party either way |
| Images, video, any media | never downloaded at all |
| Per-record identifiers | an identifier list is a **key** to the corpus: anyone holding it can refetch every record |
| The Loughran–McDonald dictionary | licensed for academic use; commercial use needs the authors' permission |

**Identifiers are not a lesser form of text.** A file that dropped the words and kept
the record ids would still hand over the corpus, one request at a time. That is why
`results/empty_post_diagnosis_summary.json` holds length statistics with no ids
rather than a per-record file with the words stripped out.

**The dictionary is fetched, not vendored.** `scripts/fetch_lexicon.py` retrieves it
and verifies its SHA-256. Reproducibility needs the same bytes and a way to check
them; it does not need this repository to become a mirror.

---

## 4. The market snapshot

`data/market_inputs_2026-08-21.csv` is the input the confirmatory run used. **It is
not distributed with this repository.**

What is published instead:

```
filename    market_inputs_2026-08-21.csv
SHA-256     9b337ca75f8d077963448853e97542fab1258ab5b6dd289debec14061012b13a
coverage    2,926 NYSE sessions, 2015-01-02 to 2026-08-21, 23 early closes
schema      documented in docs/data_availability.md
```

plus the code that produced it (`scripts/freeze_market_data.py`), the code that
verifies it (`scripts/verify_hashes.py`), and every result computed from it.

**What you can do without it:** run the full test suite, read and audit all of the
code, review every published result, and rebuild the financing fields from public
Board H.15 data — `scripts/verify_financing_from_board.py` does exactly that and
checks them against what the study reported.

**What you cannot do without it:** reproduce P1 byte for byte. That requires the same
bytes, and only the vendor can supply them.

**A later download is not the same thing.** Yahoo revises adjusted history after
corporate actions, so `freeze_market_data.py` without `--verify` produces a *new data
vintage* — a different dataset and a new research run, not a reproduction. The study
measured this deliberately: exploratory specification E21 re-downloaded the same
window and compared field by field, and the differences are recorded in
`results/e21_vintage_diff.json`.

`verify_hashes.py` reports the snapshot as `NOT VERIFIED` on a public clone and
checks only that every file recording its identifier records the same one. Supply the
CSV and its manifest and the same command upgrades to a real byte check.

---

## 5. Obtaining the inputs yourself

**Market data.** Acquire a snapshot however your own licence permits and place it in
`data/`. `scripts/freeze_market_data.py` documents the schema and the fill rules.

**Treasury rates.** Already committed, and `scripts/fetch_treasury_rates.py`
re-downloads them from the Board's H.15 release. Public domain.

**The alternative-data layer.** The whole chain is public; only its input is not:

```
public web pages
  -> scripts/collect_truth_social.py     fetch: one host, read-only, rate-limited
  -> data/raw/*.csv                      local, gitignored
  -> scripts/freeze_alt_data.py          encoding, timezone, NYSE session mapping
  -> src/altdata.py                      Loughran-McDonald counts, topic counts
  -> data/alt/*_session_features.csv     committed
```

`docs/scraping_notes.md` records each source's identity, row count and checksum.
Obtain the headline dataset, place it in `data/raw/`, and `freeze_alt_data.py`
reproduces the committed aggregates byte for byte.

Raw data lives in directories `.gitignore` excludes:

```
data/raw/      the two text corpora
vendor/        the Loughran-McDonald dictionary
local_data/    anything else you keep alongside
```

`ALT_DATA_SOURCE` and `LM_DICTIONARY` override those locations. The scripts read from
them and write nothing committable.

---

## 6. How the aggregates are produced

Text is mapped onto trading sessions before anything is counted. The session bucket
is `(close_{t-1}, close_t]` in America/New_York — left-open, right-closed — so a
document can only enter the session that was still open when it appeared. Early
closes use the actual close. The mapping is tested directly, including both sides of
a daylight-saving transition and the 13:00 close on half days.

Within a session the layer counts: documents, tokens, Loughran–McDonald category
rates (negative, positive, uncertainty, litigious, modal, constraining) and bespoke
topic keyword rates. The result is 19–20 numeric columns per trading day.

**The published aggregates contain no source text, record identifiers or URLs, and do
not contain sufficient information to reconstruct the underlying source documents.**

Automated tests enforce this rather than trusting it. A tracked CSV may not carry a
column named `text`, `body`, `headline`, `title`, `transcript`, `video_transcript`,
`card_title`, `card_description`, `status_id`, `archive_url` or similar, and may not
contain a free-text cell over 200 characters. The rules are verified by deliberately
committing a poisoned file and confirming the suite fails — a guard that has never
been seen to fire is not known to work.

---

## 7. Collection conduct

`scripts/collect_truth_social.py`:

- restricts itself to **one host**, and re-checks the host after every redirect
- issues **read-only GET** requests
- **supplies no user credentials, authentication tokens, or user-provided
  authentication cookies** — it uses a `requests.Session`, so a server may set an
  ordinary session cookie of its own, which is not the same thing
- makes **no attempt to bypass access control or bot detection**
- requests **at most once per second**
- honours **`Retry-After`**
- **stops on 403** rather than retrying
- **downloads no media**
- identifies itself with a project User-Agent, adding a contact address only if you
  set `SCRAPER_CONTACT` in your environment
- never prints fetched text to a terminal, and reduces exceptions to their type so a
  traceback cannot carry a local path into a log

As of 2026-08-25 no Terms of Service link was found on the archive's homepage, About
page, FAQ, or the common policy paths (`/terms`, `/terms-of-service`, `/privacy`,
`/privacy-policy`, `/legal` all return 404). The current `robots.txt` declares no
disallowed paths.

**This is not legal permission and does not grant redistribution rights.** An empty
`Disallow` is the absence of a stated restriction, not a grant. The absence of a
published policy is likewise not consent — it means there is nothing to read, which
is a weaker position than having read something permissive. This is precisely why the
repository distributes aggregates and not documents.

---

## 8. If you use this

You are responsible for your own compliance. Before collecting or republishing
anything:

- read the target site's terms of service, which this project did not
- check `robots.txt` yourself, at the time you run it
- consider whether the content is copyrighted, and by whom
- consider whether redistribution is yours to authorise — usually it is not

**The MIT licence covers this project's code only.** It does not cover, and cannot
grant rights to, the Loughran–McDonald dictionary, the news headline dataset, Truth
Social posts, or any market data obtained through this code.
