# Lease-matched entry gap — how much of the new-launch premium is newness, and how much is just a longer lease?

- **Status: PRE-REGISTERED, not run.** Design fixed 2026-08-08 (Sat) before any data was pulled.
- Proposed harness: new test **A2** in `scripts/study_launch_vs_resale.py`, run in CI via the
  existing `study-launch-vs-resale` workflow so `URA_ACCESS_KEY` never leaves GitHub.
- Data: URA `PMI_Resi_Transaction`, condo/apartment. No new data source, no new subscription.

## Ledger check (required before starting — `C:\dev\CLAUDE.md`)

Three prior rows bear on this. Verdict: **ADJACENT — do not re-run test A, extend it.**

| Row | Study | Status | What it gives us |
|---|---|---|---|
| 2026-08-01 · sg-property-decision | New launch vs resale, tests A and B | filed | **Test A is the entry gap and is already computed**, size-band and tenure-class matched, project excluded from its own benchmark. Harness, pre-registration and 34 self-tests exist. |
| 2026-08-08 · sg-property-decision | Land bid → launch price | filed | The land-cost leg, now re-derived. Removes land cost from the untested list. |
| 2026-07-10 · sg-property-decision | Tool build v1 | filed | The rule engine the published figures feed. |

Record to reuse: `reviews/2026-08-01_launch-vs-resale.md` and `scripts/study_launch_vs_resale.py`.

**This study exists because the prior record says it could not do this.** Its own words on test A:
the district resale median "mixes every vintage, including stock thirty years old, so the gap
blends the genuine new-build premium … with a plain age-and-condition difference". Its caveats add
that the gap "is not size-adjusted beyond four bands" and that "location within district is
uncontrolled". The blend it names is the thing this study tries to bound.

Prior result being extended, from that record:

| Segment | Median gap | p25 – p75 | n |
|---|---|---|---|
| OCR | +34.4% | +24.4 to +42.6 | 493 |
| RCR | +62.1% | +48.2 to +76.4 | 547 |
| CCR | +82.7% | +70.7 to +97.2 | 333 |

## The question

A new launch sells a fresh 99-year lease. The district resale median it is measured against is
mostly stock with decades less to run. **How much of that gap is the building being new, and how
much is simply the lease being long?**

The question matters editorially because a single "new launches cost X% more" figure is quoted
constantly, ours included, and if a large part of it is lease rather than newness then the figure
is not measuring what readers are told it measures.

## Why it is worth running: the informal signal

A crude project-level proxy (currently-selling launches against District resale projects with
≥85 years remaining, volume-weighted, **not size-matched**, n=39 pairs) returned a median gap of
**+32.6%** against the +62.1% RCR figure above. If that survives a proper treatment, roughly half
the headline gap is lease rather than newness.

**That number is a hint and must not be published.** It is not size-matched, its comparator is a
median of project medians rather than of transactions, and it has no per-cell guard. It is
recorded here only as the reason to run the study.

## Design (fixed before running)

**Estimand.** New-sale $psf against the contemporaneous district resale median, same size band,
same tenure class, project excluded from its own benchmark — identical to test A in every respect
except one: the resale comparator is additionally restricted by **lease remaining**.

**Primary.** Comparator restricted to leasehold with **≥85 years remaining**. This is the
like-for-like read a buyer of a fresh 99 actually faces.

**Secondary — the gradient.** The same gap computed against comparators bucketed by lease
remaining: ≥85, 70–84, 55–69, <55 years. The shape across buckets is the finding; a monotone
gradient is the signature of a lease effect, and a flat one falsifies the premise.

**Reporting.** By segment and by calendar year, reusing the existing n≥20 per-cell guard and the
existing convergence follow-up format.

**No new data.** Lease remaining is derivable from the free feed's tenure string and is already
implemented as `_lease_left` in `scripts/fetch_data.py`. Freehold comparators are excluded from
the primary and reported separately.

## Three ways this could be silently wrong

Stated before running, per `C:\dev\CLAUDE.md`.

**1 — Thin cells wearing the clothes of a finding.** Restricting the comparator to ≥85 years cuts
hardest in exactly the districts that have little modern stock, so surviving cells will
concentrate in districts that happen to have had recent land release. A segment median built from
four such districts is not a segment median. *Guard:* a minimum comparator count per
district-quarter-band cell; report cells dropped and districts lost against the full test-A set;
refuse to publish a segment whose surviving districts differ materially from it. The 2026-08-01
record is valuable precisely because it reported **0 qualifying** rather than a thin number, and
the same answer must be available here.

**2 — Lease and newness are collinear by construction.** Stock with ≥85 years remaining is also
newer, better specified, and more likely near an MRT, because recent government land release is
transit-oriented by policy. Matching on lease therefore partly matches on the very newness being
priced. **This study can bound the blend; it cannot decompose it.** Publishing the result as "the
pure lease effect" would be the headline error, and the write-up must state the ceiling
explicitly: the true newness premium is *no larger* than the lease-matched gap, which is the
useful claim, rather than *equal* to it.

**3 — Redevelopment survivorship in the comparator.** What still has ≥85 years is what was built
recently, which is what sits on land released recently — a non-random slice of each district's
geography. The comparator drifts towards particular pockets, so part of any narrowing is location
within district, which test A already flags as uncontrolled and this restriction makes worse, not
better. *Partial guard:* report the comparator's median distance to MRT alongside the gap, so a
location drift is visible rather than assumed absent.

## Stop condition

If the per-cell guard leaves fewer than 20 comparisons in any segment, report the segment as
infeasible and publish nothing for it. A thin lease-matched number would be more damaging than the
un-matched one it replaces, because it would look more precise.

## What gets published if it survives

- The venture's benchmark sentence changes from one number to two: the un-matched gap and the
  lease-matched gap, with the difference named as vintage rather than premium.
- The published articles carrying +62.1% are updated. Currently:
  `TheEnoughPoint/theenoughpoint` → `price-a-new-launch-before-the-price-list.mdx` (already
  qualified in prose pending this study) and `new-launch-or-resale-who-picked-the-dates.mdx`.
- Ledger row added and the record filed in `reviews/`, per `C:\dev\CLAUDE.md`.

## What this study does NOT attempt

- Realised per-buyer return. Free URA caveats carry no unit identity; the 2026-08-01 record
  settles that this needs REALIS at S$1,960/yr or an archive started now.
- Floor, stack or condition control. `floorRange` is too coarse, as the prior record notes.
- Any causal claim about why segments differ.
