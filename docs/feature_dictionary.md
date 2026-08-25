# Feature Dictionary

Generated from the metadata registry in `src/features.py` by `python scripts/build_docs.py`. Edit the registry, not this file.

Every feature is a function of information available at or before the close of session *t*. The target is the next session's open-to-close simple return, `Close_{t+1} / Open_{t+1} - 1`.

**Snapshot:** `market_inputs_2026-08-21.csv` — **not distributed with this repository**
**SHA-256:** `9b337ca75f8d077963448853e97542fab1258ab5b6dd289debec14061012b13a`
**Candidates:** 81 across 13 hypothesis groups · **Sessions:** 2,926

The snapshot named above is the historical frozen input. Its prices are licensed and are not
redistributed here; see `data_availability.md`. The digest is a recorded identifier, not
something a public clone can recompute.

`Adj-inv` marks a feature that is unchanged when the whole price history is rescaled by a constant, which is what a dividend revision does. `Lag` is any publication delay beyond the session close, in sessions. Coverage is the share of sessions with a value once the warm-up window has passed.

---

## Lagged returns

*Short-horizon index returns partially reverse. If the effect exists at all it should be strongest at the one- to three-session horizon and decay beyond it.*

5 features.

| Feature | Formula | Adj-inv | Lag | Coverage | Rationale |
|---|---|:--:|:--:|--:|---|
| `log_ret` | `log(Close_t / Close_{t-1})` | yes | 0 | 100.0% | Yesterday's move. The base term for short-horizon reversal. |
| `ret_lag_2` | `log(Close_t / Close_{t-2})` | yes | 0 | 100.0% | Cumulative 2-session move; separates reversal from momentum by horizon. |
| `ret_lag_3` | `log(Close_t / Close_{t-3})` | yes | 0 | 100.0% | Cumulative 3-session move; separates reversal from momentum by horizon. |
| `ret_lag_5` | `log(Close_t / Close_{t-5})` | yes | 0 | 100.0% | Cumulative 5-session move; separates reversal from momentum by horizon. |
| `ret_lag_10` | `log(Close_t / Close_{t-10})` | yes | 0 | 100.0% | Cumulative 10-session move; separates reversal from momentum by horizon. |

## Trend

*Price stretched far from its own moving average is more likely to snap back. Expressed as a ratio so the reading means the same thing at any price level.*

4 features.

| Feature | Formula | Adj-inv | Lag | Coverage | Rationale |
|---|---|:--:|:--:|--:|---|
| `SMA_gap_5` | `(Close_t - SMA5_t) / SMA5_t` | yes | 0 | 100.0% | Stretch above or below the 5-session average. Expressed as a ratio so it is comparable across price levels. |
| `SMA_gap_10` | `(Close_t - SMA10_t) / SMA10_t` | yes | 0 | 100.0% | Stretch above or below the 10-session average. Expressed as a ratio so it is comparable across price levels. |
| `SMA_gap_20` | `(Close_t - SMA20_t) / SMA20_t` | yes | 0 | 100.0% | Stretch above or below the 20-session average. Expressed as a ratio so it is comparable across price levels. |
| `SMA_gap_50` | `(Close_t - SMA50_t) / SMA50_t` | yes | 0 | 100.0% | Stretch above or below the 50-session average. Expressed as a ratio so it is comparable across price levels. |

## Momentum

*Bounded oscillators identify stretched conditions without needing a volatility estimate, and give a different view of the same reversal idea.*

2 features.

| Feature | Formula | Adj-inv | Lag | Coverage | Rationale |
|---|---|:--:|:--:|--:|---|
| `RSI_14` | `100 - 100/(1 + EWM(gain,14)/EWM(loss,14))` | yes | 0 | 100.0% | Bounded overbought/oversold gauge. Extreme readings are the classic short-horizon reversal signal. Wilder smoothing via EWM with adjust=False, which is causal. |
| `MACD_hist` | `(EMA12 - EMA26) - EMA9(EMA12 - EMA26)` | **no** | 0 | 100.0% | Acceleration of trend. Sign changes mark momentum turning points. A difference of price levels, not a ratio, so it scales with the adjustment factor. Sign and relative magnitude survive; the level does not. |

## Realised volatility

*Reversal is conditional on the volatility state, and the label itself is scaled by realised volatility, so these terms enter twice.*

4 features.

