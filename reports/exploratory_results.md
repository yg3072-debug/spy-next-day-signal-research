# Exploratory Results

**Everything in this document is exploratory. None of it changes the confirmatory
result, in either direction, and none of it is offered as an alternative to it.**

Protocol §7.2 commits to running the exploratory group in full and reporting all of
it. That commitment only costs something once the headline is already negative and
one of these rows looks better — which is what happened, and is why the discipline
is worth writing down rather than assumed.

The tables below are in specification order. Not one is sorted by performance.

---

## 1. The number that calibrates the rest

Three specifications differ from P1 **only in the random seed**. Random forest,
LightGBM and XGBoost are all stochastic and the bootstrap inside the selection rule
is seeded, so these four runs are the same research decision executed four times:

| | P1 | E17 | E18 | E19 |
|---|---:|---:|---:|---:|
| Seed | 20260823 | 20260824 | 20260825 | 20260826 |
| Sharpe | −0.144 | −0.297 | −0.141 | −0.175 |

**Range 0.156, standard deviation 0.073.** That is what this procedure produces
when nothing at all is changed.

Read the rest of the table against it. **Eight of the sixteen open-to-close
specifications differ from P1 by less than the seed range**, which means the
research question they were meant to answer is not resolvable at this sample size:
removing a whole feature group can move the result less than reseeding the random
number generator does.

---

## 2. Every specification

Open-to-close, 1,865 out-of-sample sessions unless noted, 2 bp per side plus
financing, excess of cash. `Δ` is the paired bootstrap Sharpe difference against P1
on shared rows.

| ID | What changed | Sharpe | Ann. mean | Participation | Terminal wealth | Δ vs P1 | 95% interval |
|---|---|---:|---:|---:|---:|---:|---:|
| **P1** | *the confirmatory procedure* | **−0.144** | −1.32% | 33.2% | 1.086 | — | — |
| E1 | cross-market group removed | −0.244 | −2.21% | 34.3% | 1.017 | −0.100 | [−0.432, +0.269] |
| E2 | macro groups removed | −0.779 | −6.66% | 27.2% | 0.734 | −0.635 | **[−1.254, −0.132]** |
| E3 | intraday group removed | −0.203 | −1.84% | 30.6% | 1.045 | −0.059 | [−0.591, +0.423] |
| E4 | volume group removed | −0.170 | −1.54% | 32.1% | 1.069 | −0.026 | [−0.342, +0.275] |
| E5 | logistic only | −0.226 | −2.40% | 43.4% | 0.992 | −0.081 | [−0.850, +0.726] |
| E6 | random forest only | −0.360 | −3.27% | 32.1% | 0.940 | −0.215 | [−0.888, +0.448] |
| **E7** | **LightGBM only** | **+0.357** | **+3.74%** | 44.9% | **1.564** | +0.501 | [−0.107, +1.138] |
| E8 | XGBoost only | +0.226 | +2.42% | 44.4% | 1.416 | +0.370 | [−0.256, +1.011] |
| E13 | rolling 1,000 window | −1.169 | −9.62% | 33.8% | 0.591 | −1.024 | **[−1.806, −0.222]** |
| E14 | initial train 1,500 *(1,365 sessions)* | +0.006 | +0.06% | 41.3% | 1.185 | +0.272 | [−0.577, +1.070] |
| E15 | quarterly refit | +0.061 | +0.49% | 31.9% | 1.250 | +0.205 | [−0.257, +0.705] |
| E16 | isotonic calibration | −0.637 | −6.67% | 47.7% | 0.724 | −0.493 | [−1.081, +0.153] |
| E17 | seed 20260824 | −0.297 | −2.70% | 33.5% | 0.981 | −0.152 | [−0.445, +0.112] |
| E18 | seed 20260825 | −0.141 | −1.29% | 33.4% | 1.089 | +0.003 | [−0.308, +0.346] |
| E19 | seed 20260826 | −0.175 | −1.57% | 32.1% | 1.067 | −0.031 | [−0.436, +0.359] |
| E20 | WTI for Brent *(1,858 sessions)* | −0.031 | −0.31% | 41.6% | 1.163 | +0.057 | [−0.538, +0.634] |
| E21 | second data vintage | −0.156 | −1.38% | 33.0% | 1.081 | −0.012 | [−0.432, +0.369] |

The close-to-close specifications are scored against their own always-long
benchmark and are not compared with P1, because they are a different strategy
holding a different exposure over a different interval — §2.2 is explicit about
this and the comparison would not be meaningful.

