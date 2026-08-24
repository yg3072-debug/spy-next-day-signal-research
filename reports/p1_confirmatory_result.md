# Confirmatory Result

**Protocol v6, configuration `c219757b…`, snapshot `9b337ca7…`. One run, 2026-08-24.**

Out-of-sample: 1,865 NYSE sessions, 2019-03-21 to 2026-08-20 (7.4 years). Costs are 2 bp per
side, 4 bp round trip, plus intraday financing.

**Units.** Annualised mean returns and Sharpe ratios are stated in excess of cash. CAGR,
terminal wealth and drawdown are computed from total portfolio returns including the cash leg.
The two conventions are explicitly identified by metric and are never used interchangeably. Both
appear in the comparison table below, in different columns of the same row.

---

## Summary

**Neither pass condition is met. The finding is that there is insufficient evidence of a stable
incremental value.**

| Condition | Point estimate | 95% lower bound | Passes |
|---|---:|---:|:--:|
| **A** — Sharpe difference against always-long open-to-close | +0.164 | **−0.519** | no |
| **B** — annualised mean excess over cash | −1.32% | **−7.32%** | no |

The verdict is not the substantive result. This is:

```
mean-return excess over always-long, decomposed        annualised, with paired intervals

    gross positioning     −3.97%   [−11.51%, +3.58%]   ← the only term bearing on prediction
    cost saving           +6.73%
    financing saving      +0.34%
    ──────────────────────────────────────────────────
    net                   +3.11%   [ −4.45%, +10.55%]
```

**The entire positive point estimate over always-long comes from saving execution cost and
financing; the realised gross positioning contribution is −3.97%.** Its interval spans zero, so
what is established is that the realised value is negative, not that true positioning ability
is. The net difference of +3.11% has an interval that also spans zero — and note that this is
its own statistic. Condition A tests a difference of *Sharpe ratios*; +3.11% is a difference of
*mean returns*, and A's interval says nothing about it.

Two diagnostics computed without reference to the P&L: a Brier skill score of **+0.0122**
against a training-base-rate reference, for which no uncertainty interval was pre-specified, and
a regression slope of realised on predicted return of **−0.085, interval [−1.005, +0.891]**,
which is highly imprecise and includes zero. Together these provide no compelling corroborating
evidence of stable predictive skill.

---

## The comparison

Same window, same execution specification, same cost model, excess of cash.

| | Ann. mean excess | CAGR | Volatility | Sharpe | 95% interval | Max drawdown | Participation | Breakeven |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **P1** | **−1.32%** | +1.12% | 9.15% | **−0.144** | [−0.862, +0.509] | −17.6% | 33.2% | 1.21 bp |
| Always-long O2C | −4.43% | −2.57% | 14.36% | −0.308 | [−0.853, +0.218] | −27.8% | 100% | 1.12 bp |
| Exposure-matched O2C | −0.98% | +1.84% | 3.17% | −0.308 | [−0.853, +0.218] | −6.3% | 100% | 1.12 bp |
| Cash | 0.00% | +2.89% | 0% | undefined | — | 0% | 0% | — |
| SPY buy-and-hold | +13.87% | +15.97% | 19.49% | +0.712 | [+0.087, +1.436] | −33.7% | 100% | — |

Always-long open-to-close reads −4.43% here and −4.23% in the benchmark table committed before
the run. Same rule, same costs; the benchmark table is indexed by the session a position is held
in and covers 1,866 sessions, while these rows are indexed by the decision date and stop one
session earlier, the last modelling session having no next session to predict. This table is the
one to use, because a comparison has to be on identical rows.

Two readings that need no statistics.

**P1 turned one dollar into 1.086 over 7.4 years. Cash turned it into 1.235.** Every dollar
committed ended about **0.149 lower** — 14.9 percentage points of cumulative wealth, or a final
wealth about **12.1% below** simply holding Treasury bills — while carrying a 17.6% drawdown.

**The exposure-matched line is the sharper comparison.** P1 held an average net exposure of
+0.221. A constant 0.221 position in the same intraday segment, with no model at all, returned
−0.98% a year at 3.17% volatility and a 6.3% drawdown. P1 returned −1.32% at 9.15% volatility
and a 17.6% drawdown. Sharpe is invariant to that scaling, so the two are −0.144 against −0.308
— P1 is ahead on the ratio, behind on level, and far behind on drawdown. The gap in Sharpe is
the +0.164 of Condition A, and it is not distinguishable from zero.

---

## Why the point estimate is positive and why that does not help

The excess of any strategy over always-long decomposes exactly:

```
R_strategy − R_always-long  =  (w − 1)·R^O2C  +  2c·(1 − |w|)  +  f·(1 − |w|)
```

Only the first term bears on prediction, and it is worth naming precisely: `(w − 1)·R` covers
not only which direction was called but also **when the procedure chose to stand aside**, since
a flat session contributes `−R`. It is a gross positioning contribution, not a direction-call
contribution. The other two terms accrue to anything that trades less than always. P1 was flat
on 66.8% of sessions, so it avoided a great deal of cost:

