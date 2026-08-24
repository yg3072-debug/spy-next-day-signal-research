# Daily Directional Signals in SPY

[![tests](https://github.com/yg3072-debug/spy-next-day-signal-research/actions/workflows/tests.yml/badge.svg)](https://github.com/yg3072-debug/spy-next-day-signal-research/actions/workflows/tests.yml)

A study of whether information available at one session's close predicts the direction of SPY's
next open-to-close return well enough to survive realistic trading costs.

The research protocol is frozen and hashed before the confirmatory procedure runs, so the claim
that the method was not tuned to the answer is something a reader can verify rather than take
on trust.

> **Status.** The confirmatory procedure was frozen at
> [`protocol-v6-frozen`](../../releases), run **once**, and is reported in
> [`reports/p1_confirmatory_result.md`](reports/p1_confirmatory_result.md). **No second
> confirmatory model was searched after the result**, which is the commitment that
> matters and the one a reader should check.
>
> The pre-registered exploratory group has since been run in full and is reported in
> [`reports/exploratory_results.md`](reports/exploratory_results.md) — all of it, in
> specification order, including the rows that beat the confirmatory result. It cannot
> change the headline and does not. The alternative-data layer is in
> [`reports/alternative_data_appendix.md`](reports/alternative_data_appendix.md).
> `results/experiment_registry.csv` records **46 realised strategy paths across 36
> specification families** — 20 retraining specifications, 14 position rules, 10 news
> arms, the confirmatory run, and one voided run whose result was inspected before it
> was discarded. That last one is in there because a number that was looked at counts,
> and leaving it out would quietly shorten the ruler.

---

## The question

> Using only information available at the close of session *t*, can the direction of SPY's
> session *t+1* open-to-close return be predicted well enough to produce a measurable increment
> over unconditional exposure to the same segment, after realistic costs?

Success here is not a profitable strategy. It is a defensible conclusion — every choice
justified in advance, out-of-sample performance reported with confidence intervals, and every
comparison made on identical terms. **"No support after costs" is a valid outcome and the more
likely one.** It is reported as such, without a second search.

---

## The answer

**Neither pass condition is met: insufficient evidence of a stable incremental value.** Over
1,865 out-of-sample sessions the Sharpe difference against always-long open-to-close is +0.164
with a paired bootstrap lower bound of −0.519, and the annualised mean excess over cash is
−1.32% with a lower bound of −7.32%. Annualised means and Sharpe ratios are stated in excess of
cash; CAGR, terminal wealth and drawdown come from total returns including the cash leg. The two
conventions are identified by metric and never used interchangeably.

The verdict is not the interesting part. This is:

```
mean-return excess over always-long, decomposed     annualised, paired intervals

    gross positioning   −3.97%   [−11.51%, +3.58%]  ← the only term bearing on prediction
    cost saving         +6.73%
    financing saving    +0.34%
    ──────────────────────────────────────────────
    net                 +3.11%   [ −4.45%, +10.55%]
```

**The entire positive point estimate over always-long comes from saving execution cost and
financing; the realised gross positioning contribution is −3.97%.** Both intervals span zero, so
neither number establishes anything about true ability in either direction — and the net figure
is a difference of *mean returns*, a separate statistic from Condition A's difference of *Sharpe
ratios*. Two diagnostics computed without touching the P&L give no compelling corroborating
evidence of skill: a Brier skill of +0.0122 against a training-base-rate reference, for which no
interval was pre-specified, and a regression slope of realised on predicted return of −0.085
with an interval of [−1.005, +0.891] — far too wide to read as anti-prediction. The verdict
holds at block lengths 20, 10 and 5.

The protocol fixed the wording for this case before the run. Where a net excess is significant
but the positioning term is not, the available conclusion is that a cost-aware participation
filter beats forced daily trading, not that a signal was found. Here even that is unavailable.

What this does **not** license is a claim that no such signal exists. The finding is that P1 did
not provide evidence of stable incremental value under the frozen specification, in this sample,
at this cost level. Section 0.1 states in advance that a true Sharpe of roughly 1.09 would be
needed for 80% power here, so this sample cannot separate "small or no true effect" from "a true
effect it lacks the power to see". The study does not determine the effect size precisely — it
reports a point estimate and a wide interval. "Not supported" and "does not exist" are different
findings, and only the first is in evidence.

---

## The row that is not the headline

The pre-registered exploratory group has been run in full. One of its specifications —
LightGBM held fixed for the whole sample instead of reselected — returned **+3.74% a year at a
Sharpe of +0.357 and turned one dollar into 1.564**, against cash's 1.235 and the confirmatory
procedure's 1.086. It is the best number in the study.

It is reported, in specification order, alongside every other row, and it is not the finding:

- its Sharpe difference against the confirmatory run is +0.501 with an interval of **[−0.107, +1.138]**
- it is the maximum of **34 comparable realised strategy paths**, and an independence-based
  descriptive reference puts the expected maximum at **+0.609**. That is a statement of scale,
  not a test: the paths are strongly correlated, so they are nowhere near 33 independent draws,
  and the expression assumes the independence they lack
- fixing one model family for the whole sample **requires knowing in advance which family to
  fix**; the selection rule chose LightGBM at two of eight reselections and nothing at the other
  six pointed to it
- all four family-fixed runs also drop the prior-only baseline from the **selector's** candidate
  set — the trading rule can still produce Flat — and participation rises to 44.9% from 33.2%, so
  whether the gain comes from the model or from holding a position more often **is not identified
  by this design**

**What calibrates the whole table is the seed.** Three runs differing from the confirmatory
procedure *only* in the random seed give Sharpe ratios of −0.297, −0.141 and −0.175 against its
−0.144 — a range of **0.156** from changing nothing at all. Eight of the sixteen open-to-close
specifications differ from it by less than that, which means removing an entire feature group can
move the result less than reseeding the random number generator does.

Full table and reasoning: [`reports/exploratory_results.md`](reports/exploratory_results.md).

---

## What is measured before anything is modelled

The benchmark layer runs first, by design: a bar computed after seeing a strategy is a bar you
can shop for. These are the numbers the strategy will have to clear, committed before the
strategy exists.

Out-of-sample, 1,866 sessions (2019-03-21 to 2026-08-21), 2 bp per side plus financing, excess
of cash. These were committed before the confirmatory procedure existed and are left as they
were computed.

One reconciliation, because the same benchmark appears twice in this repository with two
values. The table below covers 1,866 sessions indexed by the session a position is *held* in.
The head-to-head comparison in the report covers P1's 1,865 out-of-sample rows, which are
indexed by the *decision* date and therefore stop one session earlier, since the last modelling
session has no next session to predict. Always-long open-to-close is −4.23% on the first window
and −4.43% on the second. Same rule, same costs, windows offset by one session at each end. The
report uses the second because a comparison has to be on identical rows.

| Benchmark | Annualised excess | Sharpe | 95% interval | Breakeven cost |
|---|---:|---:|---:|---:|
| Cash | 0.00% | undefined | — | — |
| **Always-long, open to close** | **−4.23%** | **−0.295** | [−0.853, +0.234] | **1.16 bp/side** |
| Prior-day direction | −18.77% | −1.308 | [−1.961, −0.595] | negative |
| 5-day momentum | −17.40% | −1.211 | [−1.860, −0.614] | negative |
| 5-day reversal | −3.82% | −0.266 | [−0.919, +0.377] | 1.24 bp/side |
| **SPY buy-and-hold** | **+14.01%** | **+0.719** | [+0.101, +1.470] | — |

Three things follow, and they shaped the rest of the design.

**No simple intraday rule is profitable at the assumed cost.** With execution cost set to zero
but financing still charged, only two have any gross edge at all, and their breakeven costs —
1.16 and 1.24 bp per side — sit below the 2 bp base case. The intraday segment does not support
daily round-trip trading.

**Even "always-long loses money" is not statistically established.** Its Sharpe interval spans
zero. Over 7.4 years of daily data, on a single instrument, that is what the evidence supports.
The protocol states in advance that this study cannot confirm a moderate signal, and this is
what that limitation looks like in practice.

**A strategy that never trades beats always-long by 4.23% a year** at the base cost, entirely
through not paying costs, with a strictly negative gross positioning contribution. That is why
the pass conditions are two — a relative one and an absolute one — and why any excess must be
reported split into a positioning term and a cost-saving term. Beating a loss-making benchmark by trading
less is not a signal, and the protocol will not let it be written up as one.

---

## Why the method is checkable

**The protocol is hashed and frozen before the procedure runs.** `docs/research_protocol.md`
fixes the execution specification, the target, the nesting order, the cost model, the pass
conditions and the trial budget. `config/p1.yaml` fixes every remaining degree of freedom — the
inner splitter and its test size, the parameter grids, the calibration sub-splitter, how the
one-standard-error band is computed, the ordering that breaks ties inside it, and what happens
when a candidate degenerates. Its SHA-256 is recorded in the protocol and in every run
manifest. A later edit changes the hash and is visible.

**No look-ahead, verified rather than argued.** The whole feature matrix is rebuilt on truncated
history at three cut points and every overlapping value must be bit-identical. A centred window,
a backward fill or a full-sample statistic cannot survive that, whatever its formula looks like.

**The nesting is strict.** Label thresholds, feature selection, scaling, calibration and the
trading threshold are all estimated inside each fold's own training slice — inside the *inner*
folds, not only inside the outer ones. Outer-validation results never feed back into any choice
made for that step.

**Costs are complete and the trading rule knows about them.** Entering at the open and exiting
at the close is a round trip, not a rebalance, so an active day pays `2c`. Capital in equity
forgoes bill interest, so it also pays financing, built from session length rather than scaled
off a daily rate that already spans weekends. Both terms sit inside the no-trade threshold, not
only in the P&L: a band built from execution cost alone admits trades that clear the spread but
not the financing, and those lose money in expectation.

**The evaluation window is not claimed to be untouched.** Benchmark diagnostics were computed
on it before the procedure was specified and they influenced the design. The protocol says so,
and then bounds what it cost: recomputed on the training window alone, all three design
judgements hold, and more strongly. What is claimed is the weaker and verifiable thing — the
procedure is fixed, not the result.

**102 tests** run on every commit, including two coverage contracts: every output the
configuration declares must exist and carry its columns, and every trial identifier the
protocol registers must have a status in the registry. Both exist because both gaps
happened — silently — and neither failed anything at the time.

**Errors found after the run are listed in [`docs/errata.md`](docs/errata.md), classified
by what they affected.** None affected P1's positions or returns; one affected an
exploratory run, whose incorrect execution is retained in the registry and counted.

---

## Layout

```
config/     p1.yaml + its SHA        the confirmatory procedure, fully determined
            exploratory/             the pre-registered E group, as overlays
            altdata/                 the section 9.1 news arms
data/       frozen market snapshot, manifest and checksum
            alt/                     session-level alternative-data aggregates
docs/       research_protocol.md     the frozen protocol
            c2c_exploratory_addendum.md  the close-to-close position rule
            data_availability.md     publication time to usable time, per field
            feature_dictionary.md    generated from the metadata registry in code
            alt_feature_dictionary.md    likewise, for the text features
            scraping_notes.md        alternative-data lineage and repair
            decision_log.md          every methodological decision and its rationale
            errata.md                every error found after the run, by impact
reports/    p1_confirmatory_result.md   the confirmatory result
            exploratory_results.md       the E group, in full
            alternative_data_appendix.md the text layer
results/    benchmarks, the confirmatory run, every exploratory run, the registry
scripts/    freeze_*, build_*, run_*, evaluate_*, verify_hashes, registry
src/        features.py, altdata.py, execution.py, pipeline.py, stats.py, strategy.py
tests/      102 checks
```

---

## Reproducing

```bash
pip install -r requirements.txt

python scripts/freeze_market_data.py --verify   # confirm the snapshot checksum
python scripts/build_benchmarks.py              # rebuild every benchmark and interval
python scripts/build_docs.py                    # regenerate the feature dictionary
python scripts/run_p1.py                        # the confirmatory run, ~20 minutes
python scripts/evaluate_p1.py                   # the two conditions
pytest tests/ -q

# the exploratory group, which cannot change the result above
python scripts/fetch_lexicon.py                 # Loughran-McDonald, verified by hash
python scripts/run_exploratory_positions.py     # the arms that need no refit
python scripts/run_exploratory_batch.py --workers 6
python scripts/evaluate_exploratory.py
python scripts/run_exploratory_batch.py --dir config/altdata --out results/altdata --workers 5
python scripts/evaluate_news_increment.py
```

The snapshot is committed, so nothing above touches the network. `freeze_market_data.py`
without `--verify` re-downloads and writes a new snapshot; that is a new data vintage and a new
research run, not a reproduction.

Dependencies are pinned to exact versions. Yahoo Finance revises adjusted history after
corporate actions, and library defaults change between releases; a study that downloads at
runtime cannot be reproduced by a third party and cannot attribute its own results.

---

## Deliberately absent

A full deflated Sharpe ratio and PBO, because the candidates are strongly correlated and the
effective number of independent trials would need its own argument — a descriptive
multiple-testing reference is reported instead. A regression target, which would have to be
pre-registered in parallel rather than added after a classification result. Pre-trained language
models for the alternative-data appendix, where a lexicon already answers whether there is an
increment. **A trading test on the Truth Social sample**: measured on P1's own returns, 246
out-of-sample sessions give a paired bootstrap standard error of 1.149 on a Sharpe difference,
so only a difference above roughly 2.25 would be distinguishable from zero. Running one anyway
and reporting whatever Sharpe emerged is exactly the noise this protocol exists to prevent, and
the sample is described rather than traded.

Each is named in the protocol with what it is, why it would matter here, and why it is not in
this round.

---

## Licence

MIT. Research code for educational purposes; not investment advice.