| ID | What | Sharpe | Ann. mean | Participation | Terminal wealth |
|---|---|---:|---:|---:|---:|
| E22 | close-to-close, 2 bp, 25 bp borrow | −0.153 | −2.97% | 98.4% | 0.861 |
| E23 | close-to-close, 5 bp | −0.195 | −3.57% | 77.7% | 0.837 |
| E24 | close-to-close, no borrow charge | −0.159 | −3.09% | 98.9% | 0.853 |

**Two of seventeen intervals exclude zero, and both are negative**: removing the
macro groups and switching to a rolling window each make the result reliably worse.
At the 5% level, roughly one such interval would be expected by chance across
seventeen comparisons, so even these two deserve to be read as suggestive.

---

## 3. The row that would have been the headline

**E7 — LightGBM held fixed for the whole sample — returned +3.74% a year at a
Sharpe of +0.357 and turned one dollar into 1.564, against cash's 1.235 and P1's
1.086.** It is the best of everything run in this study.

Presenting it as the finding would require ignoring all of the following.

**Its interval spans zero.** The Sharpe difference against P1 is +0.501 with a
paired interval of [−0.107, +1.138].

**It is the maximum of 33 comparable realised strategy paths** — the 19 retraining
specifications and the 14 position rules, all scored on the same 1,865 sessions.
The 10 news arms are counted in the registry but left out of this spread, because
they run on a 1,247-session overlap and pooling two windows would compare unlike
quantities. Protocol §6.4's descriptive reference asks what the best Sharpe would be
among that many draws of pure noise with the observed spread:

| | |
|---|---:|
| Comparable realised strategy paths | **33** |
| Spread of their Sharpe ratios (sd) | 0.291 |
| **Best observed** | **+0.357** |
| Expected maximum under an **independence-based** reference | **+0.615** |

Under an independence-based descriptive reference, the expected maximum is +0.615
against an observed best of +0.357. **This is not a threshold and not a
significance test.** The 33 paths are strongly correlated — many share a training
window, a feature screen and most of their positions — so they are nowhere near 33
independent draws, and the expression assumes exactly the independence they lack.
Saying "the best result is below what luck would give" would present a descriptive
formula as a formal test, which it is not.

What it is good for is scale. It says the observed maximum is not large relative to
what a set of trials of this size and spread can throw up, which is a reason to be
unimpressed by it rather than a demonstration that it is noise.

**It was not available to be chosen.** E5 through E8 fix one model family for the
entire sample, which requires knowing in advance which family to fix. P1's
one-standard-error rule selected LightGBM at two of eight reselections; nothing
available at any of the other six pointed to it. The specification that produced
+0.357 is only reachable with the answer already in hand.

**Its siblings do not behave like it.** E5 (logistic only) and E6 (random forest
only) return −0.226 and −0.360. All four family-fixed runs also drop the majority
baseline from the candidate set, which removes **the selector's ability to fall
back to a prior-only model** — not the strategy's ability to stand aside, since the
cost band still produces Flat whenever `mu_hat` fails to clear it. Participation
nevertheless rises to 43–45% from P1's 33%. Whether E7's result comes from LightGBM
being the right family or from holding a position more often is not identified by
this design, and nothing here separates them.

---

## 3b. E21 — the data vintage, and what it exposes

E21 downloads the same window a second time and reruns the identical procedure
against it. It was pre-registered in §7.2, omitted when the overlays were written,
and run afterwards; the registry records `delay_reason=implementation_omission`
and `headline_eligible=false`.

The frozen snapshot was not touched. The second vintage was written to its own
directory with its own SHA-256 (`020d9ad9…` against the frozen `9b337ca7…`), with
the end date pinned so it covers exactly the same 2,926 sessions and no later ones.
The two were compared field by field **before** the run, and the run proceeded
regardless, as pre-registered.

**What changed in the data:**

| Field | Cells differing | Largest relative difference |
|---|---:|---:|
| SPY open/high/low/close, QQQ, IWM, DIA | 2,057–2,469 each | ~8 × 10⁻⁷ |
| DGS3MO, DTB3, DGS2, DGS10 | **1 each** | **1.1 × 10⁻²** |

The equity differences are float-level, consistent with rounding inside the
vendor's adjustment. The Treasury revisions are real but land entirely on
**2026-08-21** — the snapshot's final session, where the published figures were
still provisional when the first snapshot was taken.

**What changed in the output is the part worth reading:**

| | |
|---|---:|
| Sharpe, frozen vintage | −0.1444 |
| Sharpe, second vintage | −0.1559 |
| ΔSharpe | −0.0116, interval [−0.432, +0.369] |
| **Sessions with an identical position** | **1,692 of 1,865 (90.7%)** |
| Sessions with an identical selected model | 86.5% |
| Largest `mu_hat` difference | 2.4 × 10⁻³ |