| Term | Annualised | 95% paired interval |
|---|---:|---:|
| Gross positioning | **−3.97%** | [−11.51%, +3.58%] |
| Cost saving | +6.73% | — |
| Financing saving | +0.34% | — |
| **Net over always-long** | **+3.11%** | [−4.45%, +10.55%] |

Section 5.4 of the protocol fixes the language for this case in advance. Where the net excess is
significant but the positioning term is not, the conclusion available is that a cost-aware
participation filter beats forced daily trading — not that a directional signal was found.

**Here even that is unavailable.** P1 did not meet the pre-specified Sharpe-difference threshold,
and the mean-return difference of +3.11% carries an interval from −4.45% to +10.55%. What can be
said, and no more: the entire positive point estimate of P1's advantage over always-long is
attributable to saving cost and financing, and the realised gross positioning contribution was
−3.97%. Neither statement is a claim about true positioning ability, whose interval spans zero
in both directions.

---

## Evidence of prediction, independent of P&L

An advantage in P&L can come from saving cost. These two quantities cannot.

| Quantity | Value | 95% interval | Reading |
|---|---:|---:|---|
| Multi-class Brier skill vs training base rate | **+0.0122** | — | Essentially nil |
| Regression slope of realised return on `mu_hat` | **−0.085** | [−1.005, +0.891] | Indistinguishable from zero |

The Brier skill is a small positive point estimate, and **no uncertainty interval for it was
pre-specified**, so it is not by itself grounds for concluding that skill is absent. The slope is
highly imprecise and includes zero. Together the two provide **no compelling corroborating
evidence of stable predictive skill** — which is a weaker and more accurate statement than
either "no skill" or "negative skill".

The slope in particular deserves a caution in both directions. Its point estimate is negative,
which would suggest predictions running the wrong way, but the interval runs from −1.005 to
+0.891. **A negative point estimate inside an interval that wide is not evidence of anything**,
and reporting it as though the model were reliably anti-predictive would be the same error as
reporting a positive one as alpha.

---

## Robustness

**Block length.** The protocol fixed the main block at 20 sessions before the run, from a
Politis–White estimate of 17.0 on the pre-computed benchmark. Politis–White on P1's own return
series suggests 3.8, so the fixed choice is the conservative one. The verdict does not move:

| Block | Condition A lower bound | Condition B lower bound | Verdict |
|---:|---:|---:|---|
| 20 | −0.519 | −7.32% | fails both |
| 10 | −0.494 | −7.31% | fails both |
| 5 | −0.516 | −7.32% | fails both |

**Cost.** Positions are those produced at the base cost; only the execution cost varies.

| Cost per side | 0 bp | 1 bp | **2 bp** | 5 bp | 10 bp |
|---|---:|---:|---:|---:|---:|
| Sharpe | +0.222 | +0.039 | **−0.144** | −0.693 | −1.593 |

A gross edge exists and it is small. It is consumed somewhere between 1 and 2 bp per side. The
breakeven of 1.21 bp per side sits alongside always-long O2C at 1.12 and the five-day reversal
benchmark at 1.24 — the same order of magnitude, which is another way of saying that what P1
found is not distinguishable from the segment's own unconditional properties.

**Sub-periods.** No stability.

| | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Participation | 0% | 60% | 19% | 40% | 36% | 57% | 18% | 26% |
| Sharpe | — | −0.08 | +0.50 | **+0.87** | −0.65 | **−1.87** | −0.38 | −0.77 |

Positive in 2021 and 2022, sharply negative in 2024. By volatility regime, only the top VIX
tercile is positive (+0.46); the low and middle terciles are −1.20 and −0.79. A result that
appears only in the highest-volatility third of sessions and reverses elsewhere is what an
absence of signal looks like when it is sliced finely enough.

---

## What the procedure actually selected

Eight reselections, one a year. The selected model changed repeatedly, which is itself
information: no family was persistently better than the others.

| Step | Date | Selected | Eligible | Degenerate |
|---:|---|---|---:|---:|
| 0 | 2019-03-20 | majority baseline | 12/23 | 0 |
| 12 | 2020-03-19 | majority baseline | 13/23 | 0 |
| 24 | 2021-03-19 | random forest, depth 3 | 13/23 | 0 |
| 36 | 2022-03-18 | LightGBM, 7 leaves | 10/23 | 0 |
| 48 | 2023-03-21 | LightGBM, 7 leaves | 7/23 | 1 |
| 60 | 2024-03-21 | random forest, depth 3 | 1/23 | 1 |
| 72 | 2025-03-25 | majority baseline | 12/23 | 0 |
| 84 | 2026-03-26 | logistic, C = 0.01 | 6/23 | 0 |

**The majority baseline — a model that predicts the class prior and nothing else — was selected
at three of eight reselections.** The one-standard-error rule prefers the simplest candidate
within one standard error of the best inner score, so this says that under the pre-specified
rule, more complex models did not earn enough selection advantage to displace predicting the
base rate. It is a statement about the selection rule's verdict, not a significance test, and it
is not the same as proving those models statistically indistinguishable from the baseline.