| Feature | Formula | Adj-inv | Lag | Coverage | Rationale |
|---|---|:--:|:--:|--:|---|
| `Volatility_5` | `std(log return, 5 sessions)` | yes | 0 | 100.0% | Realised volatility over 5 sessions. Conditions the strength of any reversal effect and scales the label. |
| `Volatility_10` | `std(log return, 10 sessions)` | yes | 0 | 100.0% | Realised volatility over 10 sessions. Conditions the strength of any reversal effect and scales the label. |
| `Volatility_20` | `std(log return, 20 sessions)` | yes | 0 | 100.0% | Realised volatility over 20 sessions. Conditions the strength of any reversal effect and scales the label. |
| `Volatility_60` | `std(log return, 60 sessions)` | yes | 0 | 100.0% | Realised volatility over 60 sessions. Conditions the strength of any reversal effect and scales the label. |

## Bollinger position

*A volatility-normalised statement of where price sits, which is the same hypothesis as the trend group with the scale divided out.*

2 features.

| Feature | Formula | Adj-inv | Lag | Coverage | Rationale |
|---|---|:--:|:--:|--:|---|
| `BB_width` | `(upper - lower) / SMA20,  bands at +/- 2 sd` | yes | 0 | 100.0% | Band width is realised volatility in price-relative form; narrow bands often precede expansion. |
| `BB_percent_b` | `(Close - lower) / (upper - lower)` | yes | 0 | 100.0% | Position within the band. Near 0 or 1 marks a stretched price. |

## Cross-asset changes

*Risk-off moves transmit across assets within a session. A jump in implied volatility, the dollar, yields or oil should carry information about the next session that the index price alone does not.*

25 features.

| Feature | Formula | Adj-inv | Lag | Coverage | Rationale |
|---|---|:--:|:--:|--:|---|
| `VIX` | `VIX close` | yes | 0 | 100.0% | Level of implied volatility. The primary risk-appetite state variable. |
| `VIX_ret_1` | `log(VIX_t / VIX_{t-1})` | yes | 0 | 100.0% | 1-session move in implied volatility; cross-asset risk-off transmission. |
| `VIX_ret_2` | `log(VIX_t / VIX_{t-2})` | yes | 0 | 100.0% | 2-session move in implied volatility; cross-asset risk-off transmission. |
| `VIX_ret_3` | `log(VIX_t / VIX_{t-3})` | yes | 0 | 100.0% | 3-session move in implied volatility; cross-asset risk-off transmission. |
| `VIX_ret_5` | `log(VIX_t / VIX_{t-5})` | yes | 0 | 100.0% | 5-session move in implied volatility; cross-asset risk-off transmission. |
| `VIX_ret_10` | `log(VIX_t / VIX_{t-10})` | yes | 0 | 100.0% | 10-session move in implied volatility; cross-asset risk-off transmission. |
| `VIX_ret_20` | `log(VIX_t / VIX_{t-20})` | yes | 0 | 100.0% | 20-session move in implied volatility; cross-asset risk-off transmission. |
| `DXY_ret_1` | `log(DXY_t / DXY_{t-1})` | yes | 0 | 100.0% | 1-session move in the dollar; cross-asset risk-off transmission. |
| `DXY_ret_2` | `log(DXY_t / DXY_{t-2})` | yes | 0 | 100.0% | 2-session move in the dollar; cross-asset risk-off transmission. |
| `DXY_ret_3` | `log(DXY_t / DXY_{t-3})` | yes | 0 | 100.0% | 3-session move in the dollar; cross-asset risk-off transmission. |
| `DXY_ret_5` | `log(DXY_t / DXY_{t-5})` | yes | 0 | 100.0% | 5-session move in the dollar; cross-asset risk-off transmission. |
| `DXY_ret_10` | `log(DXY_t / DXY_{t-10})` | yes | 0 | 100.0% | 10-session move in the dollar; cross-asset risk-off transmission. |
| `DXY_ret_20` | `log(DXY_t / DXY_{t-20})` | yes | 0 | 100.0% | 20-session move in the dollar; cross-asset risk-off transmission. |
| `TNX_change_1` | `TNX_t - TNX_{t-1}` | yes | 0 | 100.0% | 1-session move in the 10-year yield; cross-asset risk-off transmission. Differences, not ratios: TNX is already a yield level. |
| `TNX_change_2` | `TNX_t - TNX_{t-2}` | yes | 0 | 100.0% | 2-session move in the 10-year yield; cross-asset risk-off transmission. Differences, not ratios: TNX is already a yield level. |
| `TNX_change_3` | `TNX_t - TNX_{t-3}` | yes | 0 | 100.0% | 3-session move in the 10-year yield; cross-asset risk-off transmission. Differences, not ratios: TNX is already a yield level. |
| `TNX_change_5` | `TNX_t - TNX_{t-5}` | yes | 0 | 100.0% | 5-session move in the 10-year yield; cross-asset risk-off transmission. Differences, not ratios: TNX is already a yield level. |
| `TNX_change_10` | `TNX_t - TNX_{t-10}` | yes | 0 | 100.0% | 10-session move in the 10-year yield; cross-asset risk-off transmission. Differences, not ratios: TNX is already a yield level. |
| `TNX_change_20` | `TNX_t - TNX_{t-20}` | yes | 0 | 100.0% | 20-session move in the 10-year yield; cross-asset risk-off transmission. Differences, not ratios: TNX is already a yield level. |
| `OIL_ret_1` | `log(OIL_t / OIL_{t-1})` | yes | 0 | 100.0% | 1-session move in Brent crude; cross-asset risk-off transmission. |
| `OIL_ret_2` | `log(OIL_t / OIL_{t-2})` | yes | 0 | 100.0% | 2-session move in Brent crude; cross-asset risk-off transmission. |
| `OIL_ret_3` | `log(OIL_t / OIL_{t-3})` | yes | 0 | 100.0% | 3-session move in Brent crude; cross-asset risk-off transmission. |
| `OIL_ret_5` | `log(OIL_t / OIL_{t-5})` | yes | 0 | 100.0% | 5-session move in Brent crude; cross-asset risk-off transmission. |
| `OIL_ret_10` | `log(OIL_t / OIL_{t-10})` | yes | 0 | 100.0% | 10-session move in Brent crude; cross-asset risk-off transmission. |
| `OIL_ret_20` | `log(OIL_t / OIL_{t-20})` | yes | 0 | 100.0% | 20-session move in Brent crude; cross-asset risk-off transmission. |

