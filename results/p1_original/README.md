# Primary P1 execution

This directory preserves the artefacts of the first P1 execution, which remains the
primary confirmatory result. Its identity is established by the frozen configuration
digest, input digest, run identifier, package versions and file-level SHA-256
manifest.

The deterministic procedure was later re-executed solely to persist omitted
diagnostics. `scripts/verify_reproduction.py` compares every shared field, including
model selection, probabilities, positions and return components. Neither execution
was chosen on the basis of its result.

## What that means precisely

Only one confirmatory decision path was evaluated. `config/p1.yaml` promised
`calibration_diagnostics.csv` in its `outputs` list and the first execution did not
write it, so the procedure was run again to emit it. Model choices, predictions,
positions and reported returns were bit-identical. The re-execution is registered as
`run_type=reproduction_output_regeneration` with `counts_toward_trial_budget=false`,
and no result was used to select a replacement procedure.

## Files

| File | Contents |
|---|---|
| `oos_predictions.csv` | per-session model, class probabilities, `mu_hat`, position, financing |
| `selection_log.csv` | which candidate won each outer step, and why |
| `candidate_diagnostics.csv` | every candidate's score at every step |
| `feature_stability.csv` | how often each feature was selected |
| `run_manifest.json` | configuration digest, input digest, code commit, package versions |
| `manifest.sha256.json` | SHA-256 of each file above |

## Verifying it

```bash
python scripts/verify_reproduction.py
```

It reads this directory and `results/` directly and compares them field by field. No
repository history needs to be checked out, and nothing outside the published files is
required.

`gross` and `net` are not compared, because reconstructing the realised session return
needs the licensed market snapshot this repository does not distribute. Every field
either execution actually publishes **is** compared, and the omission is recorded in
`results/reproduction_equivalence.json` rather than passed over.

`120f3e9` is the historical commit identifier under which these artefacts were first
recorded. It is a label, not a verification dependency: it is not fetchable from the
published repository, and nothing here requires it.
