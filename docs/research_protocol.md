# Research Protocol

**Frozen 2026-08-24, version 6.** Every degree of freedom in the confirmatory procedure is fixed below
and in `config/p1.yaml` before that procedure runs once. Amendments are not made to this
document; a change produces a new version and a new freeze.

| | |
|---|---|
| Instrument, frequency | SPY, daily |
| Sample | 2015-01-02 → 2026-08-21, 2,926 NYSE sessions |
| Out-of-sample | 2019-03-21 → 2026-08-21, 1,866 sessions (7.4 years) |
| Candidate features | 81 across 13 hypothesis groups |
| Assumed execution cost | 2 bp per side, 4 bp round trip, plus intraday financing |
| Trial structure | one confirmatory procedure, 24 pre-registered exploratory specifications |
| Data snapshot SHA-256 | `9b337ca75f8d077963448853e97542fab1258ab5b6dd289debec14061012b13a` |
| Configuration SHA-256 | `c219757bb47c087e269e4ccd7e9f03f8ca7b35a5ff119c0d49a04222a5ccb1e7` |

---

## 0. Question, success criterion, and power

**Question.** Using only information available at the close of session *t*, can the direction
of SPY's session *t+1* open-to-close return be predicted well enough to produce a measurable
increment over unconditional exposure to the same segment, after realistic costs?

**Success is not a profitable strategy.** Success is a defensible conclusion: every choice
justified in advance, out-of-sample performance reported with confidence intervals, and every
comparison made on identical terms. **"No support after costs" is a valid and more likely
outcome**, and is reported as such without a second search.

### 0.1 What this study can and cannot detect

The out-of-sample window is 1,866 sessions. Under an IID approximation the standard error of
the annualised Sharpe ratio is about **0.39**. Two distinct quantities follow, and conflating
them overstates what the study can do:

| Quantity | Value | Meaning |
|---|---|---|
| **Observed** Sharpe needed for a crude interval to exclude zero | ≈ 0.76 | 1.96 × 0.39 |
| **True** Sharpe needed for 80% power | ≈ 1.09 | (1.96 + 0.84) × 0.39 |

That 0.39 is a rough IID approximation, not a formal power analysis. Daily returns are
autocorrelated and heavy-tailed — the open-to-close series in this sample has excess kurtosis
of 12.98 — so final uncertainty comes from a paired stationary bootstrap, not from that
formula. No expected effect size is assumed anywhere in this protocol.

**The consequence is stated in advance rather than discovered later: this study cannot confirm
a moderate signal.** It can distinguish a large one from noise, and it can report an honest
negative.

### 0.2 The evaluation window is not a virgin holdout

Benchmark diagnostics (§5) were computed on the out-of-sample window before the confirmatory
procedure was specified, and they shaped it. Specifically, the finding that the intraday
segment's gross drift does not cover a daily round trip at the assumed cost is what led to the
two-condition structure in §7 rather than a single relative test.

The claim this protocol makes is therefore the weaker one: **the procedure is fixed, not the
result.** Every choice is pinned in a hashed configuration file committed before any model
runs.

Two things make the extent of that exposure checkable rather than merely disclosed.

**Direction.** Everything learned from the benchmarks raised the bar; nothing lowered it.

| Observed | Consequence for the protocol |
|---|---|
| The intraday segment is loss-making after costs | Added an absolute condition on top of the relative one |
| The always-long benchmark has negative Sharpe | Made the timing / cost-saving decomposition mandatory |
| Cash beats always-long on mean return | Refused to let the relative condition stand alone |

**Magnitude.** The three design judgements above rest on statistics from the evaluation window.
Recomputed on the training window alone — 2015-03-31 to 2019-03-20, never part of any
evaluation — all three hold, and more strongly:

| Benchmark | Training window | Out-of-sample |
|---|---|---|
| Always-long O2C, annualised excess | **−7.07%** | −4.23% |
| Always-long O2C, Sharpe | **−0.637** | −0.295 |
| Always-long O2C, breakeven cost per side | **0.60 bp** | 1.16 bp |

| Judgement | Training window | Out-of-sample |
|---|---|---|
| Loses money at the assumed cost, so an absolute condition is needed | yes | yes |
| Breakeven below the assumed cost, so the segment cannot support daily round trips | yes | yes |
| Negative Sharpe, so a relative condition alone is not binding | yes | yes |

**The design choices did not require out-of-sample information.** Training data alone would
have produced them. This does not remove the disclosure obligation; it bounds what the
disclosure costs.

---

## 1. Sample and data

### 1.1 Window

| | |
|---|---|
| Snapshot | 2015-01-02 → 2026-08-21, 2,926 NYSE sessions |
| Feature warm-up | 60 sessions |
| Modelling set | 2,866 rows from 2015-03-31 |
| Initial training block | first 1,000 sessions of the modelling set |
| **Out-of-sample** | **2019-03-21 → 2026-08-21, 1,866 sessions** |

The start date is chosen so that crises fall **outside** the training block, not inside it. The
initial training block consumes the earliest 1,000 sessions; a later start would place the
2020 dislocation entirely in training and defeat the reason for wanting it. Only a 2015 start
puts both 2020 and 2022 in the evaluation window.

The out-of-sample window contains the March 2020 dislocation (34% annualised volatility, 33.7%
drawdown in SPY), the 2022 tightening bear market (24% volatility, 24.5% drawdown), the 2023
banking episode, a low-volatility 2024, and a volatility pickup in 2025.

### 1.2 Sources and freeze

```
data/market_inputs_2026-08-21.csv
SHA-256   9b337ca75f8d077963448853e97542fab1258ab5b6dd289debec14061012b13a
Rebuild   python scripts/freeze_market_data.py       Verify   … --verify
```

| Source | Series |
|---|---|
| Yahoo Finance | SPY (adjusted OHLCV), `^VIX`, `DX-Y.NYB`, `^TNX`, **`BZ=F`** (primary oil), `CL=F` (WTI, reference), QQQ, IWM, DIA |
| FRED | **`DGS3MO`** (cash), `DTB3` (sensitivity), `DGS2`, `DGS10` |
| NYSE calendar | `session_minutes` (390 or 210), `is_half_day` |

