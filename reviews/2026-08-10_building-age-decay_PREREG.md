# Building-age decay — how fast does a new launch's premium erode, and when does it hit zero?

- **Status: PRE-REGISTERED, not run.** Design fixed 2026-08-10 (Mon) before the confirmatory data
  was pulled. **An exploratory pass has already been run and is disclosed in full below** — this is
  not a blind test, and the prediction it generated is stated here so the confirmatory run can
  contradict it.
- Proposed harness: new test **C** in `scripts/study_launch_vs_resale.py`, run in CI via the
  existing `study-launch-vs-resale` workflow so `URA_ACCESS_KEY` never leaves GitHub.
- Data: URA `PMI_Resi_Transaction`, condo/apartment. No new data source, no new subscription.

## Ledger check (required before starting — `C:\dev\CLAUDE.md`)

Four prior rows bear on this. Verdict: **ADJACENT — extends test A2, does not re-run it.**

| Row | Study | Status | What it gives us |
|---|---|---|---|
| 2026-07-10 · sg-property-decision | Tool build v1 | filed | The rule engine the published figures feed. |
| 2026-08-01 · sg-property-decision | New launch vs resale, tests A and B | filed | Test A is the entry gap. Its entry-gap figures were later voided; test B (infeasible) stands. |
| 2026-08-08 · sg-property-decision | Land bid → launch price | filed | The land-cost leg. Not touched here. |
| 2026-08-09 · sg-property-decision | Lease-matched entry gap (test A2) | filed | **The direct parent.** Measures the gap at *entry* against comparators bucketed by lease remaining, and finds it monotone. |

**This study exists because test A2 measured the gap at entry and explicitly declined to say what
happens to it afterwards.** That record's own ceiling: matching on lease "partly matches on the
newness being priced", and its caveats close with "one regime … a period estimate, not a law". It
answers *how much more you pay on day one*. It says nothing about *what you own on day 3,650*.

The published article built on it inherits the same silence, and fills it with an assumption —
which is the reason this study is being run at all (see *What must change downstream*).

## The question

A new launch sells at a large premium over the district's all-vintage resale median. **Does that
premium persist, decay, or invert as the building ages — and at what age does it reach zero?**

The question is not academic. `theenoughpoint.com/price-a-new-launch-before-the-price-list/`
publishes a break-even hurdle computed by pricing the buyer's **exit at the District 20 all-vintage
resale median**, and states that the hurdle "holds whenever you sell". If the premium decays
gradually rather than instantly, that sentence is false and the published hurdle is overstated for
any hold shorter than the decay period.

## The exploratory pass — disclosed, and not publishable

Run 2026-08-09/10 on `data/live.json` (project-level medians, already built, no new pull). Every
99-year leasehold project's current median $psf against its own district's volume-weighted
all-vintage median, grouped by age = 99 − lease remaining. n=381 projects, 26 districts.

Within the 750–950 sqft band, where median unit size is near-constant (786 → 910 sqft):

| Age | Premium over district median |
|---|---:|
| 6–10 | +13.5% |
| 11–15 | +0.3% |
| 16–20 | −7.1% |
| 21–30 | −13.1% |
| 31+ | −18.0% |

District 20 alone, monotone: Jadescape (8) +16.1%, Thomson Impressions (11) +6.0%, Sky Vue (13)
+8.6%, The Panorama (13) +3.1%, Sky Habitat (15) −1.2%, Thomson Grand (16) −10.1%, Grandeur 8 (24)
−26.5%, Braddell View (45) −48.0%.

**This must not be published.** The comparator is a median of project medians rather than of
transactions; age is measured today rather than at the transaction date; the size control is a
post-hoc stratification on a variable that was not in the cell key; and there is no per-cell guard.
It is recorded here as the reason to run the study and as the source of the prediction below.

## Design (fixed before running)

**Estimand.** For each **resale** transaction, its $psf against the median $psf of its own
`(district, quarter, size band)` cell — a cell that pools all building ages — with the
transaction's own project excluded from that median. Then grouped by **building age at the date of
the transaction**, not today.

Three improvements on the exploratory pass, each of which could overturn it:

1. **Transaction-level, not project-level.** The comparator becomes a median of transactions.
2. **Size band enters the cell key** rather than being stratified afterwards, so size is held by
   construction.
3. **Age is measured at the transaction date** — `contractDate` year minus lease commencement year
   — so a 2021 sale of a 2010 building counts as age 11, not age 16.

