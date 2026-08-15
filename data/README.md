# Frozen research inputs

`market_inputs_2026-05-05.csv` is the canonical pre-feature-engineering snapshot for the published run. It contains 1,088 observations from January 3, 2022 through May 5, 2026.

Sources:

- Yahoo Finance: SPY, VIX, DXY, 10-year Treasury yield, crude oil, QQQ, IWM, and DIA
- Federal Reserve Economic Data (FRED): DGS2 and DGS10

The adjacent manifest records the source window, columns, package versions, and SHA-256 checksum. The snapshot is included solely to make the educational research pipeline reproducible; upstream provider terms and attributions continue to apply.

To refresh the inputs intentionally:

```bash
python scripts/freeze_market_data.py
```

A refresh can change historical adjusted prices and must be treated as a new research run. Regenerate every result and update the manifest, result files, and README together.