**Sessions come from the NYSE calendar, not from the intersection of the series.** An
intersection silently drops any session where one input is missing and reports nothing about
it. Gaps are forward-filled only, limited to five sessions, never backward-filled, and every
filled cell is counted: **49 of 43,890 (0.11%)**, the largest group being 21 sessions each for
the two Treasury yields on days the bond market is shut and the NYSE trades. SPY has no
interior gap; the freeze script asserts this and refuses to write a snapshot otherwise.

### 1.3 Brent rather than WTI

Front-month NYMEX WTI settled at **−$37.63 on 2020-04-20** when Cushing storage ran out before
contract expiry. The value is correct, not a data error, but it leaves `log(OIL_t / OIL_{t−1})`
undefined on two sessions and distorts any rolling statistic spanning them. The episode is a
WTI-specific physical-delivery artefact, not a global oil-price signal.

Brent is priced on waterborne delivery and was unaffected. Over this sample its daily log
returns correlate **0.894** with WTI's, it never traded at or below zero, and it covers 99.9%
of sessions. WTI is retained as `OIL_WTI` for the vintage sensitivity. Rejected alternatives:
`USO`, whose contango decay makes its price level meaningless as a factor, and `XLE`, which at
0.567 correlation is an equity sector rather than an oil price.

### 1.4 Cash

```
rf_t = ( y_{t-1} / 100 ) × ( calendar days since the previous session / 365 )
```

`DGS3MO` is a coupon-equivalent yield. A bill under six months carries no intra-period
compounding, so it is a **simple** annualised rate and must not be compounded as an effective
annual rate. Interest accrues over calendar days, so a Friday-to-Monday gap earns three. The
rate dated *t* is published by H.15 the following business day, so accrual for session *t* uses
the rate dated *t−1*.

Cash averaged **2.84% a year** over the out-of-sample window and returned **23.51%**
cumulatively. It is not a rounding error and it is not zero.

**All Sharpe ratios are computed on excess returns.** Cash has zero excess volatility, so its
Sharpe is undefined and reported as undefined rather than as zero; comparisons against cash
use excess return or CAGR.

---

## 2. Execution specifications

### 2.1 Primary

- **Information set**: everything up to that session's official close — 16:00 ET normally,
  13:00 ET on an early close
- **Signal**: generated after that close, in an overnight batch
- **Entry**: market-on-open at *t+1*, submitted ahead of the applicable broker and exchange
  auction cut-off
- **Exit**: market-on-close at *t+1*
- **Overnight position**: none

```
r^O2C_{t+1} = log( Close_{t+1} / Open_{t+1} )      labels
R^O2C_{t+1} = Close_{t+1} / Open_{t+1} − 1         P&L

excess_t = w_t · R^O2C_t − 2c·|w_t| − f_t·|w_t|
```

**Accounting.** Figures are excess returns on unit notional: the active trading P&L of the
position, stated against cash.

The financing term is

```
f_t = ( y_{t-1} / 100 ) × session_minutes_t / ( 365 × 24 × 60 )
```

It must be built from session length rather than as a share of the daily cash return, because
that return already spans three calendar days after a Friday while a position is open for one
session; scaling it would double-count weekends. Using session minutes also charges an early
close proportionally less, with no special case. The charge is **0.53% a year at full
participation** on this sample, roughly 0.10 bp per side.

**Financing is charged by default.** A zero-cost collateral overlay is a financing structure
that would have to be specified and justified; it is not a natural baseline for a study of an
ETF. Omitting it is the sensitivity, not the base case. **Benchmarks carry the same charge**,
since a comparison is only meaningful on identical terms.

An intraday short incurs no overnight borrow.

### 2.2 Alternative

Features are all taken from *t−1*, the signal is generated before the close of *t*, execution
is market-on-close at *t*, and the position is carried to the close of *t+1*.

```
R^C2C_{t+1} = Close_{t+1} / Close_t − 1
excess = w·(R^C2C − rf) − c·|Δw| − b_annual × (calendar days held / 365) × max(−w, 0)
```

Borrow accrues over the calendar days a short is actually carried, so a position held across a
weekend is charged three days.

This specification changes the prediction target, the holding interval, the overnight exposure,
the cost function, and the dominant source of return. **It is a different strategy, not a
robustness check on the first one.** It is assigned to the exploratory group. Even a clear win
there is an exploratory result: it may be pre-registered as a future primary, but it cannot be
used to rescue a primary that failed.

---

## 3. Target and trading rule

### 3.1 Labels

```
z_t = r^O2C_{t+1} / ( Volatility_20,t + 1e-8 )

label = −1 if z_t ≤ q_25 ;  +1 if z_t ≥ q_75 ;  0 otherwise
```

`Volatility_20` is known at the close of *t*. Labels use log returns, matching the units the
volatility scaler is built from; P&L uses simple returns. The two never appear in one
expression. Where the quantiles are estimated is specified in §4.2 and is the single most
important detail in this document.

### 3.2 Calibration and the return mapping

A classifier does not produce an expected return, and a cost-determined threshold needs one on
a return scale. Tree-ensemble class probabilities are not calibrated, and multiplying
uncalibrated probabilities by class-conditional means distorts the very threshold the rule
depends on. The mapping is therefore cross-fitted:

```
scoring an inner fold
    thresholds, feature selection, scaling, the model, the class-conditional means,
    and the calibrator's own nested cross-fit are all estimated on that fold's
    inner-train, then applied to its inner-validation

the monthly refit
    a fresh cross-fit inside outer-train produces out-of-fold probabilities, the
    calibrator is fitted on those, and the base estimator is refitted on all of
    outer-train

mu_hat_t = Σ_c  P_calibrated(c | x_t) · E[R | c]
```

`E[R|c]` is estimated on **inner-train when scoring an inner fold** and on outer-train when
predicting outer-validation. This distinction is not cosmetic: outer-train contains every
inner-validation, so using outer-train means to score an inner fold lets that score see the
realised returns it is being graded on.