**Keyed on `typeOfSale`.** Resale only for the premium series. New sales are reported separately as
the age-0 anchor rather than being inferred from a lease cut-off, which is what the exploratory
pass had to do.

**Buckets.** 0–5, 6–10, 11–15, 16–20, 21–30, 31+.

**Tenure.** Original lease term 95–110 years (covers 99, 103, 110). Freehold and 999-year excluded;
`_lease_left` is already known to return four- and six-digit artefacts on 999-year strings.

**Reporting.** Pooled and by segment. Per bucket: median premium, n, district count, median sqft.

## Pre-specified prediction

Stated so that the confirmatory run can contradict it:

- The gradient is **monotone decreasing** in age.
- It crosses **zero between age 11 and 15**.
- The age 6–10 bucket lands in **+8% to +18%**.

**Falsification.** A flat gradient, a non-monotone one, or a zero-crossing outside 8–20 years
falsifies the exploratory result. In that event the published hurdle stands as written and this
study is filed as a negative.

## Three ways this could be silently wrong

Stated before running, per `C:\dev\CLAUDE.md`.

**1 — Age and unit size are collinear, and size drives $psf.** Newer stock is smaller (732 sqft
median in the exploratory 6–10 bucket against 1,292 at 31+) and small units carry a higher $psf
everywhere. A raw age gradient is partly a size gradient wearing its clothes. *Guard:* size band is
in the cell key, so the comparison is within band by construction. Median sqft is reported per
bucket so residual drift inside a band is visible. If the gradient collapses once size is keyed
rather than stratified, the exploratory finding was an artefact and must be reported as one.

**2 — En-bloc survivorship removes the old cohort's most valuable members.** A leasehold project
worth redeveloping leaves the sample when it is collectively sold, and what remains at 30+ years is
the residue nobody bid for. **The direction is genuinely ambiguous** — en-bloc candidates sit on
under-utilised land in good locations, which argues the sample loses winners and the gradient is
too steep; but en-bloc speculation also bids up a candidate's resale $psf before the sale, which
argues the opposite. There is no clean guard on free data. *Ceiling on the claim:* the decay
measured here applies to **stock that remained on the market**, and is not a statement about what
any individual building will do.

**3 — This is cross-sectional even at transaction level, so age and cohort are confounded.** The
free window is 5.25 years. A building observed at age 30 was built in the mid-1990s for a
mid-1990s market; one observed at age 8 was built for a post-2013 market of small units near
stations. The gradient may be measuring changing product rather than ageing. *Partial guard:*
compute the gradient separately for each calendar year in the window. If the 2021 gradient and the
2025 gradient have the same shape, the age–price relationship is stable and a pure cohort story is
harder to sustain. This does not eliminate the confound; it bounds it.

## The ceiling on the claim

The decay measured is the **sum** of lease run-down, physical depreciation and design
obsolescence. This design cannot separate them, and must not claim to. Test A2 already established
that the lease component alone is worth roughly 15% across the 85+/70–84 boundary; anything beyond
that is depreciation and fashion, unattributed.

## Stop condition

Any bucket with fewer than **30 transactions** or fewer than **5 districts** is reported infeasible
and published nowhere. A thin decay curve would be more damaging than the assumption it replaces,
because it would look measured.

## What must change downstream if it survives

1. **`theenoughpoint.com/price-a-new-launch-before-the-price-list/`** — the break-even table prices
   exit at the District 20 all-vintage median and asserts the hurdle "holds whenever you sell".
   That sentence becomes false, and the hurdle becomes a function of hold length. The exploratory
   pass puts the correction at roughly 10 percentage points for an 8-year hold.
2. The dashboard's fair-value card, which benchmarks against district medians without an age term.
3. Ledger row added and the record filed in `reviews/`, per `C:\dev\CLAUDE.md`.

## What this study does NOT attempt

- **Realised per-buyer return.** No unit identity in free URA caveats. Settled by the 2026-08-01
  record: needs REALIS at S$1,960/yr or an archive started now.
- **A longitudinal cohort.** A 5.25-year window cannot follow one building from 8 to 30 years old.
- **Attribution of the decay** between lease, depreciation and fashion.
- **Any claim that new launch is a good or bad purchase.** The decay is one input to a hurdle, and
  the hurdle is cleared or not by the entry price, which this study does not set.
