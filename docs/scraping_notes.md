# Alternative Data: Sources, Collection and Repair

Protocol §9.4 requires this document. Everything below is measured from the files
in question by `scripts/freeze_alt_data.py`, and the counts are re-emitted into
`data/alt/alt_data.manifest.json` on every build so this page and the data cannot
drift apart.

---

## 1. Financial news headlines

| | |
|---|---|
| Content | S&P 500 news headlines with the index close on the same date |
| Span in file | 2008-01-02 → 2024-03-04 |
| Rows in file | 19,127 |
| Exact duplicate rows | **974**, removed |
| Rows after deduplication | 18,153 |
| Unparseable dates | 0 |
| Empty titles | 0 |
| Overlap with the modelling set | **2,247 sessions**, of which 2,182 carry at least one headline and **65 carry none** |

**Deduplication is on the whole row.** 974 rows are byte-identical to another row —
same headline, same date, same close. Keeping them would weight those headlines
twice in every per-session aggregate for no reason anyone could defend. Rows that
share a headline but differ in date are kept: the same story running on two days is
two days of coverage.

**Availability assumption, stated because it cannot be verified from the data.**
The file carries dates and no times. A headline dated *D* is therefore treated as
fully known only after *D*'s close, so it enters bucket *D* and is acted on at
*D+1*'s open. This is conservative in one direction and not in the other: a
headline published at 06:00 on *D* is treated as if it arrived ten hours later than
it did, which throws away timeliness, and no headline is ever treated as available
before it was published. Given a file without times, that is the only assumption
that cannot manufacture look-ahead.

Every date in the file falls on an NYSE session, so nothing rolls forward. That is
a property of the source — it carries a closing price on every row — and not
something the mapping had to fix.

---

## 2. Truth Social archive

| | |
|---|---|
| Source | `trumpstruth.org`, which mirrors posts from `truthsocial.com/@realDonaldTrump` |
| Identifiers retained | archive URL and the original Truth Social status URL, per post |
| Span | 2024-07-13 → 2026-04-23 |
| Posts | 14,145 |
| Exact duplicate rows | 0 |
| Duplicate `status_id` | 0 |
| Overlap with the modelling set | **446 sessions**, of which 443 carry at least one post and **3 carry none** |
| Posts with no text | **3,749 (26.5%)** |

Collection used a crawl of the archive's status pages with a repair pass for rows
that failed on the first attempt. Both scripts are retained outside this
repository with the raw output they produced, and the raw file's SHA-256 is
recorded in the data manifest, so the frozen snapshot can be traced back to bytes
that were not written by this project.

### Empty posts are not missing posts

26.5% of rows carry an empty `text` field. **This is not scrape failure.** A row
exists, with a status id and a timestamp, and the post carried no text — an image,
or a repost with no added comment. A scrape failure produces no row at all, and the
repair pass exists to make that distinction hold. §9.4 requires the two to be kept
separate and they are: empty posts are excluded from the token and sentiment
aggregates and carried as their own feature, `truth_empty_post_count`.

Scoring them instead would be quietly destructive. An empty string contributes zero
positive and zero negative words, so a session of forty images would report a tone
of exactly zero — indistinguishable from a session of forty balanced posts, and
driven entirely by how much the account happened to post pictures.

### Timezone: the part that would have broken the alignment

The archive carries two time fields:

- `created_at_raw` — `"Saturday, July 13, 2024, 03:09 pm EDT"`, with the zone
- `created_at` — `"7/13/2024 15:09"`, a naive local wall time with no zone

**Reading `created_at` as UTC shifts every post four or five hours earlier.** The
frozen build parses `created_at_raw` with its own offset instead and records the
size of the error it avoided:

| Label | Posts | Error if the naive column were read as UTC |
|---|---:|---:|
| EDT | 9,314 | 4 hours |
| EST | 4,811 | 5 hours |
| absent | 20 | — |

This is not a cosmetic concern. **882 posts fall in the 16:00 hour**, against the
close, where a four-hour shift moves them into the previous session's bucket — a
look-ahead of exactly one session, in a layer built to test whether text predicts
the next session.

The 20 rows with no zone label are localised through `America/New_York`'s own
daylight-saving rule rather than assigned a guess, and counted separately, because
an unlabelled timestamp is a different object from a labelled one.

### Encoding: what was actually wrong, and what was not

The protocol's §9.4 refers to "the encoding damage and its repair". Measured
against the raw file, that phrase overstates what happened, and the accurate
account is this.

