# Errata and Corrections

Every error found in this study after the confirmatory run, classified by what it
affected. The classification is the point: transparency about mistakes is not a
result, and a list that mixes a wrong percentage in a footnote with a defect that
changed trading output tells a reader nothing.

**No error was found that affected P1's positions or returns.** The only defect
that reached trading output occurred in the exploratory group, in E24, and the
incorrect run is retained and counted rather than deleted.

Each entry states what was wrong and what changed as a result.

---

## A · Reporting and interpretation — no number changed

The figures were correct; what was claimed from them was not.

| # | What was wrong | Correction |
|---|---|---|
| A1 | The +3.11% mean-return excess over always-long was described using Condition A's interval. A tests a **Sharpe** difference; +3.11% is a **mean-return** difference. | Its own paired interval computed: [−4.45%, +10.55%]. The gross positioning term likewise: [−11.51%, +3.58%]. |
| A2 | "Underperformed cash by 12.4 percentage points." | Arithmetic error. Correct: 0.149 per dollar, 14.9 pp cumulative, 12.1% lower terminal wealth. All three stated so the reader knows which is which. |
| A3 | Brier skill of +0.0122 used to support "no skill". | No interval for it was pre-specified, so it cannot carry that conclusion. Now reads as no compelling corroborating evidence. |
| A4 | The one-standard-error rule selecting the baseline described as models being statistically indistinguishable. | It is the selection rule's verdict, not a significance test. Reworded. |
| A5 | Stable feature selection read as evidence the screen works. | A screen that consistently ranks the same uninformative variables highest looks identical from outside. Reworded. |
| A6 | 2020 participation attributed **purely** to the rate environment. | Backwards. A counterfactual holding one input at its 2019 level at a time: actual 59.7% active, 0.0% at 2019's `mu_hat`, 49.8% at 2019's threshold. The drift estimate dominated. |
| A7 | "A real effect of the size these strategies plausibly have would not have been detected." | An effect-size claim with no source. Deleted; replaced with what the sample can and cannot separate. |
| A8 | Negative news shifts called **positive controls**, supporting "adding text degrades the result regardless of what it says". | A positive control injects a variable known by construction to carry the answer. Future headlines are not that. Renamed *future-shift leakage stress tests*; the claim narrowed to "these particular shifts did not produce a positive result". The study has no genuine positive control and now says so. |
| A9 | "The best result is below what chance would produce", from an expected-maximum reference over 33 paths. | The paths are strongly correlated and the expression assumes an independence they lack. Now stated as a matter of scale, explicitly not a test. |
| A10 | Family-fixed runs described as unable to abstain. | The cost band still produces Flat. What is removed is the **selector's** ability to fall back to a prior-only model. |

---

## B · Documentation facts — P1 unaffected

| # | What was wrong | Correction |
|---|---|---|
| B1 | The trial registry table quoted the **v5** configuration hash `e6c1776d…` while the header quoted v6's `03b76826…`. A reader checking the freeze against that table would conclude the configuration had been swapped. | Corrected. `verify_hashes.py` now requires every hash-like token anywhere in the protocol to resolve to a committed artefact, and was confirmed to fail on an injected bad digest. |
| B2 | §9.3 stated the pre-open window costs "about 18.7% of posts". | That measures a proxy — posts before 09:30 on any calendar day. The claim covers any post published before its assigned session's open, which includes the evening posts that dominate this feed. Correct figure **74.4%**, understated roughly fourfold. No result depends on it: §9.2 pre-commits to no trading test on that source. |
| B4 | **The frozen configuration hash did not verify on a fresh clone.** `.gitattributes` normalises text to LF in the repository; the working copy on Windows is checked out with CRLF, so `config/p1.yaml` was 15,689 bytes locally and 15,359 after a clone — identical content, two digests. The recorded hash was the local one, so anyone cloning the repository and running `verify_hashes.py` got **FAIL on the single most important check in the study**. | Found by cloning into a clean directory and running the verification scripts, which is now part of the release checklist. Digests of text artefacts are computed on the canonical LF form in `src/digest.py`, so the answer depends on content and not on a checkout setting. The recorded digest is now `03b76826…`; the previously quoted `c219757b…` is the same file with CRLF terminators, and the content was verified byte-identical after normalisation. Pinning line endings would have fixed this repository and broken again on the next machine. |
| B3 | "Empty text and scrape failure are cleanly separated; a scrape failure produces no row." | Unsupported when written — the collector writes an empty field whenever its regular expressions fail. Withdrawn, then established by measurement (see C1). The withdrawal stays in the record, because a claim is not acceptable merely because it later turns out to be right. |

