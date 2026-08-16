# Exploratory Trump NLP extension

This directory contains the frozen, derived inputs for a separate text-feature
ablation. It does **not** alter the canonical LightGBM model or its protected
206-session holdout result.

## Source and scope

The original collection used the independent public archive at
[`trumpstruth.org`](https://trumpstruth.org/) to locate archived pages for posts
published by Donald Trump's Truth Social account. The supplied archive covered
July 13, 2024 through April 23, 2026:

- 14,145 unique archive records
- 10,396 records with usable text after cleaning
- 646 calendar rows in the lagged feature table
- 446 NYSE modeling sessions in the controlled comparison window

The collector is an HTML archive reader, not a Truth Social API client. Website
structure, availability, and terms can change. The complete post corpus and the
5.4 MB text-cleaning preview are intentionally not committed because they
contain third-party text and are not required to run the model comparison.

## Committed files

- `trump_nlp_features_lag1.csv`: frozen daily counts, keyword-topic scores, and
  market-related share, shifted by one calendar day before market alignment
- `trump_nlp_modeling_table.csv`: the 21 selected market features, targets, and
  the lagged text features on the original 1,027-session modeling calendar
- `manifest.json`: row counts, date coverage, provenance, and SHA-256 checksums

The topic groups are trade/tariffs, rates/Federal Reserve, inflation,
geopolitics/China, energy/oil, economy/markets, legal/regulation, and
election/policy. In the frozen exploratory output, four topic columns are
constant zero. They are retained for provenance; the evaluation pipeline uses
`VarianceThreshold` so constant columns never enter the fitted estimator.

All feature names ending in `_lag1` refer to information aggregated from the
prior calendar day. The evaluation is restricted to July 15, 2024 through
April 23, 2026 so pre-archive zeros are not treated as genuine no-post days.

## Reproduction boundary

Collection and cleaning are reproducible with:

```bash
python scripts/nlp/scrape_trump_truth_archive.py \
  --start-date 2024-07-13 \
  --end-date 2026-04-23

python scripts/nlp/clean_trump_archive.py \
  data/raw/trump_truth/trump_archive_raw.csv \
  data/raw/trump_truth/trump_archive_cleaned.csv
```

The committed daily feature table is a frozen artifact from the original
exploratory keyword aggregation. It is preserved rather than silently
recomputed because the public archive and HTML parsing can change over time.
The standalone evaluator consumes this frozen table and is fully deterministic.

## Interpretation

The NLP comparison is an exploratory ablation with a short and politically
specific coverage period. It does not establish causality, does not validate a
deployable trading strategy, and should not be read as evidence that one public
figure's posts consistently predict market returns.
