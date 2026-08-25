# Privacy

What personal information this repository contains, what it deliberately does not,
and what was removed after the fact.

---

## Deliberately retained

**Commit authorship — name and email.** Every commit carries them, as git records
them. This is normal version-control metadata and it is the mechanism by which
authorship of the work is attributable at all. It is not an oversight and is not
removed.

Anyone who prefers otherwise can enable GitHub's private-email setting and use a
`@users.noreply.github.com` address, but that is an account-level choice affecting
every repository, not something this project decides.

**Public sources, cited normally.** `@realDonaldTrump` as the subject of the
alternative-data layer, the Loughran–McDonald authors and their contact address as
the dictionary's licence requires, the archive's own address. These are citations,
not personal data about a user, and the scanning rules allowlist them by name rather
than being switched off.

---

## Deliberately excluded

Automated tests reject all of the following from any tracked file:

| | |
|---|---|
| Personal email addresses in code, data, logs or documentation | contact details belong in `SCRAPER_CONTACT` at run time |
| Local machine paths | `C:\Users\…`, `/home/…`, `/Users/…` — these record whose machine built an artefact and nothing a reader needs |
| Credentials of any kind | tokens, cookies, API keys, private keys, `.env` files |
| Third-party document text and identifiers | see `DATA_POLICY.md` |

The crawler identifies itself as `spy-next-day-signal-research/1.0`. A contact
address is added **only** if `SCRAPER_CONTACT` is set, and it defaults to unset.
Identifying a crawler is good practice; deciding whose address to identify it with
is the operator's decision, not the code's.

---

## Removed after the fact

Three things reached this repository before the rules above existed. All are
recorded rather than quietly fixed, because a reader assessing how carefully a
project handles data is entitled to know what it got wrong.

**A personal email address in the crawler's User-Agent.** It was hard-coded, and it
was therefore sent in the request headers of roughly 200 requests to the archive
before it was removed. Those requests are in that site's logs. Now
`SCRAPER_CONTACT`, unset by default.

**A machine user directory in a committed run log**, captured from a library
warning about a negative oil price. Sanitised, and now rejected by test.

**Third-party document text, three times.** The per-post archive, the per-headline
file, and a diagnostic that retained post bodies and video transcripts. All are
excluded from the current tree and from the history of the branch that carries this
work; see `docs/errata.md`.

---

## History

The branch carrying this study was rebuilt from a clean base so that no commit in
its ordinary reachable history contains the raw corpora or the local metadata above.
The previous repository contents are preserved under the `legacy-v1` tag and were
verified clean of these issues before that tag was made.

**One limit, stated precisely.** Force-updating a branch does not remove objects
that GitHub retains behind pull-request references (`refs/pull/N/head`,
`refs/pull/N/merge`) or in its caches. Those are outside a repository owner's
control and are cleared by GitHub on request. Until that request is confirmed, the
accurate statement is:

> Removed from the current branch and from ordinary reachable history. Pull-request
> references and provider-side caches are handled by GitHub and are not claimed to
> be purged.

It is not accurate to say the content has been "completely deleted from GitHub's
servers", and this document does not say so.

---

## Research integrity

The cleanup changed commit hashes. It changed **no** research value: the frozen
configuration, the model logic, the seeds, the daily out-of-sample predictions, the
positions, the gross, cost and net return components, and every reported conclusion
are identical before and after, verified field by field. See
`results/sanitization_equivalence.json`.
