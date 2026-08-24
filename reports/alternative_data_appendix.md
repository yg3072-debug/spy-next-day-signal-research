# Alternative Data — Exploratory Appendix

Protocol §9. Outside the confirmatory core: **nothing here can change the P1
headline, in either direction.**

Two sources, treated differently on purpose. The news headline sample is long
enough to support the same walk-forward the primary study uses, so §9.1 runs an
incremental test on it. The Truth Social sample is not, and §9.2 commits in advance
to running **no trading test on it at all**. That commitment was made before the
data was built and is honoured below.

---

## 1. Why no trading test on Truth Social

This is the part of the appendix that matters most, and it is a decision rather
than a result.

The archive overlaps the modelling set on **446 sessions**. Compressing the initial
training block from 1,000 sessions to 200 — already an abuse of the procedure —
leaves 246 sessions to evaluate on. The question is what a comparison on 246
sessions can resolve, and it is answerable without running anything.

Measured on P1's own realised returns over the same windows, by the same paired
stationary bootstrap the confirmatory report uses:

| Window | Sessions | SE of a Sharpe difference | Smallest detectable difference |
|---|---:|---:|---:|
| P1's full out-of-sample | 1,865 | 0.338 | 0.66 |
| Truth Social overlap | 446 | 0.692 | 1.36 |
| **Overlap minus a 200-session training block** | **246** | **1.149** | **2.25** |

**Only a Sharpe difference above roughly 2.25 would be distinguishable from zero
on this sample.** The protocol pre-registered 1.07 and "roughly 2.1" from a
formula; the measured values are 1.149 and 2.25, slightly worse, so the
pre-registered reasoning was if anything optimistic and its conclusion stands
unchanged.

No effect size has to be assumed for this to settle the question. A strategy with a
true Sharpe of 2.25 over a market benchmark would be an extraordinary finding; a
procedure that can only report "significant" when it sees one is not a test, it is
a lottery ticket. **Running it anyway and reporting whatever Sharpe came out is
exactly the failure mode the rest of this protocol exists to prevent.** The layer
therefore delivers lineage, mapping, features and description, and stops there.

What it is not: the sample is not dismissed as uninteresting, and no claim is made
that Truth Social carries no information. The claim is narrower and checkable —
this sample cannot resolve the question, so no answer to it is reported.

---

## 2. The session mapping, and what it is worth

§9.3 assigns text to `bucket_t = (close_{t−1}, close_t]`, so a post is attached to
the session whose close it precedes, and acted on at the next open. The obvious
alternative is to bin by calendar date. The difference is not cosmetic:

| | |
|---|---:|
| Posts assigned to a **different** session by calendar-day binning | **4,710 of 14,145 (33.3%)** |
| Sessions whose post count changes between the two schemes | 431 of 446 |
| Mean absolute difference per session | 9.9 posts |
| Largest single-session difference | 157 posts |

**Every disagreement runs the same way: calendar binning places the post
earlier.** 3,750 posts move one session earlier, 810 move three — the Friday
evening posts that a calendar scheme dates to Friday but that no one could act on
until Monday's open. Calendar-day binning is therefore not a different convention
with different trade-offs. It is a look-ahead, applied to a third of the sample.

The mapping is verified directly rather than through the features that depend on
it. `tests/test_altdata.py` pins the right-closed boundary at the close, the 13:00
close on half days, both sides of the March 2024 daylight-saving transition,
weekend and holiday roll-forward, and — on the committed snapshot — that **no post
is dated after the close of the session it is attached to**.

### The timezone trap

The archive carries the zone in `created_at_raw` (`"…03:09 pm EDT"`) and a separate
naive `created_at` (`"7/13/2024 15:09"`). Reading the naive column as UTC shifts
every post four or five hours earlier. **882 posts fall in the 16:00 hour**, right
against the close, so that error would move them into the previous session's
bucket — a one-session look-ahead in a layer built to test whether text predicts the
next session. The build parses the raw field with its own offset: 9,314 posts EDT,
4,811 EST, 20 with no label localised through the zone's own daylight-saving rule
and counted separately.

---

## 3. What the sources look like

### News headlines

| | |
|---|---:|
| Rows in file / after removing 974 exact duplicates | 19,127 / 18,153 |
| Overlap with the modelling set | **2,247 sessions**, 65 with no headline |
| Headlines per session, mean / median / max | 6.6 / 4 / 55 |
| Median tokens per headline | **10** |
| Mean LM tone | −0.098 |
| Sessions where tone is exactly zero | **34.5%** |

### Truth Social

| | |
|---|---:|
| Posts | 14,145, no duplicate status ids |
| Overlap with the modelling set | **446 sessions**, 3 with no post |
| Posts with no text | **3,749 (26.5%)** |
| Scored posts per session, mean / median / max | 23.5 / 16 / 142 |
| Empty posts per session, mean / max | 8.5 / 159 |
| Median tokens per non-empty post | **45** |
| Mean LM tone | −0.066 |
| Sessions where tone is exactly zero | 4.3% |

**A ten-token headline is a coarse instrument for a sentiment dictionary.** On more
than a third of sessions no Loughran–McDonald word appears in any headline at all,
and tone is exactly zero — not neutral sentiment, but no measurement. That is a
property of headline text, not of the dictionary, and it is the single largest
practical limitation of the news layer. Truth Social posts are four times longer and
this problem largely disappears there, which is the one respect in which the shorter
sample is the better instrument.