## Cross-asset standardisation

*Levels matter less than position within the recent range; the same VIX reading means something different after a calm month than after a turbulent one.*

8 features.

| Feature | Formula | Adj-inv | Lag | Coverage | Rationale |
|---|---|:--:|:--:|--:|---|
| `VIX_z_20` | `(VIX_t - mean_20) / sd_20,  trailing window` | yes | 0 | 100.0% | Where VIX sits relative to its own recent range, which matters more than its absolute level. |
| `VIX_z_60` | `(VIX_t - mean_60) / sd_60,  trailing window` | yes | 0 | 100.0% | Where VIX sits relative to its own recent range, which matters more than its absolute level. |
| `DXY_z_20` | `(DXY_t - mean_20) / sd_20,  trailing window` | yes | 0 | 100.0% | Where DXY sits relative to its own recent range, which matters more than its absolute level. |
| `DXY_z_60` | `(DXY_t - mean_60) / sd_60,  trailing window` | yes | 0 | 100.0% | Where DXY sits relative to its own recent range, which matters more than its absolute level. |
| `TNX_z_20` | `(TNX_t - mean_20) / sd_20,  trailing window` | yes | 0 | 100.0% | Where TNX sits relative to its own recent range, which matters more than its absolute level. |
| `TNX_z_60` | `(TNX_t - mean_60) / sd_60,  trailing window` | yes | 0 | 100.0% | Where TNX sits relative to its own recent range, which matters more than its absolute level. |
| `OIL_z_20` | `(OIL_t - mean_20) / sd_20,  trailing window` | yes | 0 | 100.0% | Where OIL sits relative to its own recent range, which matters more than its absolute level. |
| `OIL_z_60` | `(OIL_t - mean_60) / sd_60,  trailing window` | yes | 0 | 100.0% | Where OIL sits relative to its own recent range, which matters more than its absolute level. |

## Term structure

*The term spread is the market's fastest read on growth and policy. Its publication lag makes it the one group that cannot use same-day data.*

3 features.

| Feature | Formula | Adj-inv | Lag | Coverage | Rationale |
|---|---|:--:|:--:|--:|---|
| `YC_2Y10Y_change_1` | `(DGS10 - DGS2)_{t-1} - (DGS10 - DGS2)_{t-2}` | yes | 1 | 100.0% | Daily change in the term spread; a fast read on growth and policy expectations. H.15 publishes the value dated t on the next business day. |
| `YC_2Y10Y_z_20` | `z-score of the lagged term spread over 20 sessions` | yes | 1 | 100.0% | Term-spread position relative to its recent range. |
| `YC_2Y10Y_z_60` | `z-score of the lagged term spread over 60 sessions` | yes | 1 | 100.0% | Term-spread position relative to its recent range. |

## Intraday structure