**Differences at the seventh decimal place moved 9.3% of the positions.** The
mechanism is the one the seed replicates already pointed at: the
one-standard-error rule is choosing among candidates that are nearly tied, so an
arbitrarily small perturbation flips which one wins, and a different model produces
different positions for months afterwards.

The distinction this draws is worth stating precisely. **The verdict is robust and
the trades are not.** ΔSharpe of −0.0116 is an order of magnitude inside the 0.156
that reseeding alone produces, so the conclusion does not depend on which vintage
was downloaded. But anyone who read a specific position off this study as a
recommendation would be reading something that a vendor's rounding could have
reversed.

---

## 4. What the ablations do and do not establish

E1 to E4 remove a hypothesis group before selection sees it. Three of the four move
the result by less than the seed range. **E2 is the exception**: removing the
36 macro features costs 0.635 of Sharpe with an interval clear of zero.

That is worth stating carefully. It establishes that the macro block was carrying
something the rest of the feature set could not replace — but the procedure as a
whole still failed both pass conditions with those features included. The reading
is that macro features mattered *relative to a procedure that did not work*, which
is a much weaker statement than that they predict returns.

E20 substitutes WTI for Brent. Front-month WTI settled at −$37.63 on 2020-04-20, so
every log return spanning that date is undefined and those rows leave the modelling
set: 1,858 sessions against 1,865. The Sharpe moves from −0.144 to −0.031, well
inside the seed range. The oil-series choice was made for a stated reason and this
confirms nothing turned on it.

---

## 5. The close-to-close specification

Reported under `docs/c2c_exploratory_addendum.md`, whose position rule was fixed
after P1 and **before any close-to-close return was computed** — the weaker of the
two pre-registration claims and the only one that is true here. Registry rows carry
`specified_before_p1=false`.

All three are negative. The specification trades on 98.4% of sessions at 2 bp,
because a position that persists is not re-paid for and the one-step rule holds
rather than exits: it is a nearly-always-invested overnight strategy, not a
selective one.

The registry carries **45 realised strategy paths across 35 families**, one of which
is a voided run — see below — recorded because its result was inspected before it was
discarded, and a number that was looked at counts.

**E24 is the reason this section needed rerunning.** It sets the borrow charge to
zero to isolate how much of the result is the general-collateral cost. Its first
run came out bit-identical to E22 on every figure — impossible when 493 short
positions are paying a charge one of them removes. The cause was a defect in this
repository, not in the data: `get_spec` returned an object built with default
parameters, so the configured borrow was accepted, written into the run manifest,
and ignored. The overlay was valid, the hash was right, the run succeeded. Nothing
about it looked wrong.

It is fixed, unknown parameters now raise rather than being dropped, two regression
tests cover it, and E24 was rerun. The episode is recorded rather than tidied away
because a configuration that is read, logged and then ignored is the most
comfortable kind of error to have, and the only reason this one surfaced is that
two rows which should have differed did not.

**The corrected E24 comes out slightly worse than E22, not better**, at −0.159
against −0.153, despite removing a cost. That is not a paradox and it is not a
finding. The position rule prices the borrow charge, so removing it changes which
positions are taken: E24 goes short on **9 sessions** where E22 stayed flat, those
being the marginal shorts that a 25 bp charge made not worth opening. On those nine
sessions the close-to-close return averaged **+0.151%** — the market rose — so the
extra shorts lost money.

Nine observations. Stating that the borrow charge improves performance would be
reading a coin flip, and the honest summary is that removing it changes almost
nothing: 9 sessions out of 1,864, and a Sharpe difference of 0.006 against a
seed-only noise floor of 0.156.

The three close-to-close runs are within 0.042 of each other in Sharpe while their
cost assumptions differ by a factor of 2.5 on execution and infinitely on borrow.
The specification is not failing because of what it is charged.

---

## 6. What all of this licenses

Nothing about the confirmatory result. That is the point of the separation, and it
holds whichever direction the exploratory rows had gone.

What the group does establish is about the **procedure**, and it is worth more than
another performance number. At this sample size the design cannot resolve most of
the questions it was pointed at: half the specifications move the result less than
the random seed does. That is not a failure of the exploratory group — it is the
exploratory group doing its job, which is to show how much of the confirmatory
result was ever determined by the choices under study.

A design that could resolve them — a longer sample, a lower-variance target, fewer
features in genuine competition — is a different study. This one now has concrete
reasons to specify it, and those reasons are numbers rather than intuitions.
