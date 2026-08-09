# Lease-matched entry gap — how much of the new-launch premium is newness, and how much is lease?

- Run: 2026-08-09 (Sun) · `scripts/study_launch_vs_resale.py::test_a2_lease_matched`, live in CI
  (workflow_dispatch run 31301406133, `Study — new launch vs resale`; the district fix and the
  baseline fix were each re-run, and the figures here are from the final run)
- Design: **pre-registered 2026-08-08 before any data was pulled** —
  `reviews/2026-08-08_lease-matched-entry-gap_PREREG.md`. Followed without amendment.
- Data: URA `PMI_Resi_Transaction`, condo/apartment, 105,599 transactions, 28 districts.
- Output: `reviews/launch_vs_resale_result.json` → `test_a2_lease_matched`

## Verdict

**Two findings. The second one invalidates the first study's headline and two published pages.**

**1. The new-build premium is roughly the same everywhere once lease is matched.** Restrict the
resale comparator to leasehold with 85+ years remaining and all three segments converge on about
**+30%**: CCR +31.8%, OCR +30.3%, RCR +30.2%. The apparent segment spread without that
restriction (+40.1 / +50.0 / +44.1) is substantially **which vintage of stock each segment happens
to hold**, not a segment-specific premium. That is the publishable result.

**2. Every comparator pool in the prior study was national, not district.** In
`PMI_Resi_Transaction` the district field sits on the transaction; the harness read it off the
project, where it does not exist. Every row carried `district=None`, so the pools keyed
`(district, quarter, band)` merged all 28 districts into one. What the study called "the
contemporaneous district resale median" was a **national** median within size band and tenure.
The 2026-08-01 entry-gap figures are void, and so is the `+62.1%` quoted on two live pages.

## The correction, in numbers

| Segment | Filed 2026-08-01 (VOID) | Corrected, same test | Change |
|---|---:|---:|---:|
| CCR | +82.7% | **+42.2%** (n=293) | −40.5pp |
| RCR | +62.1% | **+46.9%** (n=483) | −15.2pp |
| OCR | +34.4% | **+52.0%** (n=405) | +17.6pp |

The order of the three segments **fully reverses**: CCR was dearest and is now cheapest.

The direction of each error is what the mechanism predicts, which is the strongest evidence the
diagnosis is right. Pooling nationally priced a CCR new sale against a pool containing cheap OCR
resale, inflating CCR; and priced an OCR new sale against a pool containing expensive CCR resale,
deflating OCR. RCR, in the middle, moved least. The rank order of the three segments reverses.

## Result — the lease gradient

Same new sales throughout. Only the comparator changes.

| Lease left on comparator | CCR | OCR | RCR |
|---|---:|---:|---:|
| **85+ years (primary)** | **+31.8%** (n=69, 3 districts) | **+30.3%** (n=277, 9) | **+30.2%** (n=245, 9) |
| 70–84 | +43.8% (n=46, 5) | +52.5% (n=275, 10) | +50.4% (n=198, 13) |
| 55–69 | +78.8% (n=16) *infeasible* | +85.1% (n=218, 9) | +72.7% (n=122, 7) |
| <55 | +138.7% (n=2) *infeasible* | +113.9% (n=2) *infeasible* | +125.6% (n=44, 3) |
| *no lease restriction (leasehold both sides)* | *+40.1% (n=115)* | *+50.0% (n=347)* | *+44.1% (n=355)* |

**Monotone in all three segments.** That is the signature the pre-registration named as
confirming a lease effect; a flat gradient would have falsified the premise.

Share of the gap attributable to lease, measured against the leasehold-only baseline in the last
row: OCR 39%, RCR 32%, CCR 21%. **These are superseded** — see *The paired test* below, which
holds district and project fixed and puts the lease effect at 26% / 11% / 8%. The difference is
composition, not lease.

Note that baseline carefully. It is leasehold on **both** sides, because every lease bucket is
leasehold-only, and anchoring the gradient to a pool that also contained freehold would divide by
the wrong denominator. It is therefore **not** test A, which matches tenure on both sides and
includes freehold new sales. The two differ by 2–3pp here, and conflating them is a mistake I made
in the first draft of this record.

### Freehold control

Freehold new sales against freehold resale: CCR +41.4% (n=189), OCR +52.1% (n=58),
RCR +55.9% (n=129). Higher than the 85+ leasehold read in every segment, which is consistent
with freehold resale stock being older on average than 85+ leasehold stock — the control behaves
as a control should rather than replicating the primary.

## Guards, and what they caught

| Guard | Setting | Outcome |
|---|---|---|
| Per-cell comparators | `MIN_CELL_N` = 5 | binding; drops thin district-quarter-band cells |
| Per-segment floor | `MIN_SEGMENT_N` = 20 | **fired 3×** — 55–69 CCR (n=16), <55 CCR (n=2), <55 OCR (n=2) reported infeasible, not published |
| Self-contamination | project excluded from its own pool | verified by mutation |
| Tenure match | both sides | verified by mutation; was untested until the mutation sweep found it |
| District census | count printed, warns below 20 | **added after this run's predecessor reported districts=1** |

Every guard was verified **by making it fail**, not by watching it pass. The mutation sweep is
the reason the tenure match has a fixture at all, and two mutations that first read as dead
guards were bad mutations — the runner now asserts an anchor is unique before applying it.

## The paired test — and a correction to this record's own attribution

Added 2026-08-09 after the CCR district caveat was run down properly. **It changes the headline
attribution, and not in our favour.**