**Method: sigmoid (Platt), not isotonic.** With a 500-row inner out-of-sample and three
classes, one-vs-rest isotonic sees roughly 167 points per class, well inside the range where it
overfits. Sigmoid fits two parameters per class. Isotonic is an exploratory alternative.

`CalibratedClassifierCV` cannot be used. It takes one fixed `y`, but the label thresholds are
estimated inside each fold, so the same historical observation can carry different labels in
different folds. The cross-fitting is written out explicitly.

**Skip condition**: fewer than 200 out-of-fold points in total, or fewer than 30 in any class.
The step is then skipped, raw probabilities are used, and `calibration_skipped` is set on the
row. The calibrator is never fitted on data the base estimator was trained on, and never
borrowed from another fold or another step.

### 3.3 The no-trade band

```
h_t = 2c + f_t                         δ = 0 in the confirmatory procedure

w_{t+1} = +1  if mu_hat_t >  h_t
          −1  if mu_hat_t < −h_t
           0  otherwise
```

Both cost terms sit inside the threshold. `2c` is the round trip, since the primary
specification enters at the open and exits at the close on every active day. `f_t` is the
financing, which the position owes whether or not it also pays a spread. **A band built from
execution cost alone admits every trade with `2c < |mu_hat| < 2c + f_t`, and those lose money
in expectation.** The threshold is consequently time-varying: it tracks the short rate and
shrinks on an early close, exactly as the costs it must cover do.

**`δ` is held at zero.** The rule is then exactly what the section title claims: trade if and
only if the predicted return exceeds what the trade costs. A margin above cost is a defensible
thing to want, but selecting one is a search over the trading rule, and because `δ` drives the
participation rate directly it lets an inner cross-validation choose a model and a trading
frequency in the same breath. Margins of 0.5, 1.0 and 2.0 are a declared sensitivity in the
exploratory group, not a decision the confirmatory procedure makes. See the version record.

Flat therefore means "the prediction does not cover the cost of acting on it", not "the
prediction sits near the middle of its own distribution". A naive rule taking the arg-max class
is retained as a control, to quantify what the cost-aware threshold changes.

### 3.4 Units

| Stage | Units |
|---|---|
| Labels, features | log returns |
| P&L, costs, financing, `mu_hat`, the band | simple returns |
| Equity curve | `Π (1 + R_t^net)` |
| CAGR, maximum drawdown, Calmar, terminal wealth | all from the equity curve |
| Annualised mean excess return | `252 · R̄`, reported separately from CAGR |

---

## 4. Validation

### 4.1 Walk-forward structure

| Frequency | Event | What happens |
|---|---|---|
| Every 12 outer steps | **Reselection** | Full inner cross-validation selects the model family, its hyperparameters, and `δ`. These are then frozen for the next 12 steps. |
| Every outer step (21 sessions) | **Refit** | With those three frozen, the current outer-train re-estimates the quantiles, the feature set, the scaler, the model, the calibrator, and the class-conditional means. |

The annual event decides *which procedure*; the monthly event decides *what that procedure
gives on current data*.

The 1,866 out-of-sample sessions divide into 88 full blocks plus a remainder of 18. **The
remainder is predicted with the last fitted pipeline rather than discarded**, so no
out-of-sample session is lost: 89 steps in total, with reselection at steps 0, 12, 24, 36, 48,
60, 72 and 84 — eight of them. The window is expanding; a rolling window is an exploratory
specification. Embargo is one session (see §4.3).

### 4.2 Nesting order

```
for each outer step:

    if this step is a reselection:
        for each inner fold — TimeSeriesSplit(n_splits=5, test_size=100, gap=1):
            estimate q_25, q_75 inside inner-train    → labels for train and validation
            run feature selection and scaling inside inner-train
            fit each candidate inside inner-train; cross-fit its calibrator there too
            predict inner-validation once, without looking back
        concatenate the inner out-of-sample predictions
        sweep δ and apply the one-standard-error rule to pick family, hyperparameters, δ
        freeze those three for the next 12 outer steps

    with the frozen configuration, re-estimate quantiles, features, scaler, model,
        calibrator and class-conditional means on the full outer-train
    predict outer-validation once, without looking back
    persist predictions, probabilities, mu_hat, positions and realised returns
```

**`test_size` is fixed rather than left to the splitter's default.** With the default, the
first outer-train of 1,000 rows yields a first inner-train of 169 rows — which cannot support
screening 81 features whose own IC window is 60 sessions, let alone a three-class fit and a
calibration on top. At `test_size=100` the first inner-train is 499 rows, and as outer-train
grows the inner out-of-sample stays at the most recent 500 sessions. That is also the better
economic statement: selection is made on the last two years.

**Outer-validation results never flow back into any choice made for that step.** Different
years may select different model families.

Two implementation consequences follow from the labels depending on `y`. Neither `GridSearchCV`
nor `CalibratedClassifierCV` can be used, because both assume a fixed `y` while the thresholds
are re-estimated per fold; the nested loop is written out. And feature selection and quantile
estimation depend only on the inner-train slice, not on the candidate, so they are computed
once per fold and shared across the grid — an efficiency, not a shortcut, since every candidate
still sees only what its own inner-train produced.

### 4.3 Why one session of embargo suffices

The target uses data from session *t+1* only and the features use data through *t* only, so
**no two observations share a label**. One session of gap is therefore enough and purging is
unnecessary.

Some features use rolling windows of 60 to 252 sessions, so adjacent observations have heavily
overlapping inputs. **That produces dependence between samples, not leakage of future
information.** Dependence widens confidence intervals and is handled by the block bootstrap;
leakage biases estimates and is not present here. A multi-session holding target would require
this to be reassessed.

### 4.4 Aggregation

**Out-of-sample predictions from every step are concatenated into one return series, and
performance is computed once on it.** Averaging per-fold Sharpe ratios is not permitted: the
average of fold Sharpes is not the Sharpe of the concatenated series, and it conceals drift
between folds. The same rule applies to the inner out-of-sample used for selection.

---

## 5. Costs and benchmarks

### 5.1 Cost model

