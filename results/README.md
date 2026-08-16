# Results

These files are the machine-readable outputs of the canonical frozen-snapshot run:

- `final_test_metrics.csv`: classification and trading-oriented holdout metrics
- `final_test_confusion_matrix.csv`: three-class holdout confusion matrix
- `selected_features.csv`: final 21-feature set and categories
- `run_manifest.json`: sample sizes, thresholds, selected model, data checksum, software versions, and full-precision metrics

All reported performance is historical, before trading costs, and based on a 206-session holdout. See the root README for methodology and limitations.

The separate Trump-post NLP ablation writes:

- `trump_nlp_cv_metrics.csv`: fold-level and summary metrics from five
  expanding-window comparisons
- `trump_nlp_holdout_metrics.csv`: a controlled 80/20 chronological holdout
  comparison using the same Logistic Regression specification with and without
  the lagged NLP features

These NLP files are exploratory and are not part of the canonical LightGBM
selection or the main 206-session holdout result.
