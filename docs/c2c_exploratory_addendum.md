# Close-to-Close Execution — Exploratory Addendum

**Status: specified after P1, and before any close-to-close return was computed.**

This is the weaker of the two pre-registration claims and the only one that is true here. It is
stated in those words rather than compressed into "pre-registered", because the two are not the
same and a reader who assumes the stronger one has been misled by the omission.

Every row this addendum produces carries, in `results/experiment_registry.csv`:

| Flag | Value |
|---|---|
| `specified_before_p1` | **false** |
| `specified_before_own_results` | **true** |
| `cannot_modify_p1_headline` | **true** |

---

## 1. Why an addendum is needed at all

Section 2.2 of the research protocol pre-registers, before P1 ran, all of the following:

- the target, `R^C2C_{t+1} = Close_{t+1} / Close_t − 1`
- the information lag: features from *t−1*, because the signal must exist before the close it is
  executed at
- the cost function, `c·|Δw|`, with opening and final closing costs included
- the borrow charge, 25 bp annual, accrued over the **calendar** days a short is carried
- the assignment of E22–E24 to the exploratory group, with the explicit statement that even a
  clear result there cannot rescue a primary that failed

It does not specify **how `mu_hat` becomes a position.** That is a real gap, not a formality:
the position rule determines participation, turnover and therefore almost all of the cost, and
leaving it open would let it be chosen after seeing what it produced.

## 2. What is fixed here, and when

This document was written before any close-to-close return series was computed. The chain of
custody is recorded because the claim is only worth what it can be checked against:

1. A first implementation of this specification existed and used a fixed threshold. It was
   **wrong**, for the reason given in §3, and it is registered rather than deleted.
2. That implementation was exercised only in **smoke mode**, which by design reports no
   performance figure. Its output directory was removed. No close-to-close return, Sharpe ratio
   or P&L was computed or inspected under it, and none exists in the repository history.
3. The E22–E24 overlays were moved out of the batch directory before the batch could reach
   them, so no full run was ever started under the first rule.
4. This document was then written, the rule below fixed, the repository tagged, and only then
   were the specifications run.

Step 1 is the part worth being explicit about. The first rule was not abandoned because its
results were disappointing — it produced no results. It was abandoned because it was shown to be
the wrong shape for the cost function the protocol had already fixed.

## 3. The position rule

**A single fixed threshold cannot serve this cost function.** Under `c·|Δw|` the three
transitions cost different amounts: holding a position costs nothing, moving from flat to a
position costs `c`, and reversing costs `2c`. A rule that compares `|mu_hat|` against one number
prices all three identically. The first implementation did exactly that, and it would have
exited positions it should have held — paying `c` to give up a positive expectation.

The rule is the one-step optimum over the three admissible positions:

```
w_t  =  argmax          w · (mu_hat_t − rf_t)  −  c · |w − w_{t−1}|  −  b_t · max(−w, 0)
        w ∈ {−1, 0, +1}
```

where

| Term | Definition |
|---|---|
| `mu_hat_t` | the predicted close-to-close return, from the same calibrated probabilities and class-conditional means P1 uses |
| `rf_t` | the risk-free accrual over the holding period, so the objective is in excess of cash |
| `c` | execution cost per side, `base_bps_per_side / 10⁴` |
| `b_t` | `borrow_annual_bps / 10⁴ × (calendar days from t to t+1) / 365`, charged only on a short |
| `w_{t−1}` | the position actually held into t, with `w_{−1} = 0` |

**This rule has no free parameter.** No margin, no threshold, no `δ`. `δ` is not merely fixed at
zero here — it does not exist in the rule, and passing a non-zero value raises rather than being
silently ignored. A margin would be a search over the trading rule of a specification that is
already exploratory, and the confirmatory procedure was changed in v6 precisely to stop that.

Two properties follow, and both are pinned by tests rather than asserted:

**With no borrow charge, flat is dominated from a held position.** Holding against an adverse
edge `e < 0` is worth `e`; going flat costs `c`; reversing costs `2c` and earns `|e|`. Flat beats
holding only when `|e| > c`, which is the same condition under which reversing beats flat. The
rule therefore holds or reverses, and never parks in between. Charging borrow restores flat as a
choice on the short side.

**The rule is greedy in the one-step sense.** It does not look ahead to the cost a position
would save tomorrow, so it is not the dynamic-programming optimum. That is a stated property,
not a tuned one, and it is left alone: fitting a lookahead horizon would be exactly the search
this addendum exists to prevent.

## 4. Cost accounting

```
R^net_t  =  w_t · (R^C2C_t − rf_t)  −  c · |w_t − w_{t−1}|  −  b_t · max(−w_t, 0)
```

- `w_{−1} = 0`: the first row is charged for opening whatever it opens.
- The final row is additionally charged `c · |w_T|`, closing the book. A backtest that ends
  holding a position and never pays to leave it has borrowed a basis point from the future.
- Borrow accrues over calendar days, so a short carried across a weekend is charged three days,
  and one carried over a long weekend four.

## 5. The three specifications

| ID | Change from the addendum base case | What it isolates |
|---|---|---|
| **E22** | none — 2 bp per side, 25 bp borrow | the specification itself |
| **E23** | 5 bp per side | cost sensitivity, which should be far lower than the primary specification's because this one trades far less |
| **E24** | borrow set to 0 | how much of the result is the general-collateral charge rather than the positions |

Everything else — features, feature selection, the model grid, the one-standard-error rule, the
walk-forward schedule, calibration, seeds — is inherited unchanged from `config/p1.yaml`.

## 6. What this cannot do

It cannot change the P1 headline, in either direction, and no result below will be presented as
doing so. Protocol §2.2 already says why: this is a different strategy, not a robustness check.
It holds a different asset exposure over a different interval with a different cost function,
and its dominant source of return is the overnight move, which the primary specification never
touches.

A positive result here is a reason to **pre-register close-to-close as a future primary** and
test it on data none of this has seen. It is not a result that can be reported as this study's
finding, and the distinction is the entire point of separating the two groups in advance.

Each of E22, E23 and E24 produces one realised strategy path and is registered with its own
`subrun_id`, so the descriptive count of paths examined includes them.
