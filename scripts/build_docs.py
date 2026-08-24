"""Generate documentation that must not drift from the code.

The feature dictionary is written from the metadata registry in `src/features.py`,
and the snapshot identifiers in the availability note are refreshed from the live
manifest. Anything hand-maintained in two places eventually disagrees in two places.
"""

from __future__ import annotations

import glob
import json
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.features import build_features, build_target  # noqa: E402

GROUP_TITLES = {
    "lagged_return": "Lagged returns",
    "trend": "Trend",
    "momentum": "Momentum",
    "volatility": "Realised volatility",
    "bollinger": "Bollinger position",
    "macro_change": "Cross-asset changes",
    "macro_zscore": "Cross-asset standardisation",
    "yield_curve": "Term structure",
    "intraday": "Intraday structure",
    "volume": "Volume",
    "calendar": "Calendar",
    "regime": "Volatility regime",
    "cross_market": "Cross-market style",
}

GROUP_HYPOTHESES = {
    "lagged_return": "Short-horizon index returns partially reverse. If the effect exists at "
                     "all it should be strongest at the one- to three-session horizon and "
                     "decay beyond it.",
    "trend": "Price stretched far from its own moving average is more likely to snap back. "
             "Expressed as a ratio so the reading means the same thing at any price level.",
    "momentum": "Bounded oscillators identify stretched conditions without needing a "
                "volatility estimate, and give a different view of the same reversal idea.",
    "volatility": "Reversal is conditional on the volatility state, and the label itself is "
                  "scaled by realised volatility, so these terms enter twice.",
    "bollinger": "A volatility-normalised statement of where price sits, which is the same "
                 "hypothesis as the trend group with the scale divided out.",
    "macro_change": "Risk-off moves transmit across assets within a session. A jump in "
                    "implied volatility, the dollar, yields or oil should carry information "
                    "about the next session that the index price alone does not.",
    "macro_zscore": "Levels matter less than position within the recent range; the same "
                    "VIX reading means something different after a calm month than after a "
                    "turbulent one.",
    "yield_curve": "The term spread is the market's fastest read on growth and policy. Its "
                   "publication lag makes it the one group that cannot use same-day data.",
    "intraday": "The primary target is an intraday return, so the intraday structure of the "
                "preceding session is the most directly relevant information there is — in "
                "particular whether overnight gaps are faded or extended.",
    "volume": "Conviction. The same price move on heavy participation is treated as more "
              "informative than on light participation.",
    "calendar": "Controls, not hypotheses. Included so that any calendar regularity is "
                "absorbed rather than attributed to a market feature.",
    "regime": "An explicit switch letting a model apply a different rule in calm and "
              "turbulent conditions instead of averaging across both.",
    "cross_market": "Rotation between growth, small caps and blue chips reveals risk "
                    "appetite that the headline index masks.",
}


def load_snapshot():
    csv = sorted(glob.glob(str(ROOT / "data" / "market_inputs_*.csv")))[-1]
    manifest = json.loads(Path(csv.replace(".csv", ".manifest.json")).read_text("utf-8"))
    return pd.read_csv(csv, index_col="Date", parse_dates=True), manifest


