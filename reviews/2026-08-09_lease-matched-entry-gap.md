# Lease-matched entry gap — how much of the new-launch premium is newness, and how much is lease?

- Run: 2026-08-09 (Sun) · `scripts/study_launch_vs_resale.py::test_a2_lease_matched`, live in CI
  (workflow_dispatch run 31293427363, `Study — new launch vs resale`)
- Design: **pre-registered 2026-08-08 before any data was pulled** —
  `reviews/2026-08-08_lease-matched-entry-gap_PREREG.md`. Followed without amendment.
- Data: URA `PMI_Resi_Transaction`, condo/apartment, 105,599 transactions, 28 districts.
- Output: `reviews/launch_vs_resale_result.json` → `test_a2_lease_matched`

## Verdict

**Two findings. The second one invalidates the first study's headline and two published pages.**

**1. The new-build premium is roughly the same everywhere once lease is matched.** Restrict the
resale comparator to leasehold with 85+ years remaining and all three segments converge on about
**+30%**: CCR +31.8%, OCR +30.3%, RCR +30.2%. The apparent segment spread in the unmatched gap
(+34.0 / +48.5 / +43.2) is substantially **which vintage of stock each segment happens to hold**,
not a segment-specific premium. That is the publishable result.

**2. Every comparator pool in the prior study was national, not district.** In
`PMI_Resi_Transaction` the district field sits on the transaction; the harness read it off the
project, where it does not exist. Every row carried `district=None`, so the pools keyed
`(district, quarter, band)` merged all 28 districts into one. What the study called "the
contemporaneous district resale median" was a **national** median within size band and tenure.
The 2026-08-01 entry-gap figures are void, and so is the `+62.1%` quoted on two live pages.

## The correction, in numbers

| Segment | Filed 2026-08-01 (VOID) | Corrected, same test | Change |
|---|---:|---:|---:|
| CCR | +82.7% | **+34.0%** (n=125) | −48.7pp |
| RCR | +62.1% | **+43.2%** (n=371) | −18.9pp |
| OCR | +34.4% | **+48.5%** (n=368) | +14.1pp |

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
| *unmatched (test A)* | *+34.0% (n=125)* | *+48.5% (n=368)* | *+43.2% (n=371)* |

**Monotone in all three segments.** That is the signature the pre-registration named as
confirming a lease effect; a flat gradient would have falsified the premise.

Share of the unmatched gap attributable to lease, on these numbers: **OCR 38%, RCR 30%, CCR 6%.**
CCR barely moves because its resale stock is already long-lease or freehold.

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
   square foot" is void. Corrected range is +34.0% to +48.5%, and the segment ORDER reverses.
3. **`theenoughpoint.com/price-a-new-launch-before-the-price-list/`** — "median +62.1%" is void;
   corrected +43.2%. The article already qualifies it as not lease-matched and points at this
   study, so the qualification stands and the number changes.
4. The venture's benchmark sentence becomes two numbers, as pre-registered: unmatched +43.2% RCR,
   lease-matched +30.2% RCR, with the difference named as **vintage, not premium**.

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
