"""Exploratory specifications that reuse P1's frozen predictions.

E9 through E12b change the trading rule, not the model. They read `mu_hat` and the
calibrated probabilities exactly as P1 produced them and apply a different mapping
from prediction to position, so they need no refit and introduce no new model
search. They are still registered as trials, because §7.2 counts anything that
produces new positions.

Every one of them is reported. None of them can change the headline, and the
best of them is not promoted: the point of showing all of them is to establish
that the P1 result is not an artefact of one particular trading rule.
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from build_benchmarks import cash_return, intraday_financing, load_snapshot  # noqa: E402
from src.stats import TRADING_DAYS, ann_mean, bootstrap_difference, sharpe  # noqa: E402
from src.strategy import no_trade_band  # noqa: E402

BASE_COST = 2.0
BLOCK, REPS = 20, 10_000


def net_of(w: pd.Series, r: pd.Series, fin: pd.Series, cost_bps: float) -> pd.Series:
    """The same P&L identity P1 uses, with |w| allowed to be fractional."""
    c = cost_bps / 1e4
    return w * r - 2 * c * w.abs() - fin * w.abs()


# --------------------------------------------------------------- position rules

def rule_p1(mu, fin, delta=0.0):
    band = no_trade_band(BASE_COST, fin, delta)
    return np.sign(mu).where(mu.abs() > band, 0.0)


def rule_argmax(proba):
    """E9. The control: act on the most likely class, whatever it costs.

    Note what this does and does not isolate. The labels are the 25/75 quantiles
    of the volatility-adjusted target, so the flat class carries roughly half the
    training mass and is the arg-max on most sessions. This rule therefore trades
    *less* than P1, not more: it removes the cost-aware threshold but not the label
    scheme's own reticence, and the two are easily confused.
    """
    return proba.idxmax(axis=1).astype(float)


def rule_fixed_quantile(mu, q=0.5):
    """E10. Trade when the prediction is unusual by its own history, not when it
    covers cost.

    The threshold is the `q` quantile of prior |mu_hat| only — expanding, strictly
    backward-looking, and undefined until 60 predictions exist. Using a full-sample
    quantile here would be exactly the look-ahead the rest of the protocol exists
    to prevent, and would make this variant incomparable to the others.
    """
    thresh = mu.abs().shift(1).expanding(min_periods=60).quantile(q)
    w = np.sign(mu).where(mu.abs() > thresh, 0.0)
    return w.fillna(0.0)


def rule_vol_target(mu, fin, realised, target_ann=0.10, cap=1.0):
    """E11. P1's direction, sized to a constant volatility target rather than +/-1.

    Trailing 20-session realised volatility of the O2C return, lagged one session
    so the scale for day t uses only returns through t-1.
    """
    w = rule_p1(mu, fin)
    vol = realised.rolling(20).std().shift(1) * np.sqrt(TRADING_DAYS)
    scale = (target_ann / vol).clip(upper=cap)
    return (w * scale).fillna(0.0)


# --------------------------------------------------------------------- reporting

def summarise(name, kind, w, r, fin, cash, cost_bps, base_net):
    net = net_of(w, r, fin, cost_bps)
    active = w != 0
    row = {
        "id": name, "kind": kind, "cost_bps_per_side": cost_bps,
        "ann_mean_excess": ann_mean(net.to_numpy()),
        "sharpe": sharpe(net.to_numpy()),
        "n_active": int(active.sum()),
        "participation": float(active.mean()),
        "mean_abs_position": float(w.abs().mean()),
        "terminal_wealth": float((1.0 + net + cash).prod()),
    }
    if base_net is not None:
        d = bootstrap_difference(net, base_net, sharpe, BLOCK, REPS)
        row["sharpe_minus_p1"] = row["sharpe"] - sharpe(base_net.to_numpy())
        row["sharpe_diff_lo"], row["sharpe_diff_hi"] = d["ci_low"], d["ci_high"]
    return row


def main() -> int:
    oos = pd.read_csv(ROOT / "results" / "oos_predictions.csv",
                      index_col="date", parse_dates=True)
    snapshot, _ = load_snapshot()
    fin = intraday_financing(snapshot, snapshot.index).shift(-1).reindex(oos.index)
    cash = cash_return(snapshot).reindex(oos.index).fillna(0.0)
    mu, r = oos.mu_hat, oos.realised_o2c
    proba = oos[["p_short", "p_flat", "p_long"]].rename(
        columns={"p_short": -1.0, "p_flat": 0.0, "p_long": 1.0})

    w_p1 = oos.position.astype(float)
    assert (w_p1 - rule_p1(mu, fin)).abs().max() < 1e-12, "cannot reproduce P1's own positions"
    base_net = net_of(w_p1, r, fin, BASE_COST)

    rows = [summarise("P1", "confirmatory", w_p1, r, fin, cash, BASE_COST, None)]

    rows.append(summarise("E9  arg-max, no band", "exploratory",
                          rule_argmax(proba), r, fin, cash, BASE_COST, base_net))
    for q in (0.25, 0.50, 0.75):
        rows.append(summarise(f"E10 fixed quantile {q:.2f}", "exploratory",
                              rule_fixed_quantile(mu, q), r, fin, cash, BASE_COST, base_net))
    for tgt in (0.05, 0.10):
        rows.append(summarise(f"E11 vol target {tgt:.0%}", "exploratory",
                              rule_vol_target(mu, fin, r, tgt), r, fin, cash, BASE_COST, base_net))
    for delta in (0.5, 1.0, 2.0):
        rows.append(summarise(f"E12b delta={delta}", "exploratory",
                              rule_p1(mu, fin, delta), r, fin, cash, BASE_COST, base_net))
    # E12: the band is rebuilt at each cost level, so the rule adapts rather than
    # the frozen positions being re-priced. That is the difference between this and
    # the cost scenarios in the main report, which hold positions fixed.
    for cost in (0.0, 1.0, 2.0, 5.0, 10.0):
        band = no_trade_band(cost, fin, 0.0)
        w = np.sign(mu).where(mu.abs() > band, 0.0)
        rows.append(summarise(f"E12 reoptimised @ {cost:.0f}bp", "exploratory",
                              w, r, fin, cash, cost, base_net))

    out = pd.DataFrame(rows)
    dest = ROOT / "results" / "exploratory_position_rules.csv"
    out.to_csv(dest, index=False, float_format="%.6g")

    pd.set_option("display.width", 200, "display.max_columns", 20)
    show = out.copy()
    for col in ("ann_mean_excess", "participation", "mean_abs_position"):
        show[col] = (show[col] * 100).round(2)
    print(show.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    print(f"\nwritten to {dest.relative_to(ROOT)}")
    print("")
    print("Every row above is reported and none of them replaces P1. Read n_active")
    print("before reading sharpe: the highest ratio in this table rests on a few dozen")
    print("non-zero sessions, which is precisely the configuration the confirmatory")
    print("procedure was changed in v6 to stop selecting.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
