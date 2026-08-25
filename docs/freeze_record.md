# Freeze Record

The original release tags were deleted and rebuilt after the research results were
produced, as part of removing third-party data this project has no right to
redistribute. **The rebuilt tags are not the original ones and are not presented as**
**such**: they carry a `-sanitized` suffix and different commit hashes.

This file is the record of what the originals were, so the substitution can be
audited rather than taken on trust. A rebuilt freeze tag is weaker evidence than one
that was never touched, and that loss is real and is not hidden here.

Three hash conventions appear below and are never mixed:

| Convention | Meaning |
|---|---|
| git blob SHA-1 | the object id git stores for the file at that commit |
| raw SHA-256 | the file's bytes at that commit, unnormalised |
| LF-normalised SHA-256 | CRLF collapsed to LF first; what `verify_hashes.py` checks |

## The market snapshot

```
market_inputs_2026-08-21.csv
9b337ca75f8d077963448853e97542fab1258ab5b6dd289debec14061012b13a
```

**Recorded identifier of the undistributed historical snapshot; the bytes cannot be**
**verified from a public clone.**

This is the file the frozen procedure names, and it is the input P1 actually ran on.
It is not in this repository and will not be: the prices come from a vendor whose
terms do not permit redistribution. The digest is kept so that a reader who obtains
the same vintage independently can confirm they hold the same bytes, and so that the
identifier the repository quotes in six places can be checked for internal
consistency. Neither of those is a verification of the original data, and
`verify_hashes.py` prints `NOT VERIFIED` rather than implying otherwise.

Supplying `data/market_inputs_2026-08-21.csv` together with its manifest turns that
consistency check back into a byte check automatically.

## `legacy-v1` → `legacy-v1-sanitized`

| | |
|---|---|
| original tag object | `668845641ebf701487ab1aee325c2e509f33d9aa` |
| original peeled commit | `0ee73f3d9bd68e0be6417506705f01cca1c5f606` |
| tagger | `tagger YuchengGao-26 <yg3072@columbia.edu> 1787610799 -0400` |
| config/p1.yaml blob SHA-1 | `0ee73f3d9bd68e0be6417506705f01cca1c5f606:config/p1.yaml` |
| config/p1.yaml raw SHA-256 | `n/a` |
| config/p1.yaml LF SHA-256 | `n/a` |

Original tag message:

```
The repository as it stood before this version
Preserved so the earlier work remains reachable and citable. The current study
replaces its contents entirely and shares no history with it; this tag is what
makes that replacement non-destructive.
```

## `protocol-v5-frozen` → `protocol-v5-frozen-sanitized`

| | |
|---|---|
| original tag object | `54b6870a63df88fbf79eea7d2321814f92e3dec4` |
| original peeled commit | `ef46c056da3823deb1675d61139868ead7d8bc77` |
| tagger | `tagger YuchengGao-26 <yg3072@columbia.edu> 1787546989 -0400` |
| config/p1.yaml blob SHA-1 | `f7dc94e4b89b33ebfd9df8083622a835397c1842` |
| config/p1.yaml raw SHA-256 | `cf18c7c8fe56176e67149d711d01625985ffeb253f14f770b17c8af8478e9d1f` |
| config/p1.yaml LF SHA-256 | `cf18c7c8fe56176e67149d711d01625985ffeb253f14f770b17c8af8478e9d1f` |

Original tag message:

```
Protocol frozen before the confirmatory procedure runs.
This tag marks the state of the repository at the moment the research design was
fixed and before any model had been fitted. The point of recording it is that the
claim "the method was not tuned to the answer" should be checkable rather than
as
```

## `protocol-v6-frozen` → `protocol-v6-frozen-sanitized`

