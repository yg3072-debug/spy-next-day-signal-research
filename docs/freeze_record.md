# Freeze Record

The identifiers that make the pre-registration checkable: what was frozen, what it
hashes to, and how to confirm a copy is the same one.

Release references were recreated after non-redistributable source data was removed
from the public repository. The frozen configuration and reported research outputs
were unchanged.

---

## Hash conventions

Three appear below and are never mixed.

| Convention | Meaning |
|---|---|
| git blob SHA-1 | the object id git stores for a file at a given commit |
| raw SHA-256 | the file's bytes, unnormalised |
| LF-normalised SHA-256 | CRLF collapsed to LF first; what `verify_hashes.py` checks |

Text artefacts are hashed on the canonical LF form so the answer is a function of
content rather than of a checkout setting. Data files are hashed verbatim.

---

## The frozen configuration

```
config/p1.yaml
03b768265c809581b4d2fe17703f4b303a43476b4ea5b037f91ba8ed1b024696
```

Committed, and **verified on every CI run**: `verify_hashes.py` recomputes it from
the bytes in the checkout and fails the build on any mismatch.

The protocol's own tables quote `c219757bb47c087e269e4ccd7e9f03f8ca7b35a5ff119c0d49a04222a5ccb1e7`,
which is the same file with CRLF terminators. The two were verified byte-identical
after normalisation; `docs/errata.md` B4 records why the recorded value changed and
confirms that no configuration value did.

## The frozen protocol document

```
docs/research_protocol.md
b94d63174508f8c795f3c4ee981f30bee12ec4d13e2f747596a786fa2346e3b9
```

The pre-registration itself, preserved byte-for-byte as it stood at the freeze and
verified against this digest on every CI run. It is deliberately **not** edited to
reflect anything learned afterwards — a pre-registration that is revised after seeing
results is not evidence of anything. Later findings live in `docs/errata.md`,
`docs/post_run_notes.md` and the reports.

## Historical identifiers

Digests that appear in the frozen documents and refer to superseded states. They are
recorded here so a reader who meets one can resolve it, and so `verify_hashes.py` can
tell a documented historical reference from an arbitrary stale hash — anything not
listed here and not reconstructible from a committed artefact is rejected.

```
e6c1776df8dd3b16f8fe0b3192cd417a6bd4c192648298fc444bae1c5529277d
    protocol v5 configuration, superseded by v6

c219757bb47c087e269e4ccd7e9f03f8ca7b35a5ff119c0d49a04222a5ccb1e7
    config/p1.yaml with CRLF terminators, superseded by the LF-normalised digest
```

The v5 digest appears in the frozen protocol's trial registry table while its header
quotes v6. That inconsistency is real and is recorded as `docs/errata.md` B1; it is
left in place because the document is frozen. The configuration that actually ran is
the one in Appendix A, and it is the one CI verifies.

## The market snapshot

```
market_inputs_2026-08-21.csv
9b337ca75f8d077963448853e97542fab1258ab5b6dd289debec14061012b13a
```

**Recorded identifier of the undistributed historical snapshot; the bytes cannot be
verified from a public clone.**

This is the file the frozen procedure names and the input the confirmatory run used.
It is not in this repository and will not be: the prices come from a vendor whose
terms do not permit redistribution. The digest is kept so that a reader who obtains
the same vintage independently can confirm they hold the same bytes, and so the
identifier this repository quotes in six places can be checked for internal
consistency. Neither is a verification of the original data, and `verify_hashes.py`
prints `NOT VERIFIED` rather than implying otherwise. Supplying the CSV together with
its manifest turns that consistency check back into a byte check automatically.

---

## Release reference mapping

| Original | Original commit | Current | Current commit |
|---|---|---|---|
| `legacy-v1` | `0ee73f3` | `legacy-v1-sanitized` | `f6b3780` |
| `protocol-v5-frozen` | `ef46c05` | `protocol-v5-frozen-sanitized` | `d71fad0` |
| `protocol-v6-frozen` | `a1c5636` | `protocol-v6-frozen-sanitized` | `ffbe692` |
| `c2c-exploratory-frozen` | `b9962d8` | `c2c-exploratory-frozen-sanitized` | `282e5ba` |

Full identifiers of the current tags:

```
legacy-v1-sanitized               b7b3c2326e108577cd77ddfcc676a5eec71d22ea
protocol-v5-frozen-sanitized      9196e14b633dd8a787cb1fc63d0947a195460892
protocol-v6-frozen-sanitized      924e97f5deee7b0c8292f8db4a2485af65ec89eb
c2c-exploratory-frozen-sanitized  f1a8338dd5b65eae5afd0d41e8529c749e54dbde
```

The `-sanitized` suffix is deliberate. **These are not the original tag objects and
are not presented as such**: they carry different hashes, and a rebuilt freeze tag is
weaker evidence than one that was never touched. That loss is real and is stated here
rather than papered over. What the mapping provides is a way for anyone holding the
original objects to check them against this record.

`protocol-v6-frozen-sanitized` is the reference for the confirmatory study.
`protocol-v5-frozen` is not overwritten by it: v6 is a separate tag with a separate
configuration hash, so the two states remain distinguishable.

## External evidence of ordering

Tag objects and commits can be rewritten. The following cannot be, by this project:

- the pull-request history on the GitHub repository, with creation and close timestamps
- the GitHub Actions run history for every push, including runs that failed before the
  corresponding fix

Those records place the freeze before the results.

---

## Calendar columns

`session_minutes` and `is_half_day` are not vendor data. They are computed from the
NYSE trading-session rules published by `pandas_market_calendars` (version 5.4.0, MIT
licence) as `market_close - market_open` in minutes, with a session shorter than 390
minutes counted as a half day. They are redistributable on the strength of that
licence and of being derived here rather than obtained.

---

## What this record does not claim

It does not make a rebuilt tag as good as an untouched one, and it does not assert
that the current objects are the original ones. It records what the originals were,
what the current ones are, and what each artefact hashes to, so that the substitution
can be audited rather than taken on trust.

Anyone who cloned the repository earlier holds the older objects and can compare them
against the values above.
