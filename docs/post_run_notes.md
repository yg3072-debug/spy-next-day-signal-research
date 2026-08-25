# Post-Run Notes

`docs/research_protocol.md` is frozen. It is the document that fixed every degree of
freedom **before** the confirmatory run, and it is preserved byte-for-byte as it stood
at the freeze — editing a pre-registration after seeing results would destroy the only
thing that makes it worth anything.

Things learned after the run therefore go here, or into `docs/errata.md` when they are
corrections. This file holds the ones that are neither errors nor results: changes to
how the work is verified.

Research errors are in `docs/errata.md`. Methodological reasoning is in
`docs/decision_log.md`. Results are in `reports/`.

---

## The automated suite grew after the freeze

The protocol records 38 checks, which is what `tests/` held on 2026-08-24. It has grown
since. **No protocol text, configuration value, model, parameter, split, cost, position
rule or reported figure changed with any of it**, and `config/p1.yaml` still hashes to
the digest recorded in Appendix A.

The additions fall into three groups.

**Properties of the completed run's output.** That a flat session is charged no
execution cost and no financing; that every realised position equals what §3.3's
no-trade band implies for its `mu_hat`; that the reported class probabilities sum to
one; that the majority baseline's `mu_hat` is constant within an outer block and
changes across blocks; and that each out-of-sample session appears exactly once. These
check the run against the procedure that was specified, which is the opposite of
adjusting the procedure to the run.

**The second execution specification.** The close-to-close arm (§ the C2C addendum)
brought its own checks, one of which pins the primary open-to-close implementation
against the committed run and requires agreement to the last bit. A refactor that
changed a number would fail it.

**Guards for things that had already gone wrong.** Each of these exists because
something silently passed when it should not have: the frozen configuration's digest
failing on a fresh clone because of line-ending normalisation, an output the
configuration promised that no run ever wrote, and a pre-registered trial that was
never executed. All three are recorded in `docs/errata.md` with what they affected.
None changed a research value.

A suite that grows while the document keeps quoting the frozen count makes the freeze
harder to check, not easier. Hence this note. The state at freeze is tagged and can be
diffed against the current tree.

---

## Verification entry points

| Question | Command |
|---|---|
| Is the frozen configuration the one on record? | `python scripts/verify_hashes.py` |
| Is the frozen protocol document unaltered? | same command; it checks the document digest |
| Do the financing fields rebuild from public data? | `python scripts/verify_financing_from_board.py` |
| Is the re-execution the same trial? | `python scripts/verify_reproduction.py` |
| Does everything else still hold? | `pytest tests/ -q` |
