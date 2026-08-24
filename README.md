# Daily Directional Signals in SPY

[![tests](https://github.com/yg3072-debug/spy-next-day-signal-research/actions/workflows/tests.yml/badge.svg)](https://github.com/yg3072-debug/spy-next-day-signal-research/actions/workflows/tests.yml)

A study of whether information available at one session's close predicts the direction of SPY's
next open-to-close return well enough to survive realistic trading costs.

The research protocol is frozen and hashed before the confirmatory procedure runs, so the claim
that the method was not tuned to the answer is something a reader can verify rather than take
on trust.

> **Status.** Data, benchmark, feature and inference layers are complete, tested and committed.
> The confirmatory procedure is specified and frozen at
> [`protocol-v5-frozen`](../../releases) and **has not yet been run**. No strategy result
> exists in this repository.

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

## What is measured before anything is modelled

The benchmark layer runs first, by design: a bar computed after seeing a strategy is a bar you
can shop for. These are the numbers the strategy will have to clear, committed before the
strategy exists.

Out-of-sample, 1,866 sessions (2019-03-21 to 2026-08-21), 2 bp per side plus financing, excess
of cash:

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
through not paying costs, with a strictly negative timing contribution. That is why the pass
conditions are two — a relative one and an absolute one — and why any excess must be reported
split into a timing term and a cost-saving term. Beating a loss-making benchmark by trading
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

**38 tests** run on every commit.

---

## Layout

```
config/     p1.yaml + its SHA — the confirmatory procedure, fully determined
data/       frozen market snapshot, manifest and checksum
docs/       research_protocol.md   the frozen protocol
            data_availability.md   publication time to usable time, per field
            feature_dictionary.md  generated from the metadata registry in code
            decision_log.md        every methodological decision and its rationale
results/    benchmark_comparison.csv, benchmark_intervals.csv
scripts/    freeze_market_data.py, build_benchmarks.py, build_docs.py
src/        features.py, stats.py, strategy.py
tests/      38 checks
```

---

## Reproducing

```bash
pip install -r requirements.txt

python scripts/freeze_market_data.py --verify   # confirm the snapshot checksum
python scripts/build_benchmarks.py              # rebuild every benchmark and interval
python scripts/build_docs.py                    # regenerate the feature dictionary
pytest tests/ -q
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
increment. A trading test on the Truth Social sample: 246 out-of-sample sessions give a standard
error of 1.07 on a Sharpe difference, so only a difference above roughly 2.1 would be
distinguishable, and running one anyway would be exactly the kind of noise this protocol exists
to prevent.

Each is named in the protocol with what it is, why it would matter here, and why it is not in
this round.

---

## Licence

MIT. Research code for educational purposes; not investment advice.