```
primary      R^net = w·R^O2C − 2c·|w| − f·|w|
alternative  R^net = w·(R^C2C − rf) − c·|Δw| − b_annual·(days held / 365)·max(−w, 0)
             opening and final closing costs included

base case    c = 2 bp per side = 4 bp round trip
scenarios    c ∈ {0, 1, 2, 5, 10} bp per side, always labelled per side
b_annual     25 bp, SPY general collateral
```

**2 bp is an assumed all-in execution cost, not a measured one.** Yahoo's open and close are
daily proxies and do not guarantee the price a market-on-open or market-on-close order
receives. The cost scenarios are the vehicle for that uncertainty.

At full participation the base case costs `4 bp × 252 = 10.08%` a year in execution plus 0.53%
in financing. SPY's long-run return is on the order of 10%. **A strategy trading in and out
every day must earn roughly 10.6% before it breaks even** — which is why the no-trade band has
to be determined by cost rather than by a quantile.

### 5.2 Breakeven

```
c*_zero = ( mean(w·R) − mean(f·|w|) ) / ( 2 · mean(|w|) )
```

Financing belongs in the numerator: it is owed regardless of the execution assumption, so a
breakeven ignoring it would overstate how much execution cost the strategy can absorb.

**Positions are those produced at the frozen base cost.** Only the execution cost varies
afterwards; positions are not re-optimised at each level, because a band that widens with cost
answers a different question. That re-optimisation is a separate exploratory specification.

### 5.3 Measured benchmarks

Computed and committed before any model exists, so the bar cannot move. Out-of-sample, 2 bp per
side, financing charged, excess returns.

| Spec | Benchmark | Annualised excess | Sharpe | 95% CI | Max drawdown | `c*` |
|---|---|---:|---:|---:|---:|---:|
| — | Cash | 0.00% | **undefined** | — | 0 | — |
| O2C | **Always-long O2C** | **−4.23%** | **−0.295** | [−0.853, +0.234] | −27.8% | **1.16** |
| O2C | Always-short O2C | −16.99% | −1.182 | [−1.745, −0.656] | −67.7% | −1.37 |
| O2C | Prior-day O2C direction | −18.77% | −1.308 | [−1.961, −0.595] | −74.2% | −1.74 |
| O2C | Prior-day C2C direction | −16.46% | −1.147 | [−1.780, −0.497] | −66.4% | −1.27 |
| O2C | 5-day momentum | −17.40% | −1.211 | [−1.860, −0.614] | −72.1% | −1.45 |
| O2C | 5-day reversal | −3.82% | −0.266 | [−0.919, +0.377] | −26.6% | 1.24 |
| C2C | **SPY buy-and-hold** | **+14.01%** | **+0.719** | [+0.101, +1.470] | −33.7% | — |
| C2C | 5-day reversal (C2C) | +3.45% | +0.177 | — | −28.3% | — |

Three readings belong in any write-up of this study.

**No simple intraday benchmark is profitable at the assumed cost.** With execution cost set to
zero but financing still charged, only two have any gross edge: always-long O2C (+5.85%, Sharpe
0.407) and 5-day reversal. Their breakeven costs are **1.16** and **1.24 bp per side**, both
below the 2 bp base case. **The intraday segment cannot support daily round-trip trading.**

**Even "always-long loses money" is not statistically established.** Its Sharpe interval
[−0.853, +0.234] spans zero. This is §0.1 in practice, not an aside.

**Buy-and-hold is a real and significant bar.** Its Sharpe difference against always-long O2C
has a lower bound of **+0.395**; its annualised excess over cash has a lower bound of **+2.2%**.

### 5.4 Why a single relative condition is not enough

```
R^strategy_t − R^always-long_t
    = (w_t − 1)·R^O2C_t  +  2c·(1 − |w_t|)  +  f_t·(1 − |w_t|)
      └── timing ──┘        └ cost saving ┘    └ financing saving ┘
```

Only the first term is evidence of predictive ability. The other two accrue to anything that
trades less. Substituting `w ≡ 0` — doing nothing at all:

| c per side | Timing | Cost saving | Financing saving | Net vs always-long |
|---|---:|---:|---:|---:|
| 1 bp | −6.38% | +5.04% | +0.53% | −0.81% |
| **2 bp** | **−6.38%** | **+10.08%** | **+0.53%** | **+4.23%** |
| 5 bp | −6.38% | +25.20% | +0.53% | +19.35% |

At the base cost, **doing nothing beats always-long O2C by 4.23% a year while its timing
contribution is strictly negative.**

To be precise about what this does and does not show: cash cannot "pass" the relative condition,
because that condition tests a Sharpe difference and cash has zero excess volatility, leaving
its Sharpe undefined. The accurate statement is that **cash beats always-long on mean return,
and more generally a near-flat, low-volatility strategy makes a relative Sharpe threshold
non-binding**, since its entire advantage can come from not trading. That is why an absolute
condition is required alongside it.

**Wording discipline.** If the net excess is significant but the timing term is not,
the conclusion is that **a cost-aware participation filter beats forced daily trading**. It is
not that a directional signal was found.

### 5.5 Benchmark layers

| Layer | Benchmark | Role |
|---|---|---|
| **Confirmatory** | Always-long O2C, same segment, same execution cost, same financing | Condition A |
| **Absolute** | Cash at the realised risk-free rate | Condition B |
| Risk-matched | Volatility-matched and exposure-matched O2C | Comparable return and drawdown levels |
| Capital allocation | SPY buy-and-hold, volatility-matched SPY | Scorecard only, never a significance gate |
| Model | Prior-day direction, 5-day momentum, 5-day reversal, simple logistic | Full disclosure |

Sharpe is invariant to leverage, but only given excess returns, no fixed costs, and financing
and transaction costs that scale proportionally. Cash is not zero here, so excess returns are
used throughout. Under that condition, volatility-matched and exposure-matched SPY have the
same Sharpe as SPY itself — **matching matters for comparing return levels and drawdowns, and
does nothing in a Sharpe test.**

The strategy is **not** required to beat SPY buy-and-hold. The two have different risk budgets
and holding intervals; that comparison belongs in the capital-allocation scorecard.

---

## 6. Statistical inference

