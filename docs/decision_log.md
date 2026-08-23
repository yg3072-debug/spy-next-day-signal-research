# Decision Log

Every methodological decision, with the alternatives considered and the reason for the choice.
Append-only: a reversed decision gets a new entry that supersedes the old one, rather than an
edit.

Format: **ID · date · decision · alternatives · rationale · status**

---

## D-001 — Sample window: 2015-01-01 onward

**Date:** 2026-08-23 · **Status:** Active

The study uses 2,926 NYSE sessions from 2015-01-02 to the freeze date, with the first 1,000
sessions reserved as the initial training block. Out-of-sample evaluation therefore begins in
late December 2018 and spans roughly 7.6 years.

**Alternatives considered**

| Start | Sessions | Out-of-sample | IID SE of annualised Sharpe | Crises inside the OOS window |
|---|---:|---:|---:|---|
| 2021-01-01 | 1,415 | ≈ 0.9 yr | ≈ 1.1 | none |
| 2020-01-01 | 1,668 | ≈ 2.6 yr | ≈ 0.66 | 2022 only |
| **2015-01-01** | **2,926** | **≈ 7.6 yr** | **≈ 0.38** | **2020 COVID, 2022 tightening** |

**Rationale.** The binding consideration is not how much history the model sees — a rolling or
expanding training window controls that independently — but how many independent out-of-sample
observations are available to distinguish signal from noise. A single instrument at daily
frequency yields 252 observations per year, the lowest data density of any common quantitative
design, so out-of-sample length is the scarce resource.

A start date of 2020 was considered and rejected on a specific logical ground: with a 1,000-day
initial training block, the COVID period falls entirely inside training, and the stated reason
for choosing 2020 — that the sample should contain a genuine crisis — would not have been
served. Only a 2015 start places both the 2020 and 2022 episodes in the evaluation window.

The standard errors above are rough IID approximations used for design sizing. Final
uncertainty is determined by paired block bootstrap, not by this formula.

---

## D-002 — Brent as the primary oil factor

**Date:** 2026-08-23 · **Status:** Active

`OIL` is ICE Brent front-month (`BZ=F`). NYMEX WTI (`CL=F`) is retained in the snapshot as
`OIL_WTI` for sensitivity analysis but does not feed the primary feature set.

**Rationale.** On 2020-04-20 front-month WTI settled at −$37.63 as Cushing storage ran out
before contract expiry. The value is correct, not a data error, but it has two consequences for
a sample beginning in 2015: any log-ratio return is undefined on 2020-04-20 and 2020-04-21, and
any rolling statistic spanning that date is distorted. The episode is a WTI-specific physical
delivery artefact rather than a global oil-price signal.

Brent is priced on waterborne delivery and was unaffected. Measured over this sample its daily
log returns correlate 0.894 with WTI's, it never traded at or below zero, and it covers 99.9%
of NYSE sessions. It is also the standard global benchmark, where WTI is a US regional one.

**Alternatives considered.** `USO` — never negative, full coverage, 0.889 return correlation,
but severe contango decay makes its price *level* meaningless as a factor. `XLE` — 0.567
correlation; it is an equity sector, not an oil price. Winsorising the WTI print — discards a
real observation and leaves the choice of replacement value arbitrary.

---

## D-003 — Calendar spine and gap policy

**Date:** 2026-08-23 · **Status:** Active

Sessions are taken from the NYSE calendar. Each series is reindexed onto that spine and
forward-filled with a limit of 5 sessions. Backward filling is prohibited. Every filled cell is
counted and published in the snapshot manifest and in `docs/data_availability.md`.

**Alternative rejected.** Joining the series on their intersection. An intersection drops any
session for which any one input is missing, produces a sample whose length depends silently on
the least-available series, and reports nothing about what was lost.

**Result.** 49 filled cells out of 43,890 (0.11%), the largest group being 21 sessions each for
`DGS2` and `DGS10` on Columbus Day and Veterans Day, when the bond market is closed and the
NYSE trades. SPY has no interior gaps; the freeze script asserts this and fails if it does not
hold.

---

## D-004 — H.15 yields carry an additional one-session lag

**Date:** 2026-08-23 · **Status:** Active

Features derived from `DGS2` and `DGS10` are lagged one session beyond the price-based
features. The H.15 release publishes the value dated *t* on the following business day, so a
decision taken after *t*'s close can only use the yields dated *t−1*.

The lag is applied in the feature layer rather than in the snapshot, so that the snapshot
stores each value on its nominal date and the adjustment remains visible and auditable.