*The primary target is an intraday return, so the intraday structure of the preceding session is the most directly relevant information there is — in particular whether overnight gaps are faded or extended.*

4 features.

| Feature | Formula | Adj-inv | Lag | Coverage | Rationale |
|---|---|:--:|:--:|--:|---|
| `intraday_ret` | `log(Close_t / Open_t)` | yes | 0 | 100.0% | The previous session's open-to-close return, which is the lag-1 of the prediction target itself. Any autocorrelation in intraday returns shows up here first. Same-session ratio, so the adjustment factor cancels exactly. |
| `overnight_gap` | `log(Open_t / Close_{t-1})` | yes | 0 | 100.0% | The overnight move, which the target deliberately excludes. Whether a gap is faded or extended during the session is the central question this specification can answer. |
| `high_low_range` | `(High_t - Low_t) / Close_t` | yes | 0 | 100.0% | Realised intraday range; a volatility measure that does not need a rolling window. Mechanically compressed on early-close sessions. |
| `close_location_value` | `(Close - Low) / (High - Low),  undefined when High == Low` | yes | 0 | 100.0% | Where the session closed inside its range. Near 1 is a strong close, near 0 a weak one. |

## Volume

*Conviction. The same price move on heavy participation is treated as more informative than on light participation.*

3 features.

| Feature | Formula | Adj-inv | Lag | Coverage | Rationale |
|---|---|:--:|:--:|--:|---|
| `relative_volume_20` | `Volume_t / mean(Volume, 20)` | yes | 0 | 100.0% | Participation relative to the recent norm. Moves on heavy volume are held to persist more often than moves on light volume. A ratio of raw volumes, so the missing volume adjustment cancels. |
| `volume_z_20` | `(Volume_t - mean_20) / sd_20` | yes | 0 | 100.0% | Standardised abnormal volume. |
| `volume_ret_interaction` | `volume_z_20 * log(Close_t / Close_{t-1})` | yes | 0 | 100.0% | A large move on abnormal volume is treated differently from the same move on quiet volume. Invariant to dividend adjustment, which rescales the whole price history by one factor that cancels inside the log ratio. It is the only feature exposed to a *split*, which changes Volume without changing the adjusted price and so distorts the 20-session volume window around the split date. Verified: SPY, QQQ, IWM and DIA have no split in this sample, the most recent being IWM in June 2005. |

## Calendar

*Controls, not hypotheses. Included so that any calendar regularity is absorbed rather than attributed to a market feature.*

4 features.

| Feature | Formula | Adj-inv | Lag | Coverage | Rationale |
|---|---|:--:|:--:|--:|---|
| `is_monday` | `1 if the session is a Monday` | yes | 0 | 100.0% | Day-of-week effects are weak and mostly historical; carried as a control. |
| `is_friday` | `1 if the session is a Friday` | yes | 0 | 100.0% | Pre-weekend positioning; carried as a control. |
| `is_month_start` | `1 on the first NYSE session of the month` | yes | 0 | 100.0% | Month-turn flows from index rebalancing and retirement contributions. |
| `is_month_end` | `1 on the last NYSE session of the month` | yes | 0 | 100.0% | Month-end rebalancing flows. |

## Volatility regime

*An explicit switch letting a model apply a different rule in calm and turbulent conditions instead of averaging across both.*

2 features.

| Feature | Formula | Adj-inv | Lag | Coverage | Rationale |
|---|---|:--:|:--:|--:|---|
| `vix_regime_high` | `1 if VIX_t is above its trailing 252-session 75th percentile` | yes | 0 | 100.0% | Reversal strength is widely held to depend on the volatility state. These flags let a model condition on it. Trailing quantiles only; min_periods=60 keeps the early sample honest. |
| `vix_regime_low` | `1 if VIX_t is below its trailing 252-session 25th percentile` | yes | 0 | 100.0% | Reversal strength is widely held to depend on the volatility state. These flags let a model condition on it. Trailing quantiles only; min_periods=60 keeps the early sample honest. |

## Cross-market style

*Rotation between growth, small caps and blue chips reveals risk appetite that the headline index masks.*

15 features.