### 6.1 Bootstrap

| | |
|---|---|
| Method | Stationary bootstrap (Politis and Romano) |
| Main block length | **20 sessions** |
| Sensitivity, stress | 10, 5 |
| Diagnostic | Politis–White data-driven length reported alongside; 17.0 on the always-long benchmark |
| Resamples | 10,000 for reported intervals, 1,000 inside the selection loop |
| Interval | Percentile, with BCa as a cross-check |
| Seed | Fixed and recorded |

The main block length was set to 20 before the confirmatory procedure ran, from the
Politis–White estimate on the already-computed benchmark. It is not chosen from a result.

**A strategy and its benchmark are resampled with the same block indices.** A strategy is a
timed version of its benchmark, so the two are strongly correlated; resampling them
independently inflates the standard error of their difference to the point where nothing is
significant. The Jobson–Korkie test with Memmel's correction is reported as a parametric
cross-check, not as the basis for any conclusion, since it assumes IID normality.

The share of resamples at or below zero is a **bootstrap fraction, not a p-value**: resampling
is centred on the observed difference rather than on a null of zero. Conditions read the
confidence bound.

### 6.2 Evidence of prediction, independent of P&L

An advantage in P&L can come from saving cost rather than from predicting. Three quantities
that do not depend on the trading rule are therefore reported:

- **Out-of-sample multi-class Brier skill score**, against a training-base-rate reference
- **Regression slope of realised open-to-close return on `mu_hat`**, with a paired bootstrap
  interval
- Calibration diagnostics: reliability curve, and Brier before and after calibration

### 6.3 Decomposition and sensitivity

Performance is decomposed by calendar year and by VIX tercile. Sensitivities cover the cost
scenario, `δ`, random seed, expanding versus rolling window, initial training length, block
length, excluding early closes, and omitting the financing charge. Their classification —
which count as trials and which do not — is in §7.2.

### 6.4 Multiple-testing reference

```
E[max SR] ≈ σ̂_SR · [ (1−γ)·Φ⁻¹(1 − 1/N) + γ·Φ⁻¹(1 − 1/(N·e)) ],   γ ≈ 0.5772
```

This is a **descriptive reference, not a p-value**, and not a substitute for a deflated Sharpe
ratio or a reality check. It answers: given N trials whose Sharpe ratios have sample standard
deviation σ̂, what is the best Sharpe pure noise would be expected to produce?

---

## 7. Trials

### 7.1 What counts as one

A trial is **one complete research specification** — feature set, model pipeline, target,
training window, position rule, thresholds — that **produces a set of outer-fold out-of-sample
predictions**.

Not trials: re-running the same specification after an error; the individual outer steps of a
walk-forward; the hyperparameter grid compared inside an inner cross-validation; regenerating
an identical result. An automatic tuning procedure evaluated once on outer out-of-sample is
**one** trial, not one per hyperparameter it searched.

But the random seed, `δ`, the window type, and the initial training length **do** count as
research attempts whenever they are used to choose which result is reported. The test is
whether the choice shapes the headline.

### 7.2 One confirmatory procedure

Allowing several specifications to produce out-of-sample results and then reporting the best
with an ordinary bootstrap interval invites the **winner's curse**: an ordinary interval does
not correct for having selected a maximum, and the reference in §6.4 does not repair it.

Two kinds of sensitivity must therefore be distinguished, or the budget is breached quietly:

| Kind | Definition | Counts as a trial |
|---|---|---|
| **Analysis sensitivity** | Recomputed on **frozen predictions and positions**: cost scenarios, block length, subsamples, omitting financing, decomposition by year or regime | **No** — no new predictions |
| **New specification** | Requires retraining, reselecting `δ`, or producing new positions | **Yes** — takes an E number |

| ID | Kind | Content |
|---|---|---|
| **P1** | **Confirmatory primary procedure** | `config/p1.yaml`, SHA `c219757b…` |
| E1–E4 | Exploratory | Feature-group ablation: cross-market, macro, intraday, volume |
| E5–E8 | Exploratory | Single model family fixed, no dynamic selection |
| E9–E11 | Exploratory | Naive arg-max, fixed-quantile band, volatility targeting |
| E12b | Exploratory | Safety margins above cost: δ ∈ {0.5, 1.0, 2.0} |
| E12 | Exploratory | Positions re-optimised at each cost level |
| E13–E16 | Sensitivity | Rolling window, initial training length, refit step, isotonic calibration |
| E17–E19 | Sensitivity | Repeated random seeds |
| E20–E21 | Sensitivity | Data vintage: WTI in place of Brent, and a re-download |
| E22–E24 | Exploratory | The alternative execution specification |

**The conditions in §8 apply to P1 only.** The exploratory group is reported in full, produces
no headline, and cannot substitute for P1. Every configuration in P1 is fixed before anything
runs.

The budget is not trimmed to flatter a multiple-testing adjustment. If twenty failures would
have been followed by a twenty-first attempt, the true N was never twenty. **The honest
response is to budget generously and register truthfully, not to shorten the ruler.**

### 7.3 Registry

Every trial, **including every failure**, is one row in `results/experiment_registry.csv`:
date, snapshot SHA, configuration SHA, code commit, feature set, model, hyperparameters,
training window, position rule, seed, out-of-sample net Sharpe, and the increment over
always-long O2C and over cash. **When the budget is spent, confirmatory research for this
version stops.**

---

## 8. Conditions

Evaluated on the concatenated out-of-sample net returns at the base cost, for **P1 only**.

```
Condition A — relative increment
    the net Sharpe difference against always-long O2C,
    paired stationary bootstrap 95% lower bound  >  0
    reported alongside the timing / cost-saving / financing-saving decomposition

Condition B — absolute tradability
    the annualised mean excess return over cash,
    paired stationary bootstrap 95% lower bound  >  0

Both satisfied      →  "supported"
Either unsatisfied  →  "insufficient evidence of a stable incremental value"
```

Several pre-declared conditions that must all hold are not several headlines, and create no
selection problem, because there is nothing to choose between.

`c*_zero` is reported as an economic margin, not used as a gate: if the lower bound on excess
over cash at 2 bp is already positive, requiring a point estimate of `c* > 2` adds almost
nothing.

