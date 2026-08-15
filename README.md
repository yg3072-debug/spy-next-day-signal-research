# SPY Next-Day Long/Flat/Short Signal Research

An end-to-end, time-aware machine-learning study of next-trading-day directional signals for SPY. The project converts information available at the current close into one of three actions:

- **Long**: sufficiently positive volatility-adjusted next-day return
- **Flat**: movement is too small to justify directional exposure
- **Short**: sufficiently negative volatility-adjusted next-day return

The emphasis is not on maximizing in-sample accuracy. It is on building a leakage-aware research process, comparing models under walk-forward validation, and separating model selection from final out-of-sample evaluation.

> Research prototype for educational purposes only. Results are historical, do not include trading costs, and are not investment advice.

## Research question

Can market, volatility, macroeconomic, and cross-market information available at day \(t\) support a robust Long/Flat/Short decision for SPY on trading day \(t+1\)?

## Methodology

### 1. Data and features

The analysis uses daily observations from **March 30, 2022 through May 4, 2026**, with **1,027 complete observations** after feature construction. Data are downloaded at runtime from Yahoo Finance and FRED.

The initial 81 candidate features cover:

- SPY returns, trend, momentum, and Bollinger position
- realized volatility and VIX level/change/regime
- Treasury yields and the 2Y-10Y yield curve
- DXY and crude-oil movements
- intraday range, overnight gap, and relative volume
- calendar effects
- cross-market signals from QQQ, IWM, and DIA

Feature selection is performed only on the training/CV period. Rolling 60-day Spearman IC and ICIR are used for within-group screening, followed by category-aware selection, hierarchical correlation clustering, and a final redundancy check. This reduces the feature set from **81 to 21**.

### 2. Target construction

The target is the next-day SPY log return divided by the 20-day historical volatility available at the current close. Long and Short thresholds are the 75th and 25th percentiles estimated from the training/CV sample only; the middle observations are labeled Flat.

This volatility-adjusted definition keeps the action threshold more comparable across changing volatility environments while avoiding future information in threshold estimation.

### 3. Time-aware validation

- First 80% of observations: training and model-selection period
- Final 20%: protected chronological holdout
- Five expanding-window validation folds with a one-trading-day gap
- Final holdout remains untouched until the model and hyperparameters are selected

The candidate models are a majority-class baseline, Logistic Regression, Random Forest, XGBoost, and LightGBM. Model selection considers balanced accuracy, Macro F1, fold stability, train-validation gaps, and trading-oriented diagnostics.

## Final holdout results

The tuned LightGBM model was selected using walk-forward CV evidence and evaluated once on the protected 206-day holdout period.

| Metric | Final holdout |
|---|---:|
| Accuracy | 39.32% |
| Balanced accuracy | 39.89% |
| Macro F1 | 37.71% |
| Active-trade hit rate | 51.35% |
| Active-trade rate | 71.84% |
| Annualized return | 7.48% |
| Annualized volatility | 10.92% |
| Sharpe ratio | 0.68 |
| Maximum drawdown | -9.55% |

These figures are **before commissions, bid-ask spread, slippage, financing, and taxes**. The decline from CV to final-holdout performance is itself an important result: predictive relationships are weak, unstable, and sensitive to market regime.

## Repository structure

```text
.
├── notebooks/
│   └── spy_next_day_signal_research.ipynb
├── results/
│   ├── final_test_metrics.csv
│   └── selected_features.csv
├── .gitignore
├── README.md
└── requirements.txt
```

The repository notebook keeps the complete analysis code but clears execution outputs to remain lightweight and reviewable. Reported final metrics are preserved in the README and CSV files; running the notebook regenerates all tables and figures.

## Execution modes

The notebook supports two reproducibility modes through one configuration variable near the top:

```python
FULL_TUNING = False
```

- **Fast reproduction (default):** rebuilds the four tuned estimators from the best parameters recorded during the original training-only walk-forward searches. It still reruns feature construction, walk-forward diagnostics, model comparison, the protected final holdout, and the core figures.
- **Full tuning:** set `FULL_TUNING = True` to repeat every `GridSearchCV` search. This performs **70,810 cross-validation fits** and can take several hours depending on the machine.

The fast path does not use holdout results to select parameters; it reuses parameters that were originally selected from the training/CV period.

## Reproducing the analysis

Python 3.10 or later is recommended.

```bash
git clone https://github.com/yg3072-debug/spy-next-day-signal-research.git
cd spy-next-day-signal-research
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
jupyter lab notebooks/spy_next_day_signal_research.ipynb
```

Run the notebook from top to bottom. Internet access is required for Yahoo Finance and FRED downloads. Leave `FULL_TUNING = False` for the recommended reviewer-friendly run, or change it to `True` for an exhaustive research rerun.

## Main limitations

- The sample covers a limited set of recent market regimes.
- Transaction costs, slippage, financing, and statistical significance tests are not yet incorporated.
- The current backtest maps discrete signals to fixed directional exposure; it does not optimize position size.
- Feature screening includes a final manual redundancy decision.
- Classification performance is only modestly above a three-class chance benchmark.
- Text-based sentiment features are not included in this notebook.

## Planned research extension

The next research stage will extend this framework from SPY to equity-index futures such as the E-mini S&P 500 and Nasdaq-100. The extension will require continuous-contract construction, rollover handling, nearly 24-hour session definitions, transaction-cost modeling, margin-aware position sizing, sequence models, dynamic decision policies, and explicit risk controls.