def write_feature_dictionary(features: pd.DataFrame, registry, manifest) -> Path:
    target_note = (
        "Every feature is a function of information available at or before the close of "
        "session *t*. The target is the next session's open-to-close simple return, "
        "`Close_{t+1} / Open_{t+1} - 1`."
    )
    lines = [
        "# Feature Dictionary",
        "",
        "Generated from the metadata registry in `src/features.py` by "
        "`python scripts/build_docs.py`. Edit the registry, not this file.",
        "",
        target_note,
        "",
        f"**Snapshot:** `{manifest['snapshot_file']}` · **SHA-256:** `{manifest['sha256']}`",
        f"**Candidates:** {len(registry)} across {len(GROUP_TITLES)} hypothesis groups · "
        f"**Sessions:** {len(features):,}",
        "",
        "`Adj-inv` marks a feature that is unchanged when the whole price history is rescaled "
        "by a constant, which is what a dividend revision does. `Lag` is any publication delay "
        "beyond the session close, in sessions. Coverage is the share of sessions with a value "
        "once the warm-up window has passed.",
        "",
        "---",
        "",
    ]

    warm = features.dropna().index.min()
    post_warm = features.loc[warm:]

    for group, title in GROUP_TITLES.items():
        items = [f for f in registry if f.group == group]
        if not items:
            continue
        lines += [
            f"## {title}",
            "",
            f"*{GROUP_HYPOTHESES[group]}*",
            "",
            f"{len(items)} features.",
            "",
            "| Feature | Formula | Adj-inv | Lag | Coverage | Rationale |",
            "|---|---|:--:|:--:|--:|---|",
        ]
        for f in items:
            cov = post_warm[f.name].notna().mean()
            note = f" {f.notes}" if f.notes else ""
            lines.append(
                f"| `{f.name}` | `{f.formula}` | {'yes' if f.adjustment_invariant else '**no**'} "
                f"| {f.extra_lag_sessions} | {cov:.1%} | {f.rationale}{note} |"
            )
        lines.append("")

    non_inv = [f.name for f in registry if not f.adjustment_invariant]
    lagged = [f.name for f in registry if f.extra_lag_sessions]
    lines += [
        "---",
        "",
        "## Verification",
        "",
        "`tests/test_features.py` asserts, on the frozen snapshot:",
        "",
        "- **No look-ahead.** The whole frame is rebuilt on truncated history at three cut "
        "points and every overlapping value must be bit-identical. A transform that reads "
        "forward cannot survive this.",
        "- **Target alignment.** Row *t* holds `Close_{t+1} / Open_{t+1} - 1`, and the target "
        "is absent from the feature frame.",
        "- **No proxy for the target.** No feature correlates above 0.5 with the value it is "
        "meant to predict.",
        "- **Publication lag.** A synthetic jump in the term spread dated *t* moves the "
        "feature dated *t+1* and leaves the feature dated *t* untouched.",
        "- **Adjustment invariance.** Every price series is rescaled by a constant; each "
        "feature must move or not move exactly as its flag claims.",
        "- **No infinities, bounded warm-up, binary flags binary.**",
        "",
        f"Features not invariant to a price rescaling: "
        + (", ".join(f"`{n}`" for n in non_inv) if non_inv else "none") + ".",
        "",
        f"Features carrying an extra publication lag: "
        + (", ".join(f"`{n}`" for n in lagged) if lagged else "none") + ".",
        "",
        "## Known distortions",
        "",
        "- **Early closes.** 23 sessions close at 13:00 ET. `high_low_range`, "
        "`close_location_value`, `intraday_ret` and every volume feature are mechanically "
        "compressed on those days. They are flagged in the snapshot rather than dropped.",
        "- **Splits.** Volume is not split-adjusted while price is, so a trailing volume "
        "window spanning a split is distorted. Verified: no split occurs in this sample for "
        "SPY, QQQ, IWM or DIA.",
        "- **Non-synchronous closes.** Brent and the dollar index close at different instants "
        "from the 16:00 ET equity close. Under the primary specification the whole information "
        "set is used only after that close and traded at the next open, which leaves ample "
        "slack.",
        "",
    ]

    out = ROOT / "docs" / "feature_dictionary.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def refresh_availability_header(manifest) -> Path:
    """Keep the snapshot identifiers in the availability note current."""
    path = ROOT / "docs" / "data_availability.md"
    text = path.read_text(encoding="utf-8")
    text = re.sub(r"\*\*Snapshot:\*\* `[^`]+`", f"**Snapshot:** `data/{manifest['snapshot_file']}`", text, count=1)
    text = re.sub(r"\*\*SHA-256:\*\* `[0-9a-f]{64}`", f"**SHA-256:** `{manifest['sha256']}`", text, count=1)
    path.write_text(text, encoding="utf-8")
    return path


ALT_GROUP_TITLES = {
    "alt_news": "News headlines — Loughran-McDonald sentiment",
    "alt_news_topic": "News headlines — topic exposure (bespoke word lists)",
    "alt_truth": "Truth Social — Loughran-McDonald sentiment",
    "alt_truth_topic": "Truth Social — topic exposure (bespoke word lists)",
}