**Interpreting Condition A.** The confirmatory benchmark is itself imprecisely estimated
(Sharpe −0.295, interval spanning zero). Paired resampling preserves the correlation between
the two series, so their difference can be estimated more precisely than either level, and the
test is valid. But the conclusion is that **P1 outperformed this pre-declared execution
benchmark** — not that the benchmark's true Sharpe is negative. Absolute profitability and
predictive ability are carried by Condition B and §6.2 respectively.

Further:

- Outperformance is not required on every metric or in every sub-period; auxiliary benchmarks
  are disclosed in full but do not gate
- If P1 does not pass, **no unregistered specification is added**; E1–E24 still run as
  pre-registered, but cannot change the P1 headline
- A failure is reported as **"not supported"**, never as "no such signal exists in the market" —
  the power stated in §0.1 does not license the latter

---

## 9. Alternative data

An exploratory appendix, outside the confirmatory core.

| Source | Overlap with the modelling set | Sessions |
|---|---|---:|
| News headlines | 2015-03-31 → 2024-03-04 | **2,247** |
| Truth Social | 2024-07-13 → 2026-04-23 | **446** |

Each experiment uses its own maximal overlap. **The requirement that an incremental test use one
sample applies within a single comparison, not across the study**; forcing all three onto a
common window would sacrifice most of the core sample to accommodate the shortest source.

### 9.1 News

2,247 overlapping sessions support the same walk-forward as P1: 1,000 for initial training
leaves 1,247 out-of-sample, a standard error of about 0.48 on a Sharpe difference. Inside the
same outer-step structure, restricted to the overlap, a market-features-only specification is
compared with market-plus-news — same sample, same folds, same cost model, differing only in
the feature set.

**Placebo**: the alternative-data dates are shifted by *k* ∈ {±5, ±10, ±20, ±60} sessions and
the incremental test is re-run. If the improvement survives the shift, it comes from sample
structure rather than from information content. Each shift is its own test and is registered.

### 9.2 Truth Social: no trading test

446 overlapping sessions cannot support an initial training block of 1,000. Even compressed to
200, the out-of-sample is 246 sessions and the standard error on a Sharpe difference is **1.07**
— **only a difference above roughly 2.1 would be distinguishable**. No effect size is assumed;
that threshold alone settles it.

**Running a trading model on this sample and reporting a Sharpe is exactly the kind of noise
this protocol exists to prevent.** The layer therefore delivers:

1. Data lineage and collection documentation: source, time zone and daylight saving, dedup,
   the cause of the encoding damage and its repair, coverage and known gaps, compliance
2. The trading-session mapping and its verification, quantifying the difference against
   calendar-day binning
3. Feature construction and a feature dictionary, including how empty text is classified and
   how zero-variance topics are dropped
4. Descriptive statistics and the power calculation showing why no trading test was run

### 9.3 Session mapping

```
bucket_t = ( κ_{t−1}, κ_t ]      κ_t = the official close of session t
```

The bucket is combined with the market features of session *t*, the signal is generated after
that close, and the trade happens at the open of *t+1*. A post at 08:00 on Monday belongs to
Monday's close batch and trades Tuesday's open. Weekend and holiday posts roll into the next
complete close batch and are never dropped. The time zone is `America/New_York` with daylight
saving handled; boundaries are left-open and right-closed; the original publication time is
used, not an edit time and not a scrape time.

**Stated explicitly**: to keep the alternative data on the same end-of-day information set as
the market variables, the pre-open window is not used. Relative to a separate morning pipeline
this **forgoes about 18.7% of posts being tradable one session earlier**. That is a design
choice, not an oversight.

### 9.4 Construction and known limitations

- Sentiment uses the **Loughran–McDonald** financial lexicon (Loughran and McDonald 2011,
  *Journal of Finance*), which is citable and reproducible, rather than a bespoke word list
- Source, licence and download path are recorded in `docs/scraping_notes.md`
- The raw headline file contains exact duplicate rows; deduplication is explicit and counted
- **Availability assumption, stated because it cannot be verified from the data**: the headline
  file carries dates without times, so a headline dated D is treated conservatively as fully
  known only after D's close, and used for the trade at D+1's open
- 26.5% of archived posts have empty text; **"image or repost with no text" and "scrape
  failure" are different things** and are classified separately, never merged
- Topic columns with zero variance in the training slice are dropped and recorded

---

## 10. Early closes

23 sessions in the sample close at 13:00 ET (`session_minutes = 210`; the other 2,903 are 390).

| Treatment | Decision |
|---|---|
| Drop from the modelling set | No |
| Rescale the target by session length | No |
| Keep the true open-to-close return, the true round-trip cost, and financing scaled by length | Yes |
| Carry `session_minutes` and `is_half_day` | Yes |
| Excluding early closes | Analysis sensitivity, on frozen predictions |
| Normalising volume and range by session length | At most an exploratory specification |

An early close is a real trading state, and **a shorter session makes the same fixed round trip
harder to recover** — which is itself an economic result, not an artefact to be cleaned away.

Measured effect, early closes relative to full sessions:

| Quantity | Ratio | Mechanically compressed |
|---|---:|---|
| Volume | 0.518 | yes |
| High-low range | 0.541 | yes |
| Absolute open-to-close return | 0.656 | yes |
| **Close location value** | **1.071** | **no** |

Close location value is already divided by the day's high-low range and is a scale-free
intraday ratio. Returns are never scaled by 390/210.

---

## 11. Verification

`tests/` — the automated suite, run on every commit. It stood at 38 checks when this protocol was frozen; see the editorial note in Appendix B for what was added afterwards and why that does not constitute a change of method.

The central one is **no look-ahead by construction, verified empirically**: the entire feature
matrix is rebuilt on truncated history at three cut points, and every overlapping value must be
bit-identical. Any transform that reads forward — a centred window, a backward fill, a
full-sample statistic — fails this regardless of how its formula looks.

