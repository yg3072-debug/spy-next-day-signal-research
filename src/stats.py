"""Bootstrap inference for dependent return series.

Daily returns are autocorrelated and heavy-tailed, so an IID bootstrap understates
standard errors and a normal-theory test misstates them in both directions. Every
interval here comes from a stationary bootstrap, which resamples geometrically
distributed blocks and so preserves short-range dependence while remaining
stationary under resampling.

Comparisons between a strategy and a benchmark use *paired* resampling: both
series are drawn with the same block indices, so the correlation between them is
preserved. Resampling them independently would inflate the standard error of the
difference to the point where nothing is ever significant, since a strategy is
typically a timed version of its own benchmark.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from arch.bootstrap import StationaryBootstrap, optimal_block_length

TRADING_DAYS = 252
# Main block length, fixed before P1 runs. Politis-White on the pre-computed
# always-long O2C benchmark suggests 17.0; 20 is that rounded up. Sensitivity
# runs use 10, with 5 as a short-block stress test.
DEFAULT_BLOCK = 20
DEFAULT_REPS = 10_000
DEFAULT_SEED = 20260823


def sharpe(excess: np.ndarray) -> float:
    """Annualised Sharpe ratio of an excess-return series."""
    sd = excess.std(ddof=1)
    return np.nan if sd == 0 else excess.mean() / sd * np.sqrt(TRADING_DAYS)


def ann_mean(excess: np.ndarray) -> float:
    """Annualised arithmetic mean of an excess-return series."""
    return excess.mean() * TRADING_DAYS


def politis_white_block(series: pd.Series) -> float:
    """Data-driven mean block length (Politis and White, 2004).

    Reported alongside the fixed block length so the choice is visible rather
    than assumed. The protocol fixes the headline block length in advance; this
    is a diagnostic, not a selection rule.
    """
    return float(optimal_block_length(pd.DataFrame({"x": series.to_numpy()}))["stationary"].iloc[0])


def _ci(draws: np.ndarray, alpha: float) -> tuple[float, float]:
    lo, hi = np.nanpercentile(draws, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return float(lo), float(hi)


def bootstrap_statistic(
    series: pd.Series,
    statistic=sharpe,
    block: float = DEFAULT_BLOCK,
    reps: int = DEFAULT_REPS,
    alpha: float = 0.05,
    seed: int = DEFAULT_SEED,
) -> dict:
    """Percentile interval for a statistic of one return series."""
    x = series.to_numpy(dtype=float)
    point = statistic(x)
    bs = StationaryBootstrap(block, x, seed=seed)
    draws = np.array([statistic(d[0]) for d, _ in bs.bootstrap(reps)])
    lo, hi = _ci(draws, alpha)
    return {
        "point": float(point),
        "ci_low": lo,
        "ci_high": hi,
        "se": float(np.nanstd(draws, ddof=1)),
        "block": float(block),
        "reps": int(reps),
    }


def bootstrap_difference(
    strategy: pd.Series,
    benchmark: pd.Series,
    statistic=sharpe,
    block: float = DEFAULT_BLOCK,
    reps: int = DEFAULT_REPS,
    alpha: float = 0.05,
    seed: int = DEFAULT_SEED,
) -> dict:
    """Percentile interval for statistic(strategy) - statistic(benchmark).

    Both series are resampled with the same block indices. `p_le_zero` is the
    share of resamples in which the difference is not positive, which is the
    quantity the stopping rule reads.
    """
    if not strategy.index.equals(benchmark.index):
        raise ValueError("strategy and benchmark must share an index for paired resampling")
    a = strategy.to_numpy(dtype=float)
    b = benchmark.to_numpy(dtype=float)
    point = statistic(a) - statistic(b)
    bs = StationaryBootstrap(block, a, b, seed=seed)
    draws = np.array([statistic(d[0]) - statistic(d[1]) for d, _ in bs.bootstrap(reps)])
    lo, hi = _ci(draws, alpha)
    return {
        "point": float(point),
        "ci_low": lo,
        "ci_high": hi,
        "se": float(np.nanstd(draws, ddof=1)),
        "fraction_le_zero": float(np.mean(draws <= 0)),
        "block": float(block),
        "reps": int(reps),
    }


def jobson_korkie_memmel(strategy: pd.Series, benchmark: pd.Series) -> dict:
    """Parametric test for a difference in Sharpe ratios, as a cross-check.

    Jobson and Korkie (1981) with Memmel's (2003) correction. Assumes IID normal
    returns, which daily equity returns are not, so this is reported only to sit
    beside the bootstrap interval, never in place of it.
    """
    a = strategy.to_numpy(dtype=float)
    b = benchmark.to_numpy(dtype=float)
    n = len(a)
    mu_a, mu_b = a.mean(), b.mean()
    sd_a, sd_b = a.std(ddof=1), b.std(ddof=1)
    rho = np.corrcoef(a, b)[0, 1]
    sr_a, sr_b = mu_a / sd_a, mu_b / sd_b
    theta = (
        2 - 2 * rho
        + 0.5 * (sr_a**2 + sr_b**2 - 2 * sr_a * sr_b * rho**2)
    ) / n
    diff_daily = sr_a - sr_b
    z = diff_daily / np.sqrt(theta) if theta > 0 else np.nan
    from scipy.stats import norm

    return {
        "sharpe_diff_annualised": float(diff_daily * np.sqrt(TRADING_DAYS)),
        "z": float(z),
        "p_two_sided": float(2 * (1 - norm.cdf(abs(z)))) if np.isfinite(z) else np.nan,
        "correlation": float(rho),
    }


def expected_max_sharpe(sharpes: np.ndarray) -> float:
    """Expected best Sharpe from N independent draws of pure noise.

    Bailey and Lopez de Prado's expression for the expected maximum of N draws.
    Descriptive only: it is a multiple-testing reference point, not a p-value and
    not a substitute for a deflated Sharpe ratio or a reality check.
    """
    from scipy.stats import norm

    n = len(sharpes)
    if n < 2:
        return np.nan
    sd = np.nanstd(sharpes, ddof=1)
    gamma = 0.5772156649015329
    return float(
        sd * ((1 - gamma) * norm.ppf(1 - 1 / n) + gamma * norm.ppf(1 - 1 / (n * np.e)))
    )