Appendix A.4.1 of the protocol notes in advance what those steps mean for the positions, and
2019 against 2020 is the clearest illustration. In both, the baseline was selected, so `mu_hat`
was a per-step constant. In 2019 it never cleared the cost band and participation was **0%**. In
2020 the same kind of constant cleared it on **60%** of sessions, contributing −1.4% for the
year.

Two inputs moved, and which one mattered is a measurable question rather than a rhetorical one.
Note first that `mu_hat` is re-estimated at **every outer step**, not at every reselection, so
comparing two chosen refits cannot account for a year: across the twelve baseline steps in 2019
it ranged from 7.3e-5 to 2.8e-4, and across 2020's from 2.8e-4 to 5.2e-4. Averaged over each
year's baseline sessions, `mu_hat` went from 1.84e-4 to 4.09e-4 — a factor of **2.22** — while
the threshold went from 4.148e-4 to 4.027e-4, a fall of **3%**, because the band is dominated by
the 4 bp execution round trip and financing is the small part of it.

Holding one input at its 2019 level at a time settles it:

| 2020 baseline sessions active | |
|---|---:|
| actual — 2020 `mu_hat`, 2020 threshold | **59.7%** |
| 2019 `mu_hat` level, 2020 threshold | **0.0%** |
| 2020 `mu_hat`, 2019 threshold | **49.8%** |

**At 2019's drift estimate nothing would have traded at all, whatever the rate environment
did.** The exposure arose jointly from the updated unconditional-return estimate and a lower
financing threshold, with the return estimate accounting for the large majority of it, and no
feature discrimination is involved in either. It is flagged in `selection_log.csv` rather than
presented as a strategy result.

The feature layer was more stable than the model layer. Of 81 candidates, 45 were selected at
least once and **15 were selected in at least 80 of 89 steps**; nine appeared in all 89:
`vix_regime_low`, `vix_regime_high`, `YC_2Y10Y_z_60`, `Volatility_60`, `TNX_z_60`,
`high_low_range`, `intraday_ret`, `volume_z_20`, `SMA_gap_50`. **Feature-selection outputs were
relatively stable, but that stability did not translate into stable model selection or into
detectable out-of-sample value.** Stability of a screening output is not evidence that the
screen is correctly identifying predictive variables; a screen that consistently ranks the same
uninformative variables highest would look the same from here.

---

## What this licenses, and what it does not

**Licensed.** Over 2019–2026, under this execution specification and at an assumed all-in cost
of 2 bp per side, a nested walk-forward over 81 features and 23 model configurations produced no
detectable incremental value against unconditional exposure to the same segment, and no
detectable excess over cash. The realised gross positioning contribution was negative. Two
diagnostics of predictive skill computed independently of the P&L provide no compelling
corroborating evidence of it.

**Not licensed.** That no such signal exists. **P1 did not provide evidence of stable
incremental value under the frozen specification, in this sample, at this cost level.** The
sample's resolution is limited and stated in advance: Section 0.1 gives an out-of-sample
standard error on the Sharpe ratio of roughly 0.39, so a true Sharpe of about 1.09 would be
needed for 80% power, and Condition A's interval accordingly spans −0.519 to +0.806. Under those
constraints, an effect materially smaller than that threshold would not be reliably detected
here. What the sample cannot do is separate "small or no true effect" from "a true effect this
design lacks the power to see". **The study does not determine the effect size precisely**: it
reports a point estimate and an interval for it, and the interval is wide. The correct statement
is "not supported", not "does not exist".

**Also not licensed.** Any claim that the procedure is a cost-aware filter worth deploying. Its
positive point estimate against always-long comes from not trading, and against cash it is
negative.

---

## Limitations

**The evaluation window was not untouched.** Benchmark diagnostics were computed on it before
the procedure was specified, and they shaped the two-condition structure. Section 0.2 records
this, and bounds it: recomputed on the training window alone, all three design judgements hold
and hold more strongly. The claim made is that the procedure was fixed, not the result.

**Yahoo's open and close are daily proxies.** They do not guarantee the price a market-on-open
or market-on-close order receives. The 2 bp is an assumed all-in cost, not a measured one, and
the cost scenarios carry that uncertainty.

**One instrument, one frequency, one specification.** The alternative close-to-close execution
specification and 24 exploratory specifications are pre-registered and have not been run. None
of them can change this headline.

**Financing is charged at the full risk-free rate** for the hours a position is open. A
collateralised overlay would pay less; that variant is a pre-declared sensitivity worth about
0.53% a year at full participation.

---

## Reproduction

```bash
pip install -r requirements.txt
python scripts/verify_hashes.py          # snapshot, configuration, and the hashes the protocol quotes
python scripts/run_p1.py                 # ~20 minutes
python scripts/evaluate_p1.py
```

The state of the repository at the moment the design was fixed, before any model had been
fitted, is tagged `protocol-v6-frozen`; `protocol-v5-frozen` is retained alongside it. At those
commits `results/` contains the benchmarks and the registry and no strategy result. Every run,
including two engineering smoke tests excluded from the trial budget, is recorded in
`results/experiment_registry.csv`.

**One of the twenty-five budgeted trials has been used. No further model was searched after this
result.**
