# Data

What is here, what is not, and where the missing pieces come from.

## Committed

```
treasury_rates_h15_2026-08-25.csv        Federal Reserve Board H.15 rates, public domain
treasury_rates_h15_2026-08-25.manifest.json   its SHA-256, source URL and citation
alt/truth_social_session_features.csv    per-session NLP aggregates
alt/news_session_features.csv            per-session NLP aggregates
alt/alt_data.manifest.json          source checksums, row counts, audit counts
```

The `alt/` feature tables hold counts and ratios per trading day: document counts,
token counts, Loughran-McDonald category rates, topic keyword rates. **No document
text, no identifiers, no URLs.** They are not reversible — a count of negative words
in a session does not reconstruct the sentences.

## Not committed

```
market_inputs_2026-08-21.csv        the frozen market snapshot, 2,926 NYSE sessions
market_inputs_2026-08-21.manifest.json   its SHA-256, coverage and fill accounting
vintage_e21/                        a second download of the same window (E21)
raw/          the two text corpora, gitignored
../vendor/    the Loughran-McDonald dictionary, gitignored
```

`market_inputs_2026-08-21.csv` is the filename of the historical frozen input — the file
P1 actually ran on. **It is not distributed here**, because the prices come from a vendor
whose terms do not permit redistribution. Its SHA-256 is recorded in `config/p1.yaml`,
`docs/freeze_record.md` and four other places, so a reader who obtains the same vintage
independently can confirm they hold the same bytes. A full re-run requires you to acquire
market data yourself, legally.

Whether to redistribute a publisher's content is that publisher's decision. See
`../DATA_POLICY.md`.

`tests/fixtures/market_inputs_synthetic.csv` is a seeded random walk with the same schema.
It exists so the test suite runs without vendor data. It is **not** the frozen P1 input,
and `load_snapshot()` refuses to fall back to it.

To rebuild the aggregates from raw:

```bash
python scripts/fetch_lexicon.py             # dictionary, checksum-verified
python scripts/collect_truth_social.py      # or supply your own copy
# place the news headline dataset in data/raw/ as well
python scripts/freeze_alt_data.py           # regenerates alt/*_session_features.csv
python scripts/freeze_alt_data.py --verify  # confirms they match the committed ones
```

`docs/scraping_notes.md` records each source's identity, row count and SHA-256, so a
reader who obtains the same files can confirm they have the same bytes.

## Calendar columns

`session_minutes` and `is_half_day` are generated from the NYSE trading-session
rules published by `pandas_market_calendars` (5.4.0, MIT licence), as
`market_close - market_open` in minutes. They are not vendor data.

## The market snapshot

Committed, because the confirmatory result is not reproducible without it. Its
licensing is an open question recorded in `../DATA_POLICY.md` rather than settled
here.
