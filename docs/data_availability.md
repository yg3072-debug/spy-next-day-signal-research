# Data Availability

When each input is published, when a strategy running in real time could actually use it,
and every transformation applied between the two. A field may only enter a feature for
session *t* if the whole pipeline below is complete before the decision point for *t*.

**Snapshot:** `data/market_inputs_2026-08-21.csv`
**SHA-256:** `103a837de14b5226283c2b13f6ff0781def29565eec9f9d4ae8fc23510ffa507`
**Sessions:** 2,926 — 2015-01-02 to 2026-08-21 (11.6 years), 23 early closes
**Manifest:** `data/market_inputs_2026-08-21.manifest.json`
**Reproduce:** `python scripts/freeze_market_data.py` · **Check:** `... --verify`

---

## 1. Decision points

The study evaluates two execution specifications. Each has a different information cut-off,
so the same field can be available under one and not the other.

| Specification | Information cut-off | Signal generated | Order | Return captured |
|---|---|---|---|---|
| **Primary** | session *t* close, 16:00 ET | after *t*'s close | market-on-open at *t+1*, closed market-on-close at *t+1* | `log(Close_{t+1} / Open_{t+1})` |
| **Alternative** | session *t−1* close | before *t*'s close | market-on-close at *t* | `log(Close_{t+1} / Close_t)` |

Orders are assumed submitted ahead of the applicable broker and exchange auction cut-off.
The exact cut-off differs by venue and by broker and is not modelled to the second.

---

## 2. Field-level availability

`Available for` states the earliest session whose *open* can be traded on the field's value,
under the primary specification.

| Column | Source | Native publication | Latency | Available for | Notes |
|---|---|---|---|---|---|
| `Open` `High` `Low` `Close` | Yahoo — SPY | consolidated tape, final at 16:00 ET session close | same session | *t+1* open | split- and dividend-adjusted |
| `Volume` | Yahoo — SPY | 16:00 ET | same session | *t+1* open | **not** adjusted for splits |
| `VIX` | Yahoo — `^VIX` | CBOE, 16:15 ET (index disseminated to 16:15) | same session | *t+1* open | close value only |
| `DXY` | Yahoo — `DX-Y.NYB` | ICE US Dollar Index | same session | *t+1* open | spot index, trades on a calendar that differs slightly from NYSE |
| `TNX` | Yahoo — `^TNX` | CBOE 10-year Treasury yield index | same session | *t+1* open | quoted as yield × 10 |
| `OIL` | Yahoo — `BZ=F` | ICE Brent front-month futures | same session | *t+1* open | **primary oil factor** — see §4 |
| `OIL_WTI` | Yahoo — `CL=F` | NYMEX WTI front-month futures | same session | *t+1* open | reference only, retained for sensitivity |
| `QQQ_Close` `IWM_Close` `DIA_Close` | Yahoo | 16:00 ET | same session | *t+1* open | adjusted closes |
| `DGS2` `DGS10` | FRED | H.15, published **the following business day** around 16:15 ET | **one business day** | *t+2* open | see §3 |
| `is_half_day` | NYSE calendar | known years in advance | none | any | 1 = early close (13:00 ET) |

### 2.1 The one field with a real publication lag

`DGS2` and `DGS10` come from the Federal Reserve H.15 release. The value **dated** *t* is not
published until the following business day. A strategy deciding after *t*'s close therefore
knows the yields dated *t−1*, not *t*.

**Every feature built from `DGS2` / `DGS10` must be lagged one additional session** relative
to the price-based features. This is enforced in the feature layer, not in the snapshot — the
snapshot stores the values on their nominal dates so the lag stays visible and auditable
rather than baked in.

The 2-year and 10-year yields are slow-moving; the practical effect of the extra lag is small.
That is not a reason to skip it.

---

## 3. Calendar and alignment

**Spine.** Sessions come from the NYSE calendar via `pandas_market_calendars`, not from the
intersection of the downloaded series. An intersection silently drops any session where one
series is missing, and reports nothing about it.

**Gap policy.** Forward fill only, limit 5 sessions. Backward filling would move future values
into the past. Every filled cell is counted in the manifest.

**Completeness after alignment.** SPY is present on all 2,926 sessions with no interior gaps —
this is asserted, and the freeze fails if it does not hold. Remaining fills:

| Series | Sessions forward-filled | Reason |
|---|---:|---|
| `DGS2`, `DGS10` | 21 each | Columbus Day and Veterans Day — SIFMA bond-market holidays on which NYSE trades |
| `DX-Y.NYB` | 2 | ICE holiday calendar differs from NYSE |
| `BZ=F` | 2 | ICE Futures Europe holiday calendar |
| `CL=F` | 2 | NYMEX holiday calendar |
| `^TNX` | 1 | CBOE index not disseminated |
| all others | 0 | — |

Total filled cells: 49 out of 43,890 (0.11%). No gap exceeded the 5-session limit; no
unresolved missing values remain.

**Early closes.** 23 sessions close at 13:00 ET (day after Thanksgiving, Christmas Eve, day
before Independence Day). They are flagged rather than dropped: intraday range and volume
features are mechanically depressed on these days, and the flag lets the feature layer decide
what to do about it.

---

## 4. Oil: why Brent rather than WTI

On **2020-04-20**, front-month NYMEX WTI settled at **−$37.63** — the first negative crude
settlement on record, driven by Cushing storage running out days before contract expiry. The
value in the snapshot is correct, not a data error.

Consequences for a sample starting in 2015:

- `log(OIL_t / OIL_{t−1})` is undefined on 2020-04-20 and 2020-04-21
- Any rolling mean, standard deviation, or z-score spanning that date is distorted
- The event is a WTI-specific physical-delivery artefact, not a global oil-price signal

Brent (`BZ=F`) is seaborne and priced on waterborne delivery, so it was unaffected. Over this
sample its daily log returns correlate **0.894** with WTI's, it never traded at or below zero,
and it covers 99.9% of NYSE sessions. Brent is also the more standard global benchmark for
macro purposes; WTI is a US regional benchmark.

**Decision:** Brent is the primary oil factor (`OIL`). WTI is retained as `OIL_WTI` so the
choice can be revisited as a sensitivity without re-downloading. Recorded as **D-002**.

Alternatives considered and rejected: `USO` (never negative and 100% coverage, but severe
contango decay makes its *level* meaningless as a factor); `XLE` (0.567 correlation — it is an
equity sector, not an oil price).

---

## 5. Adjustment

Prices are split- and dividend-adjusted (`yfinance` `auto_adjust=True`). Volume is not.

Two consequences worth stating explicitly:

1. **The primary target is adjustment-invariant.** `log(Close_t / Open_t)` compares two prices
   from the same session, and any multiplicative adjustment factor applies equally to both, so
   it cancels. A later revision to the dividend history cannot move the primary target.
2. **Volume is the one asymmetry.** A dividend revision rescales price but not volume, and
   because every volume feature here is a ratio or a z-score of raw volume, that asymmetry
   cancels. A **split** does not cancel: it changes Volume while leaving the adjusted price
   continuous, distorting any trailing volume window that spans the split date. Verified
   against the dividend and split history: SPY, QQQ, IWM and DIA have no split inside this
   sample, the most recent being IWM in June 2005. `src/features.py` records the exposure per
   feature and `tests/test_features.py` asserts each claim by rescaling the price history.

---

## 6. Known limitations

- **`Open` is a data proxy, not an execution guarantee.** Yahoo's opening price is the official
  opening print. A market-on-open order is filled in the opening auction and may print away
  from it. The gap is not modelled; the transaction-cost scenarios in the protocol are the
  vehicle for that uncertainty.
- **Macro closes are not synchronous with the 16:00 ET equity close.** Brent and WTI futures
  trade nearly around the clock; the dollar index is a spot index. Their daily "close" values
  are venue-specific snapshots taken at different instants. Under the primary specification
  this is tolerable because the whole information set is used only after *t*'s close and traded
  at *t+1*'s open, leaving hours of slack.
- **Survivorship and vendor revision.** Yahoo may revise adjusted history after corporate
  actions. The frozen snapshot fixes one vintage; a re-download at a later date is one leg of
  the planned sensitivity analysis, not the default path.
- **No corporate-action or index-reconstitution data.** SPY tracks the S&P 500; constituent
  changes are not modelled and are assumed to be already reflected in the ETF price.

---

## 7. Provenance summary

| | |
|---|---|
| Downloaded | 2026-08-23 (UTC) |
| Window requested | 2015-01-01 → 2026-08-22 (exclusive) |
| Sessions retained | 2,926 |
| Untraded calendar sessions dropped from the tail | 1 |
| Leading rows trimmed | 0 |
| Python | 3.10.20 |
| pandas | 2.3.3 · numpy 2.2.6 · yfinance 0.2.66 · pandas_market_calendars 5.4.0 |