Going from the unrestricted baseline to the 85+ bucket moves two things at once: the comparator's
lease, and *which observations survive the cell floor*. CCR keeps 3 of its 6 districts, RCR 9 of
14, OCR 9 of 15. So the segment-level fall cannot be read as the lease effect — part of it is
composition. Nothing at segment level can separate them.

The paired test can. It keeps only the new-sale observations that clear the floor in **both**
pools and differences them, so district, quarter, size band and project are identical on each
side and cancel exactly.

| Segment | Segment-level fall | **Paired (lease alone)** | Lease as share of the gap | n |
|---|---:|---:|---:|---:|
| CCR | 8.3pp | **3.0pp** | 8% | 69 |
| RCR | 13.9pp | **4.3pp** | 11% | 245 |
| OCR | 19.7pp | **11.8pp** | 26% | 277 |

**Roughly half to two-thirds of what this record attributed to lease was composition.** The
earlier figures — OCR 39%, RCR 32%, CCR 21% — are superseded by 26% / 11% / 8%. The mechanism is
visible in the baselines: restricted to the shared observations, the RCR baseline falls from
+44.1% to +37.5%, so 6.6pp of its apparent lease effect was simply which homes survived.

What survives unchanged:

- **The lease-matched level.** +31.8 / +30.3 / +30.2% is the gap against 85+ leasehold resale and
  is unaffected — it is a direct comparison, not a difference of two.
- **The convergence finding**, which is the publishable result and is if anything strengthened:
  the three segments sit within 1.6pp of each other on the lease-matched basis.
- **The monotone gradient**, which is a within-comparison shape.

What does not survive is the sentence "roughly a third of the headline gap is vintage". On the
only estimator that controls for composition it is about a tenth in RCR and a quarter in OCR.

### Risk 1 is now closed by design rather than caveated

The CCR three-district caveat was the reason for this test. It no longer needs a caveat about
district mix, because the paired estimator holds district fixed by construction. What remains is
plain sample size — n=69 across 3 districts — which is a precision statement, not a bias one.

## Risk 1 of the pre-registration — thin cells wearing the clothes of a finding

The 85+ restriction costs districts, and the loss is reported rather than assumed away:

- **CCR keeps 3 districts**, losing D01 and D02. On a five-district segment that is material, and
  the CCR primary should be read as indicative rather than as a segment estimate.
- OCR keeps 9 (loses D25, D26); RCR keeps 9 (loses D01, D02, D04, D20).
- The stop condition fired where it should: nothing below n=20 is published.

## Risk 3 — location drift, measured

Comparator median distance to MRT, by bucket: **85+ = 550 m**, 70–84 = 314 m, 55–69 = 440 m,
<55 = 348 m.

The drift is real and it runs **against** the pre-registered worry rather than with it. The
concern was that recent, transit-oriented land release would put 85+ stock closer to stations and
so make it dear, flattering the lease-matched gap. The opposite holds: the 85+ comparators sit
**furthest** from MRT, which makes them cheaper, which makes the lease-matched gap **larger** than
a distance-matched one would be. So +30% is if anything an over-estimate of the newness premium,
not an under-estimate. Distance is not controlled for, only reported.

## The ceiling on the claim

Stated in the pre-registration and restated here because it is the headline error waiting to be
made. Stock with 85+ years remaining is also newer, better specified and more likely near
amenity, because recent land release is what has long leases. **Matching on lease partly matches
on the newness being priced.** This bounds the blend; it does not decompose it. The true newness
premium is **no larger than** ~30%. It is not equal to it.

## What must change downstream

1. **`reviews/2026-08-01_launch-vs-resale.md`** — its entry-gap result is void. Its flagship
   finding (test B infeasible on free URA data) is unaffected: that conclusion rests on coverage
   counting, not on the comparator pool.
2. **`theenoughpoint.com/new-launch-or-resale-who-picked-the-dates/`** — "34% to 83% more per
   square foot" is void. Corrected range is **+42% to +52%**, and the segment order reverses. That
   article's convergence claim is void too and reverses direction: it says the spread between
   cheapest and dearest segment ran ~63pp in 2021 and ~34pp by 2025, i.e. narrowing. Corrected, the
   spread is **4.2pp in 2021 widening to 12.9pp in 2025**.
3. **`theenoughpoint.com/price-a-new-launch-before-the-price-list/`** — "median +62.1%" is void;
   corrected **+46.9%** on n=483 (the article also cites n=547, itself from the broken run). The article already qualifies it as not lease-matched and points at this
   study, so the qualification stands and the number changes.
4. The venture's benchmark sentence becomes two numbers, as pre-registered: unrestricted +44.1%
   RCR, lease-matched +30.2% RCR, with the difference named as **vintage, not premium**.

## Relation to prior work

Extends `reviews/2026-08-01_launch-vs-resale.md` test A, exactly as that record invited: it named
the vintage blend as the thing it could not separate. It separates it, and in doing so found that
the record's own numbers were computed on a broken key. Adjacent:
`reviews/2026-08-08_land-to-launch-multiple.md` (the land-cost leg, itself corrected 2026-08-09).

## Caveats

- Project-level $psf. No unit identity, so no repeat sales and no per-buyer return.
- Floor, stack and condition uncontrolled; `floorRange` is too coarse to use.
- Lease measured from the current year, matching `fetch_data.py::_lease_left`. Conservative: it
  can only move a comparator out of the 85+ bucket, never into it.
- One regime — a ~5-year window spanning one rate path, the 2023 ABSD step and the Jul-2025 SSD
  change. A period estimate, not a law.
- Distance to MRT is reported, not controlled.
- CCR primary rests on 3 districts. Indicative only.