| | |
|---|---|
| original tag object | `808a300b65bd3a6d14634aa6ceb3d78697b154fb` |
| original peeled commit | `a1c56365acbc5e3ef8559ca61eeb10502c269ebd` |
| tagger | `tagger YuchengGao-26 <yg3072@columbia.edu> 1787550127 -0400` |
| config/p1.yaml blob SHA-1 | `aa857723b8411f31bba97c3aafaa5431216da7a6` |
| config/p1.yaml raw SHA-256 | `03b768265c809581b4d2fe17703f4b303a43476b4ea5b037f91ba8ed1b024696` |
| config/p1.yaml LF SHA-256 | `03b768265c809581b4d2fe17703f4b303a43476b4ea5b037f91ba8ed1b024696` |

Original tag message:

```
Protocol v6 frozen. Supersedes v5 without replacing it.
Delta is held at zero in the confirmatory procedure rather than selected from a
grid. Selecting over it let the inner cross-validation choose a model and a
trading frequency at the same time, and the winner was reliably whichever
candidate trad
```

## `c2c-exploratory-frozen` → `c2c-exploratory-frozen-sanitized`

| | |
|---|---|
| original tag object | `b2194398a6c3667746314d27743470a5b9556878` |
| original peeled commit | `b9962d872dd204b26c74fbb36698794b2c31f1f6` |
| tagger | `tagger YuchengGao-26 <yg3072@columbia.edu> 1787585263 -0400` |
| config/p1.yaml blob SHA-1 | `aa857723b8411f31bba97c3aafaa5431216da7a6` |
| config/p1.yaml raw SHA-256 | `03b768265c809581b4d2fe17703f4b303a43476b4ea5b037f91ba8ed1b024696` |
| config/p1.yaml LF SHA-256 | `03b768265c809581b4d2fe17703f4b303a43476b4ea5b037f91ba8ed1b024696` |

Original tag message:

```
Close-to-close position rule fixed, before any C2C return was computed
```

## External evidence of ordering

Tag objects and commits can be rewritten; the following cannot be, by this project:

- pull requests #1 to #5 on the GitHub repository, with their creation, close and
  merge timestamps
- the GitHub Actions run history for every push, including the runs that failed
  before the corresponding fix

Those records place the freeze before the results and the cleanup after them.

## Reference mapping

| Original | Original commit | Rebuilt | Rebuilt commit |
|---|---|---|---|
| `legacy-v1` | `0ee73f3` | `legacy-v1-sanitized` | `f6b3780` |
| `protocol-v5-frozen` | `ef46c05` | `protocol-v5-frozen-sanitized` | `d71fad0` |
| `protocol-v6-frozen` | `a1c5636` | `protocol-v6-frozen-sanitized` | `ffbe692` |
| `c2c-exploratory-frozen` | `b9962d8` | `c2c-exploratory-frozen-sanitized` | `282e5ba` |
| `main` | `0ee73f3` | `main` | `6d54d68` |
| `v2-research` | `56b40d2` | `v2-research` | `23588b0` |
| `agent/add-truth-social-nlp-extension` | `e2c2339` | `agent/add-truth-social-nlp-extension` | `e1888df` |
| `agent/freeze-data-refresh-results` | `9dc1cda` | `agent/freeze-data-refresh-results` | `097f9f3` |
| `agent/add-fast-reproduction-mode` | `ddf038c` | `agent/add-fast-reproduction-mode` (unchanged) | `ddf038c` |

## Calendar columns

`session_minutes` and `is_half_day` are not vendor data. They are computed from the
NYSE trading-session rules published by `pandas_market_calendars` (version 5.4.0,
MIT licence) as `market_close - market_open` in minutes, and a session shorter than
390 minutes is a half day. They are redistributable on the strength of that MIT
licence and of being derived here rather than obtained.

## What this record cannot restore

The original tags are gone from this repository. Anyone who cloned it before the
cleanup holds the old objects, and the pull-request references GitHub serves may
still resolve to them until GitHub purges its caches. This record lets someone
holding those objects check them against what is written here; it does not, and
cannot, make a rebuilt tag as good as an untouched one.