`ftfy.fix_text` was applied to the raw scrape and changed **4,486 of 14,145 rows**.
Sorted by what it actually removed:

| Character removed | Rows | What it was |
|---|---:|---|
| U+2019 `’` | 3,412 | typographic apostrophe, normalised to ASCII `'` |
| U+201C `“` | 2,260 | opening curly quote, normalised to `"` |
| U+201D `”` | 2,216 | closing curly quote, normalised to `"` |
| U+2018 `‘` | 274 | opening single quote |
| `&`, `#`, `;`, digits | ~13 | HTML numeric character references, e.g. `&#8217;`, left undecoded by the scrape |

**Classic UTF-8-read-as-cp1252 mojibake — `â€™`, `Ã©`, `Â ` — appears in one row,
and that row is a false positive**: a Daily Mail URL containing `article-14952289`.
There was no systematic encoding corruption.

So the repair was two different things: about a dozen rows of genuine damage,
undecoded HTML entities, and 4,486 rows of ordinary Unicode punctuation normalised
to ASCII. Calling the whole of it "encoding damage" would credit the cleaning step
with fixing a problem that mostly did not exist.

**The normalisation is not free, and its cost is measured rather than assumed.**
The tokeniser keeps ASCII apostrophes inside words, so `company's` is one token and
does not match Loughran–McDonald's `company`. Across both sources, the tokens that
would match the dictionary only after stripping a possessive are **99 of 629,089**
for Truth Social and **46 of 185,188** for news — 0.23% and 0.47% of all dictionary
matches respectively. Small enough to leave the tokeniser alone, and quantified so
that the decision is a decision.

### Near-duplicate reposts are kept

Posts 23853 and 23854 are four minutes apart and differ in one word — *"As me move
forward"* corrected to *"As we move forward"*. Deduplication is on `status_id`, so
both survive. That is deliberate: a deleted-and-corrected repost is two acts of
posting, and collapsing them would require a similarity threshold chosen by
somebody, which is a researcher degree of freedom in exchange for almost nothing.

---

## 3. Sentiment lexicon

| | |
|---|---|
| Dictionary | Loughran–McDonald Master Dictionary, 1993–2025, updated March 2026 |
| File | `Loughran-McDonald_MasterDictionary_1993-2025.csv`, 9.1 MB, 86,553 words |
| Source page | https://sraf.nd.edu/loughranmcdonald-master-dictionary/ |
| SHA-256 | `e2d1328682bab7d2187684fb9f5420bb730401c9eefc00daf835edd203f4859d` |
| Retrieval | `python scripts/fetch_lexicon.py` |

Category sizes as loaded: Negative 2,355 · Positive 354 · Uncertainty 297 ·
Litigious 905 · Strong-modal 19 · Weak-modal 27 · Constraining 184.

**Licence.** Free for use in academic research; commercial applications require a
licence from the authors. Cite Loughran, T. and McDonald, B. (2011), "When Is a
Liability Not a Liability? Textual Analysis, Dictionaries, and 10-Ks", *Journal of
Finance* 66(1), 35–65.

**The dictionary is not committed to this repository**, because this repository is
MIT-licensed and redistributing a file whose terms restrict commercial use inside
it would misstate what a reader is permitted to do. Reproducibility does not need
redistribution: it needs the same bytes and a way to check they are the same bytes.
`fetch_lexicon.py` retrieves the file and verifies the SHA-256 above, and
`src/altdata.py` refuses to run against a file that does not match — a different
dictionary version scores differently and is a different study.

**Why a published lexicon rather than a word list built here.** A general-purpose
sentiment dictionary scores *liability*, *tax*, *cost* and *restructuring* as
negative, which in financial text are ordinary vocabulary; that mismatch is the
finding the LM paper exists to report. Using it also removes a degree of freedom:
the word lists were fixed by someone with no stake in this study's outcome, years
before it, and can be checked by anyone.

The **topic** features are a different matter and are labelled as such. Their word
lists are bespoke, declared in `src/altdata.py` where they can be read and objected
to, and they are counted rather than scored. Keeping the citable part and the
bespoke part under separate names is the point.

---

## 4. Compliance

Both sources are publicly accessible archives of published material. Collection was
rate-limited and read-only, no authentication was used or bypassed, and no
non-public content was accessed. Only text that the publishers made public is
retained. Post identifiers and source URLs are kept so that any row can be traced
to its origin.
