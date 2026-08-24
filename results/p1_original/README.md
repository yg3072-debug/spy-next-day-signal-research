# First execution of P1

Recovered from commit `120f3e9`. This is the **primary** result.

P1 was executed a second time to emit `calibration_diagnostics.csv`, which the
configuration promised and the first execution did not write. That second
execution changed no data, no rule, no model selection and no reported figure,
and is registered as `run_type=reproduction_output_regeneration` with
`counts_toward_trial_budget=false`.

`scripts/verify_reproduction.py` compares the two field by field and writes
`results/reproduction_equivalence.json`. Neither run was chosen over the other
on the basis of what it produced.