The same suite pins target alignment; the H.15 publication lag, via a single-point jump in
synthetic data; each feature's declared adjustment invariance, by rescaling the whole price
history; cash accrued simply rather than as an effective annual rate; financing built from
session length rather than a share of the daily rate, so weekends are not double-counted and
early closes are charged less; borrow accrued over calendar days held; breakeven including
financing; the no-trade band's boundary case, where a prediction covering the spread but not
the financing must not trade; the absence of infinities; a bounded warm-up; and binary flags
being binary.

Three of those checks corrected a claim made in an earlier draft of this document rather than
confirming one: `volume_ret_interaction` is in fact invariant to dividend adjustment, its real
exposure being splits, of which this sample has none; cash had been compounded as an effective
annual rate; and the financing charge had been scaled off the daily cash return, double-counting
weekends.

---

## 12. Deliberately out of scope

| Item | Reason |
|---|---|
| Full deflated Sharpe ratio | The candidates are strongly correlated and the effective number of independent trials would itself need a separate argument; §6.4 gives a descriptive reference instead |
| PBO / CSCV | Limited marginal information under a single confirmatory procedure |
| A regression target | The three-class frame is retained. A regression specification would have to be pre-registered in parallel, never added after a classification result |
| A third execution specification permitting overnight carry | It would blend the intraday and overnight segments and enlarge the trial space |
| Pre-trained language models | The lexicon approach already answers whether there is an increment |
| A trading test on Truth Social | 246 out-of-sample sessions, standard error 1.07 — see §9.2 |
| Event study | Too few in-sample events |
| Live paper trading | Can begin any time after the freeze; it does not block this round |

---

## Appendix A · P1 configuration

`config/p1.yaml`, **SHA-256 `c219757bb47c087e269e4ccd7e9f03f8ca7b35a5ff119c0d49a04222a5ccb1e7`**,
recorded in every run manifest.

### A.1 Inner cross-validation

`TimeSeriesSplit(n_splits=5, test_size=100, gap=1)`. First inner-train 499 rows; inner
out-of-sample fixed at the most recent 500 sessions. Feature selection and quantile estimation
are computed once per fold and shared across candidates.

### A.2 Feature selection

Runs inside every inner-train slice and again on every outer-train refit. No manual step.

1. Drop features with zero variance in the slice
2. Rank by the absolute mean of a 60-session rolling Spearman IC
3. Keep the top **3** within each of the 13 hypothesis groups
4. Hierarchical clustering, average linkage, distance `1 − |correlation|`, cut at **0.20**
   (merging anything above 0.80); keep the highest-|IC| member of each cluster
5. Cap at **25** features

### A.3 Candidate space: 23

| Family | Complexity rank | Grid | Count |
|---|---:|---|---:|
| Majority baseline | 0 | — | 1 |
| Logistic | 1 | C ∈ {0.01, 0.1, 1.0} × class_weight ∈ {None, balanced} | 6 |
| Random forest | 2 | max_depth ∈ {3, 5} × min_samples_leaf ∈ {50, 20} | 4 |
| LightGBM | 3 | num_leaves ∈ {7, 15} × lr ∈ {0.03, 0.1} × min_child ∈ {60, 30} | 8 |
| XGBoost | 4 | max_depth ∈ {2, 3} × lr ∈ {0.03, 0.1} | 4 |

`δ` is fixed at zero and is not a dimension of the search.

### A.4 One-standard-error rule

```
metric        net Sharpe on the concatenated inner out-of-sample, at 2 bp per side
point         computed once on the concatenated series, never averaged across folds
standard err  stationary bootstrap, block 20, 1,000 resamples
              (10,000 for reported figures; 1,000 here affects only the tie band)

eligible      score_j  >=  score_best − se_best
              the band is one standard error of the BEST candidate, not of each

ordering      (complexity_rank, within_family_rank)
ties          resolve to the earliest entry in the declared grid order

vetoes        fewer than 30 active positions on the concatenated inner out-of-sample
              undefined Sharpe from zero excess variance
              → excluded from ranking, recorded as degenerate
              → if all are degenerate, the majority baseline is selected and the
                step is flagged as producing no tradeable model
```

Three things this rule is not, stated because each is easy to assume.

It is **not a multiple-testing correction.** It is a model-simplification heuristic: given two
candidates that are indistinguishable, prefer the simpler. Selecting a maximum over 23
candidates still carries a winner's curse, which is what the descriptive reference in §6.4
speaks to and what a deflated Sharpe ratio would address properly.

It uses **the standard error of the best candidate alone**, not the paired covariance between
candidate scores. When the candidates being compared are correlated — and here they are, being
fits of overlapping feature sets to the same labels — that understates how much of the gap
between two candidates is shared noise. This is a known limitation of the rule and is recorded
rather than worked around.

It carries **no guarantee that more than one candidate is eligible.** A single eligible
candidate means the best was more than one standard error clear of everything simpler. That is
an outcome, not a malfunction, and widening the band after seeing that it bound tightly would
be exactly the kind of post-hoc loosening the protocol exists to prevent.

The 30-position floor is a **degeneracy guard only**: below it the metric is not estimable. It
is not a statement that a strategy ought to trade often. Raising it to produce more eligible
candidates would smuggle "must trade frequently" into the hypothesis space and could exclude a
genuinely sparse signal. Per-candidate diagnostics — score, standard error, active positions,
turnover, and the train-minus-validation gap — are written to
`results/candidate_diagnostics.csv` for every candidate at every reselection, as diagnostics
and not as further gates.

### A.4.1 When the majority baseline is selected

The baseline is in the candidate set as a reference: a model that predicts the class prior and
nothing else. The one-standard-error rule can select it, and that outcome has a specific
meaning — **no candidate was more than one standard error clear of predicting the base rate**.

It also has a specific consequence for the positions, which must be read correctly rather than
as a strategy result. The baseline's `mu_hat` is a constant within each refit, being the
prior-weighted average of the class-conditional means. The band it is compared against is not
constant: it moves with the short rate and the session length. So on steps where the baseline is
selected, **the position series is the comparison of an unconditional drift estimate against the
prevailing cost level, and carries no feature-based signal at all.** It will tend to hold
exposure when financing is cheap and stay flat when it is not, which is a property of the rate
environment rather than of anything predicted.