---

## C · Data verification — re-checked, conclusions unchanged

| # | Question | Resolution |
|---|---|---|
| C1 | Are the 26.5% empty Truth Social rows text-free posts or extraction misses? | A structural extractor reading `div.status__content` was validated on 49 rows the old one did find text for (100% agreement), then applied to 148 empty rows: **zero extraction misses**. 26.5% is what it appears to be. The sample also found 92.6% of them carry an unused video transcript, recorded as a future direction rather than added. |
| C2 | Does the result survive the vendors revising history? | E21. Equity prices differ at ~8×10⁻⁷; four Treasury series differ on one cell each, all on the final session. ΔSharpe −0.0116, an order of magnitude inside the seed noise floor. **But 9.3% of positions changed** — the verdict is robust, the individual trades are not. |

---

## D · Exploratory execution — one defect reached trading output

| # | What was wrong | Correction |
|---|---|---|
| D1 | `get_spec` returned objects built with default parameters, so E24's configured `borrow_annual_bps: 0` was accepted, written into the manifest, and ignored. **E24 ran with the 25 bp charge it existed to remove.** | Found only because E24 came out bit-identical to E22, which cannot happen when 493 short positions pay a charge one of them removes. Fixed; unknown parameters now raise rather than being dropped; two regression tests added. E24 was rerun, and E22/E23 were rerun and confirmed bit-identical to their pre-fix output, proving the default path was untouched. **The incorrect run is retained in the registry as `E24-VOIDED-01` and counts against the multiple-testing total, because its result was inspected.** |

---

## E · Delivery gaps — promised and absent

| # | What was missing | Resolution |
|---|---|---|
| E1 | `config/p1.yaml` declared `calibration_diagnostics.csv` in its `outputs` and no run wrote it. Nothing failed; it was simply absent. | P1 was re-executed to emit it. Same data, configuration, seeds and package versions; the instrumentation consumes no random numbers and touches no selection or position. `verify_reproduction.py` confirms the two executions are bit-identical across every field, including the gross, cost and net components of every daily return and the reported metrics. The first execution is preserved under `results/p1_original/` as the primary result. Registered as `reproduction_output_regeneration` with `counts_toward_trial_budget=false`. |
| E2 | E21 was pre-registered in §7.2, omitted when the overlays were written, and its absence declared nowhere. | Run. See C2. |

Both gaps were silent — nothing failed, the artefacts were simply not there. Two
contracts now watch for exactly that: every output the configuration declares must
exist, be non-empty and carry its expected columns; and every P/E identifier the
protocol registers must have a registry row, **with ranges expanded**, since
`E20–E21` is precisely the notation E21 disappeared behind.

---

## A note on calibration

Not an error, but the same class of problem and worth recording beside them. Three
of the four calibration diagnostics the configuration requires are measured on the
calibrator's own fitting sample. Reporting them as evidence that calibrating helped
would have been wrong by a wide margin:

| | Brier |
|---|---:|
| In-sample view, LightGBM, before → after | 0.694 → 0.616 |
| **Out-of-sample for model and calibrator, before → after** | **0.62591 → 0.62646** |

Out of sample, calibrating made the probabilities very slightly **worse**. The
inner diagnostics are stamped `eligible_as_confirmatory_evidence=false` and the
outer comparison is reported instead.

---

## How to read this list

The distribution matters more than the count. Ten entries are about how results
were described, three about document facts, two about data checks that changed
nothing, two about missing deliverables — and one about an execution defect, which
occurred in the exploratory group and whose incorrect run is retained and counted.

What would be a serious finding is an entry in a category that does not appear
here: an error affecting P1's positions or reported returns. None was found.