| Feature | Formula | Adj-inv | Lag | Coverage | Rationale |
|---|---|:--:|:--:|--:|---|
| `QQQ_ret_1` | `log(QQQ_t / QQQ_{t-1})` | yes | 0 | 100.0% | 1-session return of Nasdaq growth. Its spread against SPY carries the risk-appetite rotation the index alone hides. |
| `QQQ_ret_2` | `log(QQQ_t / QQQ_{t-2})` | yes | 0 | 100.0% | 2-session return of Nasdaq growth. Its spread against SPY carries the risk-appetite rotation the index alone hides. |
| `QQQ_ret_3` | `log(QQQ_t / QQQ_{t-3})` | yes | 0 | 100.0% | 3-session return of Nasdaq growth. Its spread against SPY carries the risk-appetite rotation the index alone hides. |
| `QQQ_ret_5` | `log(QQQ_t / QQQ_{t-5})` | yes | 0 | 100.0% | 5-session return of Nasdaq growth. Its spread against SPY carries the risk-appetite rotation the index alone hides. |
| `QQQ_ret_10` | `log(QQQ_t / QQQ_{t-10})` | yes | 0 | 100.0% | 10-session return of Nasdaq growth. Its spread against SPY carries the risk-appetite rotation the index alone hides. |
| `IWM_ret_1` | `log(IWM_t / IWM_{t-1})` | yes | 0 | 100.0% | 1-session return of small caps. Its spread against SPY carries the risk-appetite rotation the index alone hides. |
| `IWM_ret_2` | `log(IWM_t / IWM_{t-2})` | yes | 0 | 100.0% | 2-session return of small caps. Its spread against SPY carries the risk-appetite rotation the index alone hides. |
| `IWM_ret_3` | `log(IWM_t / IWM_{t-3})` | yes | 0 | 100.0% | 3-session return of small caps. Its spread against SPY carries the risk-appetite rotation the index alone hides. |
| `IWM_ret_5` | `log(IWM_t / IWM_{t-5})` | yes | 0 | 100.0% | 5-session return of small caps. Its spread against SPY carries the risk-appetite rotation the index alone hides. |
| `IWM_ret_10` | `log(IWM_t / IWM_{t-10})` | yes | 0 | 100.0% | 10-session return of small caps. Its spread against SPY carries the risk-appetite rotation the index alone hides. |
| `DIA_ret_1` | `log(DIA_t / DIA_{t-1})` | yes | 0 | 100.0% | 1-session return of blue chips. Its spread against SPY carries the risk-appetite rotation the index alone hides. |
| `DIA_ret_2` | `log(DIA_t / DIA_{t-2})` | yes | 0 | 100.0% | 2-session return of blue chips. Its spread against SPY carries the risk-appetite rotation the index alone hides. |
| `DIA_ret_3` | `log(DIA_t / DIA_{t-3})` | yes | 0 | 100.0% | 3-session return of blue chips. Its spread against SPY carries the risk-appetite rotation the index alone hides. |
| `DIA_ret_5` | `log(DIA_t / DIA_{t-5})` | yes | 0 | 100.0% | 5-session return of blue chips. Its spread against SPY carries the risk-appetite rotation the index alone hides. |
| `DIA_ret_10` | `log(DIA_t / DIA_{t-10})` | yes | 0 | 100.0% | 10-session return of blue chips. Its spread against SPY carries the risk-appetite rotation the index alone hides. |

---

## Verification

`tests/test_features.py` asserts, on the frozen snapshot:

- **No look-ahead.** The whole frame is rebuilt on truncated history at three cut points and every overlapping value must be bit-identical. A transform that reads forward cannot survive this.
- **Target alignment.** Row *t* holds `Close_{t+1} / Open_{t+1} - 1`, and the target is absent from the feature frame.
- **No proxy for the target.** No feature correlates above 0.5 with the value it is meant to predict.
- **Publication lag.** A synthetic jump in the term spread dated *t* moves the feature dated *t+1* and leaves the feature dated *t* untouched.
- **Adjustment invariance.** Every price series is rescaled by a constant; each feature must move or not move exactly as its flag claims.
- **No infinities, bounded warm-up, binary flags binary.**

Features not invariant to a price rescaling: `MACD_hist`.

Features carrying an extra publication lag: `YC_2Y10Y_change_1`, `YC_2Y10Y_z_20`, `YC_2Y10Y_z_60`.

## Known distortions

- **Early closes.** 23 sessions close at 13:00 ET. `high_low_range`, `close_location_value`, `intraday_ret` and every volume feature are mechanically compressed on those days. They are flagged in the snapshot rather than dropped.
- **Splits.** Volume is not split-adjusted while price is, so a trailing volume window spanning a split is distorted. Verified: no split occurs in this sample for SPY, QQQ, IWM or DIA.
- **Non-synchronous closes.** Brent and the dollar index close at different instants from the 16:00 ET equity close. Under the primary specification the whole information set is used only after that close and traded at the next open, which leaves ample slack.
