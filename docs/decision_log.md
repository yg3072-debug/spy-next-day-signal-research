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

---

## D-005 — `δ` fixed at zero rather than selected

**Date:** 2026-08-24 · **Status:** Active, supersedes the v5 grid

The no-trade band is `(1+δ)(2c + f_t)` with `δ = 0`, so the rule is exactly "trade when the
prediction covers what the trade costs". `δ` was a grid of {0, 0.5, 1, 2} in protocol v5.

**Alternatives considered.** Keep the grid; raise the active-position floor from 30 to a
participation percentage; fix `δ` at zero.

**Rationale.** An engineering smoke test under v5 showed the inner cross-validation was choosing
a model and a trading frequency in the same pass. `δ` drives participation directly, so the
winning candidate was reliably whichever traded least: at the median, 28 active positions in a
500-session inner out-of-sample, ranked first of 92. A Sharpe estimated on 28 non-zero
observations and selected as the maximum of 92 is not a quantity to build on.

Raising the active-position floor was rejected because 15% would have been a threshold picked to
fit the diagnostic, and it would have added "must trade frequently" to the hypothesis space.
Fixing `δ` removes a researcher degree of freedom instead of adding a constraint. The margins
moved to the exploratory group, where E12b reports all three.

The diagnostic that prompted this came entirely from inner cross-validation inside the training
block; no out-of-sample information entered it. Full record in the protocol's version record.

---

## D-006 — The Loughran–McDonald dictionary is fetched, not vendored

**Date:** 2026-08-24 · **Status:** Active

`scripts/fetch_lexicon.py` downloads the dictionary and verifies its SHA-256; the file is not
committed, and `src/altdata.py` refuses to run against a mismatch.

**Alternatives considered.** Commit the CSV; depend on a package that bundles it; write a word
list for this project.

**Rationale.** The dictionary is free for academic use and requires a licence for commercial
use. This repository is MIT-licensed, so shipping the file inside it would misstate what a
reader may do with the result. Reproducibility does not require redistribution — it requires the
same bytes and a way to check they are the same bytes, which the recorded hash provides. A
bespoke word list was rejected because it would add a researcher degree of freedom to a layer
whose whole appeal is that someone else fixed the vocabulary years earlier.

The same reasoning was applied afterwards to the per-document text, which is third-party content
and is likewise not redistributed; the session-level aggregates the study consumes are committed
instead. See D-007.

---

## D-007 — Alternative-data aggregates committed, per-document text not

**Date:** 2026-08-24 · **Status:** Active

`data/alt/` carries the session-level feature tables and the manifest. The 14,145 scraped posts
and 18,153 headlines are not committed.

**Alternatives considered.** Commit everything; commit nothing and require a re-scrape.

**Rationale.** Whether to redistribute third-party content is the publisher's decision, not this
project's, and public accessibility does not make redistribution so. Committing nothing would
have made every downstream result unreproducible from a clone. The aggregate is what the study
actually consumes, so committing it preserves reproducibility of everything downstream of the
text while leaving redistribution to the source. Source checksums are in the manifest, and the
feature builders fall back to the committed aggregate when the raw files are absent — verified
by hiding them and rebuilding.

---

## D-008 — The close-to-close position rule is a one-step optimum, specified in an addendum

**Date:** 2026-08-24 · **Status:** Active, supersedes a fixed-threshold implementation

`w_t = argmax over {−1, 0, +1} of [ w(μ̂_t − rf_t) − c|w − w_{t−1}| − b_t·max(−w, 0) ]`.

**Alternatives considered.** A fixed band on `|μ̂ − rf|`, as the primary specification uses; a
band with a selectable margin; a dynamic-programming optimum.

**Rationale.** The protocol pre-registered the close-to-close target, information lag, cost
function, borrow accrual and exploratory status, but not how `μ̂` becomes a position. The first
implementation used a fixed threshold and was **wrong, not merely unspecified**: under `c|Δw|`
costs, holding costs nothing, opening costs `c` and reversing costs `2c`, so one number compared
against `|μ̂|` prices all three transitions identically and would pay `c` to exit positions with
a positive expectation. The one-step optimum prices each transition at what it costs and has no
free parameter — `δ` does not exist in it and passing one raises.

A dynamic-programming optimum was rejected because choosing a lookahead horizon would be a
search over the trading rule of a specification that is already exploratory. The rule is greedy
in the one-step sense and says so.

**This decision was made after P1 and before any close-to-close return was computed.** That is
the weaker of the two pre-registration claims and the only true one; registry rows carry
`specified_before_p1=false` and `specified_before_own_results=true`. Full statement in
`docs/c2c_exploratory_addendum.md`.

---

## D-009 — Truth Social is described, not traded; and not re-scraped

**Date:** 2026-08-24 · **Status:** Active

No trading test is run on the Truth Social sample, and the archive was not re-collected to close
its four-month gap against the market snapshot.

**Alternatives considered.** Compress the training block and run a test anyway; re-scrape to
extend coverage; re-scrape with a better extractor.

**Rationale.** Measured on P1's own returns, 246 out-of-sample sessions give a paired bootstrap
standard error of 1.149 on a Sharpe difference, so only a difference above about 2.25 would be
distinguishable. A procedure that can only report significance when it sees a Sharpe of 2.25 is
not a test. Re-scraping the 83 missing sessions moves that threshold to 2.16 — measured, not
assumed — so it cannot change the conclusion and costs roughly 14,000 requests.

A **sample** was collected instead, to answer a question the archive alone could not: whether the
26.5% of rows with empty text are text-free posts or extraction misses. Reading
`div.status__content` directly rather than matching patterns against flattened page text, and
validating on 49 rows where the old extractor did succeed (100% agreement), 148 empty rows
contained **zero** extraction misses. The sample also found that 92.6% of text-free posts carry a
video transcript the study does not use — recorded as a pre-registrable direction rather than
added, since adding a feature source after seeing a null result is the move §7.2 exists to
prevent.