### Association with the next session's return

Spearman correlation against the next session's open-to-close return, computed on
sessions with content. These are descriptive, and no interval is attached because
none was pre-specified:

| Feature | ρ | | Feature | ρ |
|---|---:|---|---|---:|
| `news_doc_count` | +0.031 | | `truth_doc_count` | +0.015 |
| `news_tone` | +0.011 | | `truth_tone` | +0.007 |
| `news_negative_rate` | +0.006 | | `truth_negative_rate` | −0.022 |
| `news_uncertainty_rate` | +0.031 | | `truth_empty_post_count` | **+0.056** |

Every one of them is within noise of zero. The largest in absolute value belongs to
`truth_empty_post_count` — the number of **images and text-free reposts**. When
counting pictures is as associated with tomorrow's return as anything the text
says, the honest reading is that none of them is associated with it.

---

## 4. Features

37 features, generated into `docs/alt_feature_dictionary.md` from the registry in
`src/altdata.py` so the documentation cannot drift from the code.

**Sentiment and topic are deliberately not the same kind of thing, and are not
given the same kind of name.** Sentiment uses Loughran–McDonald: published,
citable, versioned, fixed by people with no stake in this study, and checksum-
verified at load. Topic features are keyword counts whose word lists were written
for this project and carry none of that authority; they are declared in code where
they can be read and argued with. Collapsing both into one table of "NLP features"
would launder the second into the credibility of the first.

Two construction choices are worth stating because the alternatives are quietly
destructive.

**Empty text is counted, not scored.** An empty string contributes zero positive
and zero negative words, so a session of forty text-free rows would report a tone of
exactly zero — indistinguishable from forty balanced posts. Scoring them would make
every tone estimate a function of how many such rows there were. They are excluded
from the aggregates and carried as `truth_empty_post_count`.

**What those 26.5% are cannot be fully determined**, and an earlier draft of this
appendix overstated it. The collector extracts the post body by regular expression
over the flattened page and writes nothing when no pattern matches, so an empty
field means "the extractor returned nothing" — either a genuinely text-free post or
an extraction miss. All 3,749 such rows do carry a status id, both URLs and a parsed
timestamp, so the page was fetched successfully and these are not network failures.
26.5% is an upper bound on text-free posts containing an unknown number of misses.
`docs/scraping_notes.md` carries the detail.

**Sessions with no documents are kept, with zero counts and neutral tone.**
Dropping them would make the alternative-data sample a non-random subset of the
market sample — quiet sessions removed, busy ones retained — and every comparison
against the market-only arm would then be confounded by which rows survived.

Zero-variance topic columns are dropped inside each fold's own training slice, not
globally, for the same reason every other estimate here is fold-local.

---

## 5. §9.1, the news incremental test

Ten arms, all pre-registered, all reported:

| Arm | Feature set | Alignment |
|---|---|---|
| N0 | market only | — |
| N1 | market + news | true |
| N1p5, N1p10, N1p20, N1p60 | market + news | shifted **+k**: news from *t−k* |
| N1m5, N1m10, N1m20, N1m60 | market + news | shifted **−k**: news from *t+k* |

Both arms are restricted to the same 2,247 overlap sessions. Running the market-only
arm on the full sample and the news arm on the overlap would confound the feature
set with the window, which is the most common way an incremental test is quietly
not one.

The positive shifts are the placebo §9.1 asks for: stale news, still legitimate
information. **The negative shifts are not a placebo — they are a positive
control.** They hand the model text it could not have had. If next month's
headlines do not improve the result either, then a null at the true alignment says
much less than it appears to: it would mean the pipeline cannot detect text of this
kind at all, and the interesting quantity is the sensitivity of the procedure rather
than the informativeness of the data. Knowing which of the two applies is worth more
than the incremental test itself.

Results are appended when the runs complete, in full and without selection.

---

## 6. Limitations

**Headline availability is assumed, not observed.** The file carries dates without
times, so a headline dated *D* is treated as fully known only after *D*'s close.
That is conservative and it costs intraday timeliness on purpose, but it cannot be
verified from the data.

**The pre-open window is forgone, and this costs more than the protocol first
stated.** §9.3 keeps the alternative data on the same end-of-day information set as
the market variables. Relative to a separate morning pipeline that acts at the open,
**10,520 of 14,145 posts (74.4%)** could have been acted on one session earlier. The
protocol quoted 18.7%, which measures a narrower proxy; the discrepancy is logged as
an erratum in the version record. The design choice stands — comparability with the
market features is what it buys — but the concession is four times larger than
recorded.

**One account, one news source, one market.** Truth Social is a single author over
21 months; the headline file is one publisher's selection. Neither is a
representative sample of financial text.

**The text sample ends before the market sample does.** The archive runs to
2026-04-23 and the market snapshot to 2026-08-21, a gap of 83 trading sessions.
Closing it would move the smallest detectable Sharpe difference from 2.40 to 2.16 —
measured, not assumed — which changes nothing about §9.2's conclusion, so the
snapshot was left as collected rather than re-scraped for a result that cannot
turn on it.

**Topic word lists are bespoke.** They were written for this project and have not
been validated against anything. They are visible in `src/altdata.py` precisely so
that a reader can discount them appropriately.
