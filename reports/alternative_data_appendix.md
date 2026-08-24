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
`truth_empty_post_count` — the count of rows the extractor returned no text for.
When a count of *empty rows* ranks with everything the text actually says, the
honest reading is that none of them is associated with tomorrow's return.

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

**What those 26.5% are was measured rather than assumed.** The collector extracts
the body by regular expression over the flattened page and writes nothing when no
pattern matches, so an empty field could mean a text-free post *or* an extraction
miss, and the archive alone does not separate them. `scripts/diagnose_empty_posts.py`
re-fetches a sample and reads the body element directly. Validated first on 49 rows
the old extractor did find text for — the structural reader agrees on 100% of them —
and then applied to 148 empty rows: **not one is an extraction miss.** All 148 are
genuinely text-free, 96 with an image attachment and 50 with a video.

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

### Results

All ten arms, in specification order. 1,247 out-of-sample sessions each, identical
rows, paired stationary bootstrap against N0.

| Arm | Alignment | Participation | Ann. mean excess | Sharpe | Δ Sharpe vs N0 | 95% interval |
|---|---|---:|---:|---:|---:|---:|
| **N0** | market only | 32.6% | +2.18% | **+0.213** | — | — |
| **N1** | true | 36.8% | −0.62% | −0.058 | −0.271 | [−0.704, +0.106] |
| N1p5 | *t−5* | 35.2% | −0.66% | −0.064 | −0.277 | [−0.767, +0.116] |
| N1p10 | *t−10* | 33.8% | −0.53% | −0.051 | −0.264 | [−0.723, +0.121] |
| N1p20 | *t−20* | 33.7% | −0.20% | −0.019 | −0.232 | [−0.704, +0.186] |
| N1p60 | *t−60* | 34.8% | +2.51% | **+0.242** | +0.029 | [−0.301, +0.377] |
| N1m5 | *t+5* | 33.4% | −1.84% | −0.177 | −0.390 | [−0.871, +0.001] |
| N1m10 | *t+10* | 34.3% | +0.41% | +0.039 | −0.174 | [−0.905, +0.519] |
| N1m20 | *t+20* | 27.5% | +0.39% | +0.042 | −0.171 | [−0.721, +0.408] |
| N1m60 | *t+60* | 31.9% | −1.04% | −0.103 | −0.316 | [−0.925, +0.201] |

**Every one of the nine intervals includes zero.** Adding news at the true
alignment moves the Sharpe ratio by −0.271, and that is not distinguishable from
no change.

**Read the positive controls before drawing any conclusion about news.** N1m5,
N1m10, N1m20 and N1m60 were handed headlines from five, ten, twenty and sixty
sessions in the future — information no tradeable procedure could have. **All four
have negative point estimates against N0.** Being told the future did not help.

That reframes the whole test. A null at the true alignment would ordinarily be read
as "these headlines do not predict this return". Here it cannot be, because the
procedure did not improve when given headlines that trivially do contain the
answer. **What the experiment establishes is a property of the procedure, not of
the data**: at this sample size, with this feature screen, adding thirty-seven
text columns to eighty-one market columns degrades the result regardless of what
the text says. The screen must choose twenty-five features from one hundred and
eighteen instead of eighty-one, and the cost of the extra dilution exceeds anything
the additional columns contribute.

The placebo arms make the same point from the other side. N1p60 — news from sixty
sessions earlier, three months stale — is the **best of all ten arms** at +0.242,
nominally above the market-only control. Nobody should believe three-month-old
headlines predict tomorrow's open-to-close return. That row is what noise looks
like when ten arms are run, and it is exactly why the protocol requires all ten to
be reported rather than the best one.

**What this does not license.** It is not evidence that financial news carries no
information about next-day returns. It is evidence that this procedure, on this
sample, cannot detect such information even when it is inserted artificially. A
design that could — fewer, stronger text features; a screen that does not put text
and market columns in direct competition; a longer sample — is a different study,
and one this result gives a concrete reason to specify.

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

**A large share of the available text is not used.** The diagnostic above found
that **92.6% of text-free posts carry a video transcript** — archive-generated text
for video attachments, roughly 3,470 posts' worth of spoken content that no feature
here touches, because the original collector never extracted it. This is the most
substantial known gap in the layer.

It is left open on purpose. Adding transcripts now, having seen that the news layer
produced nothing, would be a new specification chosen in response to a null result,
which is the move §7.2 exists to prevent. It is a pre-registrable direction for a
future round rather than a repair to this one — and it would need its own
justification, since a transcript is spoken rather than typed and machine-produced
rather than authored, and concatenating it onto the post body would silently mix
two different kinds of evidence.