def write_alt_feature_dictionary() -> Path:
    """Generated from src/altdata.py's registry, for the same reason as the main one."""
    import json
    from src.altdata import LM_CATEGORIES, REGISTRY, TOPICS, build_news_features
    from src.altdata import build_truth_social_features, load_lexicon

    snapshot, _ = load_snapshot()
    REGISTRY.clear()
    lexicon = load_lexicon()
    build_news_features(snapshot.index, lexicon)
    build_truth_social_features(snapshot.index, lexicon)

    manifest = json.loads((ROOT / "data" / "alt" / "alt_data.manifest.json")
                          .read_text(encoding="utf-8"))
    lines = [
        "# Alternative-Data Feature Dictionary",
        "",
        "Generated by `scripts/build_docs.py` from the registry in `src/altdata.py`.",
        "Do not edit by hand.",
        "",
        "Every feature below is a function of text published at or before the close of",
        "the session it is attached to. The mapping that guarantees this is applied once,",
        "in `scripts/freeze_alt_data.py`, and is checked directly by",
        "`tests/test_altdata.py` rather than inferred from these columns.",
        "",
        "**Two kinds of feature, kept under separate names.** The sentiment features use",
        "the Loughran-McDonald dictionary, which is published, citable and was fixed by",
        "people with no stake in this study. The topic features are keyword counts whose",
        "word lists were written for this project, are visible in `src/altdata.py`, and",
        "carry no such authority. Naming them differently is what keeps the distinction",
        "from quietly disappearing into a single 'NLP features' table.",
        "",
        f"Sessions with no documents carry zero counts and a neutral tone rather than",
        f"being dropped. Truth Social covers 446 modelling sessions, 3 of which received",
        f"no post; news covers 2,247, of which 65 carry no headline.",
        "",
    ]
    for group in ("alt_news", "alt_news_topic", "alt_truth", "alt_truth_topic"):
        members = [f for f in REGISTRY if f.group == group]
        if not members:
            continue
        lines += [f"## {ALT_GROUP_TITLES[group]}", "",
                  "| Feature | Formula | Rationale | Notes |", "|---|---|---|---|"]
        for f in members:
            lines.append(f"| `{f.name}` | {f.formula} | {f.rationale} | {f.notes or ''} |")
        lines.append("")

    lines += [
        "## Zero-variance handling",
        "",
        "A topic column can be identically zero over a training slice — a keyword set",
        "that nobody used that year. `feature_selection.drop_zero_variance` removes those",
        "columns inside each fold's own training slice, so a column that is constant in",
        "one fold and informative in another is dropped only where it is constant. The",
        "drop is per-fold rather than global for the same reason every other estimate",
        "here is: computing it once on the whole sample would use out-of-sample rows to",
        "decide what the model may see.",
        "",
        "## Empty text",
        "",
        f"{manifest['truth_social']['empty_text']:,} Truth Social posts "
        f"({manifest['truth_social']['empty_text_share']:.1%}) carry no text. They are an",
        "image or a repost with no comment, not a scrape failure — a scrape failure",
        "produces no row at all. They are excluded from token and sentiment aggregates",
        "and carried as `truth_empty_post_count`, because posting without text is an act",
        "of posting and scoring an empty string would drag every tone toward zero in",
        "proportion to how many images were posted.",
        "",
    ]
    out = ROOT / "docs" / "alt_feature_dictionary.md"
    out.write_text(chr(10).join(lines), encoding="utf-8")
    return out


def main() -> int:
    snapshot, manifest = load_snapshot()
    features, registry = build_features(snapshot)
    target = build_target(snapshot)

    a = write_feature_dictionary(features, registry, manifest)
    b = refresh_availability_header(manifest)
    c = None
    if (ROOT / "data" / "alt" / "alt_data.manifest.json").exists():
        try:
            c = write_alt_feature_dictionary()
        except FileNotFoundError as exc:
            print(f"alternative-data dictionary skipped: {exc}")

    warm = features.dropna().index.min()
    print(f"Features      {features.shape[1]} candidates over {len(features):,} sessions")
    print(f"Warm-up ends  {warm.date()}  (session {features.index.get_loc(warm)})")
    print(f"Modelling set {features.loc[warm:].shape[0]:,} sessions with a complete feature row")
    print(f"Target        {target.notna().sum():,} sessions with a next-session return")
    print(f"Wrote {a}")
    print(f"Wrote {b}")
    if c:
        print(f"Wrote {c}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