Two things follow, and both are disclosures rather than adjustments:

- Steps where the baseline was selected are flagged in `results/selection_log.csv`
  (`baseline_selected`) and are identifiable in `results/oos_predictions.csv` from the `model`
  column. Any performance figure covering those steps is reported with that fact attached.
- No rule maps "baseline selected" to a forced flat position. Adding one would change the
  realised P&L, which is a substantive change and would need its own version. The protocol
  notes instead that the configuration already flags the *other* route to the baseline — being
  selected because every candidate degenerated — as producing no tradeable model, and that the
  two routes are therefore reported differently despite arriving at the same model. That
  asymmetry is recorded here rather than smoothed over.

### A.5 Calibration

Sigmoid (Platt), hand-rolled cross-fit. Isotonic is exploratory.

```
nested splitter        TimeSeriesSplit
n_splits               3
test_size              100     → 300 out-of-fold points from a 499-row inner-train
gap                    1
min base train rows    180     → a sub-fold below this is skipped and recorded
min calibration points 200     → total out-of-fold
min per class          30

when unmet   skip calibration for that candidate and fold, use raw probabilities,
             set calibration_skipped; never fit the calibrator on data the base
             estimator saw, and never borrow one from another fold or step
```

### A.6 Compute budget

```
per candidate per inner fold   4 fits  (3 calibration sub-folds + 1 model)
per reselection                23 × 5 folds × 4 = 460
reselections                   8
per monthly refit              4  (3 calibration sub-folds + 1 final)
outer steps                    89
total                          460 × 8 + 4 × 89 = 4,036 fits
```

### A.7 Determinism and artefacts

Base seed `20260823`; each outer step uses `base + step_index`; each fit runs single-threaded,
with parallelism at the outer-step level.

Outputs: `oos_predictions.csv`, `trade_ledger.csv`, `selection_log.csv`,
`feature_stability.csv`, `calibration_diagnostics.csv`, `run_manifest.json`.

---

## Appendix B · Version record

**v6, 2026-08-24.** `δ` is held at zero in the confirmatory procedure rather than selected
from a grid, which reduces the candidate space from 92 to 23. The margins move to the
exploratory group. Nothing else changed: the metric is still the inner out-of-sample net
Sharpe, the one-standard-error rule stands, and the 30-position floor stays where it was as a
degeneracy guard.

The reason came from an engineering smoke test run on a truncated window under v5. Selecting
over `δ` turned out to let the inner cross-validation choose a model and a trading frequency at
the same time: `δ` sets the participation rate directly, so the candidate that won was reliably
whichever one traded least — at the median, 28 active positions in a 500-session inner
out-of-sample, ranked first out of 92. A Sharpe ratio estimated on 28 non-zero observations and
selected as the maximum of 92 is not a quantity to build a procedure on.

Two properties of that diagnostic matter for whether acting on it was legitimate. It came
entirely from inner cross-validation inside the training block, so no out-of-sample information
entered it. And the change tightens the procedure: one fewer researcher degree of freedom, and
a trading rule that now matches what §3.3 says it is. The alternative considered and rejected
was raising the active-position floor, which would have imposed a 15% participation requirement
picked to fit the diagnostic and would have quietly added "must trade frequently" to the
hypothesis space.

The smoke run itself is recorded in `results/experiment_registry.csv` as `SMOKE-01` with
`run_type=engineering_smoke` and `excluded_from_trial_budget=true`. **It inspected structural
outputs, including position participation, over 63 realised out-of-sample dates. No returns or
performance statistics were computed or inspected.** It is excluded from the research trial
budget because it used an informal retune cadence, covered 63 outer dates, and produced no
performance figure — recording it as a failed experiment would be as inaccurate as leaving it
out.

Verifying v6 on the same window confirmed the fix — 12 and 8 eligible candidates of 23 at the
two reselections, against 1 of 92 before — and surfaced one further property, disclosed in
A.4.1 rather than changed: the one-standard-error rule can select the majority baseline, and the
positions that follow then reflect the cost environment rather than any prediction. It is
flagged in the outputs and left alone, because forcing those steps flat would change the
realised P&L and require another version. The train-minus-validation gaps from that verification
are worth recording as the clearest thing the diagnostics produced: 0.66 for the baseline, 0.89
to 1.45 for logistic, 1.63 to 2.94 for random forest, 3.17 to 4.80 for XGBoost, and 5.03 to 9.09
for LightGBM.

**Editorial note, 2026-08-24, after the confirmatory run.** Five checks were added to `tests/`,
taking the suite from 38 to 54. They verify properties of the completed run's output rather than
of the procedure: that a flat session is charged no execution cost and no financing, that every
realised position equals what §3.3's band implies for its `mu_hat`, that the reported class
probabilities sum to one, that the majority baseline's `mu_hat` is constant within an outer
block and changes across blocks, and that each out-of-sample session appears exactly once. **No
protocol text, configuration value, model, or reported figure changed.** They are recorded here
because the alternative — a suite that silently grows while the document keeps quoting the frozen
count — makes the freeze harder to check rather than easier. The state at freeze is tagged
`protocol-v6-frozen` and can be diffed.

`protocol-v5-frozen` is not overwritten. v6 is a separate tag with a separate configuration
hash, so the two states remain distinguishable. Both smoke runs are in
`results/experiment_registry.csv` as `SMOKE-01` and `SMOKE-02`.

---

## Appendix C · Execution order after the freeze

1. Commit the protocol, configuration, code and test results
2. Tag the freeze; the tag is immutable
3. Smoke test on synthetic data or a truncated training period — check the flow and the shape
   of the artefacts only, never a performance figure
4. Run P1 once
5. Do not inspect interim performance and stop, change a parameter, or switch model on it
6. Complete the P1 report before running the pre-registered exploratory group
7. Whether or not P1 passes, the exploratory group cannot change its headline

A pure coding error may be fixed, registered, and the run repeated. **If the fix would change
the labels, the features, the splits, the model selection, the costs, or the trading rule, it is
a new version: regenerate the protocol and configuration hashes before running again.**
