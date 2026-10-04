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

## Correction note, 2026-10-04 — duplicate records in the feed: checked, this record is not affected

Appended 2026-10-04 (Sunday). Nothing above is rewritten.

**What prompted the check.** A separate study of landed houses on the same URA feed found that
`PMI_Resi_Transaction` serves one landed caveat as two or three records identical on every field,
and that removing them reproduces URA's published landed counts. The question for this record was
whether the 105,599 condominium and apartment transactions it rests on carried the same artefact,
which would have overstated every n above by about a fifth and could have moved the medians.

**What was measured.** `scripts/ura_duplicate_census.py`, run in CI on 2026-10-04 (runs
37200377892 and 37200900931) on the feed as served that day, contract months 2021-09 to 2026-09.
An identical record is one that agrees with an earlier record on the project's name and street and
on every field URA puts on the transaction.

| Category | Records | Identical records beyond the first | Rate |
|---|---:|---:|---:|
| Landed houses (terrace, semi-detached, detached) | 10,989 | 2,329 | 21.2%, in pairs and triples only |
| Condominium / apartment, resale | 60,329 | 318 | 0.5% |
| Condominium / apartment, sub-sale | 4,994 | 268 | 5.4% |
| Condominium / apartment, new sale | 38,243 | 3,779 | 9.9%, in groups of up to thirteen |

The identical condominium records are distinct sales, not the landed artefact. URA's
developer-sales feed counts units sold per project from developers' returns, independently of
caveats. For the 45 selling projects whose first new-sale caveat falls inside the window, the raw
new-sale caveat count equals units sold, 16,216 against 15,986 (1.014), while removing the
identical records would have cut it to 14,222 (0.89). Mirror-image units sold at one list price
in one floor band in one month produce identical records; a house on two or three lots produces
the landed pairs and triples.

**What changed in the code.** `scripts/fetch_data.py` and `scripts/study_launch_vs_resale.py` now
drop exact duplicate records of landed houses before anything is counted. The whole record is the
key; strata landed and every non-landed record are left as served and the identical ones are
counted. `scripts/test_dedup.py` pins both edges and runs three mutations (keep the duplicates,
widen the scope, drop a field from the key), each of which must fail the suite; CI and the weekly
refresh run it. This study reads condominiums and apartments only, so the step changes none of
its rows by construction, and the study's own self-test now asserts that.

**What moved, and what did not.** Re-run on 2026-10-04 (workflow_dispatch 37201371001; output
filed as `reviews/2026-10-04_launch-vs-resale-result_landed-dedup.json`). The feed delivered
103,566 condominium and apartment transactions and the de-duplication removed none of them
(2,329 landed records removed; 5,844 identical non-landed records left in place). The filed n of
105,599 was therefore not overstated by duplicates; the difference to 103,566 is the feed's
rolling window, which has moved since August. On the October feed the lease-matched primary reads
CCR +31.78% (n=69, 3 districts), OCR +30.30% (n=254, 9), RCR +30.35% (n=232, 9) against the filed
+31.78 / +30.30 / +30.16 (n=69 / 277 / 245); the paired lease effect 2.98 / 12.10 / 3.97pp against
2.98 / 11.80 / 4.27; the unrestricted leasehold baseline +39.89 / +53.25 / +44.62 against +40.10 /
+50.00 / +44.11; the corrected test A +41.84 / +54.10 / +47.07 (n=283 / 380 / 465) against +42.19
/ +51.99 / +46.85 (n=293 / 405 / 483); the 85+ comparators still sit 550 m from the nearest
station. Every one of those movements is window drift, and none changes a finding: the three
segments still sit within 1.5pp of each other once lease is matched, the gradient is still
monotone in all three, and the three infeasible cells are the same three. The filed figures stand
as the record of the August feed; `reviews/launch_vs_resale_result.json` is unchanged.

**What the assumed treatment would have done.** A comparison run with the removal widened to
every record (same workflow run, `reviews/2026-10-04_launch-vs-resale-result_dedup-all.json`)
discards 4,365 condominium and apartment records (103,566 to 99,201) and moves the lease-matched
primary to +32.25 / +30.16 / +30.85 and the paired effect to 3.00 / 12.22 / 3.99pp: about half a
point on the CCR and RCR medians, bought by discarding sales URA counts. It is filed for
comparison and is not the record.
