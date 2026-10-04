# Building-age decay — how fast does a new launch's premium erode, and when does it hit zero?

- Run: 2026-08-10 (Mon) · `scripts/study_launch_vs_resale.py::test_c_age_decay`, live in CI
  (workflow_dispatch run 31360128362, `Study — new launch vs resale`)
- Design: **pre-registered 2026-08-10 before the confirmatory pull** —
  `reviews/2026-08-10_building-age-decay_PREREG.md`. Followed without amendment. Not blind: the
  exploratory pass and the prediction it generated are disclosed in that document.
- Data: URA `PMI_Resi_Transaction`, condo/apartment. 37,722 resales cleared the guards, 25 districts.
- Output: `reviews/launch_vs_resale_result.json` → `test_c_age_decay`

## Verdict

**The decay is real and large. The pre-registered prediction of its shape was wrong on two of
three counts, and is recorded as wrong.**

| Prediction, stated 2026-08-10 | Outcome |
|---|---|
| Monotone decreasing in age | **FAILED** — 11–15 (+0.1%) and 16–20 (+1.4%) invert |
| Zero crossing between age 11 and 15 | **FAILED** — measured at **18.8** |
| Age 6–10 premium in +8% to +18% | **HELD** — +9.9% |

The exploratory pass on `live.json` had put the crossing at 11–15 and the 6–10 bucket at +13.5%.
Both moved once the comparator became a median of transactions rather than of project medians,
size entered the cell key rather than being stratified afterwards, and age was measured at the
transaction date rather than today. **This is the entire reason the confirmatory test was
specified differently from the pass that motivated it.**

## Result — the gradient

Each resale against the median of its own `(district, quarter, size band)` cell, that cell pooling
all building ages, own project excluded. Age at the transaction date.

| Age | Premium | p25 – p75 | n | Districts | Median sqft |
|---|---:|---:|---:|---:|---:|
| 0–5 | **+19.8%** | +12.5 to +29.1 | 187 | 12 | 732 |
| 6–10 | **+9.9%** | +0.7 to +21.0 | 10,774 | 24 | 743 |
| 11–15 | **+0.1%** | −8.3 to +10.3 | 12,072 | 24 | 915 |
| 16–20 | **+1.4%** | −8.8 to +12.7 | 4,190 | 25 | 1,216 |
| 21–30 | **−12.4%** | −21.4 to −2.2 | 7,582 | 25 | 1,206 |
| 31+ | **−25.2%** | −34.8 to −13.0 | 2,917 | 24 | 1,324 |

Entry anchor — new sales through the same all-age denominator: **+45.2%** (n=34,623, 25 districts,
p25 +32.6 / p75 +57.5). Consistent with test A2's corrected entry gap of +42.2 / +46.9 / +52.0 by
segment, which is a useful independent check since the two use different comparator constructions.

**Read the shape, not the smoothness.** A building sheds roughly 35 points of relative value
between its first five years and its third decade. But the middle of that path is a **plateau**,
not a slide: 11–15 and 16–20 are indistinguishable, and the 16–20 bucket is nominally *higher*.

### Why the plateau is probably an artefact, and why that is not fixed

The size-band cell key has four bands and the top one is **open-ended above 1,150 sqft**. The
16–20 bucket's median unit is 1,216 sqft — inside that open band, and benchmarked partly against
stock far larger than itself. Larger units carry a lower $psf, so the comparator is dragged down
and the bucket is flattered. The 21–30 bucket has almost the same median size (1,206 sqft) and
does *not* pop up, so this is a partial explanation rather than a complete one.

The honest statement is that the crossing point sits somewhere in the **15–20** range and this
design cannot place it more precisely than that. The published article says "about nineteen years"
and pairs it with "flat from eleven to twenty", which is the width the evidence supports.

## Risk 3 of the pre-registration — is this ageing, or is it cohort?

The guard: compute the same gradient per calendar year. A stable shape across years makes a pure
cohort story harder to sustain.

| Year | 0–5 | 6–10 | 11–15 | 16–20 | 21–30 | 31+ |
|---|---:|---:|---:|---:|---:|---:|
| 2021 | +19.6% | +4.6% | +2.4% | −4.1% | −14.4% | −28.9% |
| 2022 | +20.2% | +6.6% | +1.2% | −1.2% | −13.3% | −23.3% |
| 2023 | +18.0% | +9.4% | +0.7% | +3.8% | −11.7% | −24.7% |
| 2024 | · | +13.3% | −1.1% | +2.4% | −11.3% | −23.9% |
| 2025 | · | +12.8% | −1.3% | +2.0% | −12.1% | −28.3% |
| 2026 | · | +13.7% | +1.1% | +0.6% | −11.3% | −23.7% |

**The old end is stable and the young end is not.** 21–30 sits between −11.3% and −14.4% in every
one of six years, and 31+ between −23.3% and −28.9%. That stability is what the guard was for, and
it passes.

But the 6–10 bucket runs **+4.6% in 2021 to +13.7% in 2026** — it has roughly tripled. The premium
on young stock has been widening through the window, which means **the decay curve is not
stationary** and a single cross-sectional gradient describes 2026 better than it describes 2021.
This was not anticipated in the pre-registration and is the most interesting thing in the run.

Consequence for anyone using this forward: the exit comparable a buyer will face depends on what
the young premium is *at exit*, not what it is today, and that quantity has been moving.

## Guards, and what they caught

| Guard | Setting | Outcome |
|---|---|---|
| Per-cell comparators | `MIN_CELL_N` = 5 | binding; 1,208 resale rows dropped for a thin cell |
| Per-bucket transactions | 30 | not binding on the live run; every bucket cleared |
| Per-bucket districts | 5 | not binding on the live run; 12–25 per bucket |
| Standard lease only | term 95–110 | 22,054 rows dropped — freehold and 999-year |
| Self-contamination | project excluded from its own cell | verified by mutation |
| Age at transaction date | not today | verified by mutation |
| New sales out of the denominator | resale-only cells | verified by mutation |

**8 of 8 guards verified by making them fail.** The sweep earned its keep twice. It found the
per-bucket transaction floor and the per-cell comparator floor were **untested** — every fixture
failed both stop conditions simultaneously, so deleting either left `feasible=False` and the suite
green. Both now have a fixture that isolates them. It also found that breaking the age arithmetic
**crashed** the suite instead of failing a named check, because a shifted bucket made a subscript
raise `KeyError` before the naming assertion ran; the fixtures now use `.get()`.

One of my own assertions was wrong and the suite caught it: I asserted the gradient was monotone
on a fixture of 5 transactions in 1 district, when monotonicity is assessed over feasible buckets
only and must withhold a verdict there. 100 self-tests, up from 62.

## The ceiling on the claim

- The decay is the **sum** of lease run-down, physical depreciation and design obsolescence. Test
  A2 puts the lease component alone at roughly 15% across the 85+/70–84 boundary; the remainder is
  unattributed and this design cannot attribute it.
- **Cross-sectional, not longitudinal.** A 5.25-year window cannot follow one building from 8 to
  30 years old. A building observed at 30 was built for a mid-1990s market.
- **En-bloc survivorship** removes the old cohort's redevelopment candidates. Direction genuinely
  ambiguous: en-bloc candidates sit on under-utilised land in good locations (argues the sample
  loses winners), but en-bloc speculation bids up a candidate's resale $psf beforehand (argues the
  reverse). No clean guard on free data.
- Describes **stock that remained on the market**, not the path of any individual building.
- One regime, one point in the cycle — and the by-year table shows the young end moving within it.

## What changed downstream

1. **`theenoughpoint.com/price-a-new-launch-before-the-price-list/`** — PR
   `TheEnoughPoint/theenoughpoint#40`. The hurdle no longer claims to hold "whenever you sell":
   the five-building comparator is selected at 85+ years of lease, and a fifteen-year hold puts the
   building at ~83, outside its own comparator. The caveat that called the hurdle assumption-free
   is corrected — it is free of an assumption about the *rate* of appreciation, not about *what you
   sell alongside*. The caveat that the lease comparison was "an association, not a decay curve" is
   replaced by this curve, including the failed prediction.
2. **`scripts/check_figures.py`** in the article repo now guards five decay figures against this
   study's committed result rather than `live.json`. 49 figures, up from 44.
3. **Not changed: the article's S$2,162 exit comparable.** An earlier reading of mine had it as the
   District 20 all-vintage median, which would have made the hurdle badly overstated. It is not —
   it is the median of five named young D20 buildings, already age-matched, and it reproduces
   exactly from the feed. The article's method was sound and the correction is narrower than first
   thought: the basket's median age is 13 against an exit age nearer 10, worth roughly 5 points on
   the hurdle, and that is disclosed in prose rather than restated as a new headline number.

## Relation to prior work

Extends `reviews/2026-08-09_lease-matched-entry-gap.md`, which measured the gap on day one and
explicitly declined to say what happens to it afterwards. Adjacent:
`reviews/2026-08-01_launch-vs-resale.md` (test B, infeasible, unaffected) and
`reviews/2026-08-08_land-to-launch-multiple.md` (the land-cost leg).

The unanswered question this hands on: **the young premium is widening and nothing here explains
why.** Land cost, the shrinking supply of new stock and the post-2013 shift to smaller units are
all plausible and none is tested.

## Caveats

- Project-level identity only. No unit identity, so no repeat sales and no per-buyer return.
- Floor, stack and condition uncontrolled; `floorRange` is too coarse.
- Four size bands, the top one open-ended above 1,150 sqft — the residual confound behind the
  16–20 plateau.
- The 0–5 bucket rests on 187 transactions in 12 districts. It clears both floors but is the
  thinnest row in the table and should not be leaned on.
- Distance to MRT is not controlled here (test A2 reports it for the entry gap).

## Correction note, 2026-10-04 — duplicate records in the feed: checked, this record is not affected

Appended 2026-10-04 (Sunday). Nothing above is rewritten.

**What prompted the check.** A separate study of landed houses on the same URA feed found that
`PMI_Resi_Transaction` serves one landed caveat as two or three records identical on every field.
The question for this record was whether the 37,722 resales and 34,623 new sales it rests on
carried the same artefact, which would have overstated every n above by about a fifth.

**What was measured.** The census and the developer-sales cross-check are set out in the
correction note of `reviews/2026-08-09_lease-matched-entry-gap.md` (CI runs 37200377892 and
37200900931, 2026-10-04). In short: 21.2% of landed records are identical to an earlier one, in
pairs and triples only; 0.5% of condominium and apartment resales and 9.9% of new sales are, and
the new-sale ones are distinct sales, because for the projects launched inside the window the raw
new-sale caveat count equals URA's count of units sold (16,216 against 15,986) while removing the
identical records would have cut it to 14,222.

**What changed in the code.** Exact duplicate records of landed houses are now dropped before
anything is counted, in `scripts/fetch_data.py` and in this study's loader, with the whole record
as the key, strata landed and every non-landed record left as served, a fixture, and three
mutations that must each fail the suite. This study reads condominiums and apartments only, so the
step changes none of its rows by construction.

**What moved, and what did not.** Re-run on 2026-10-04 (workflow_dispatch 37201371001; output
filed as `reviews/2026-10-04_launch-vs-resale-result_landed-dedup.json`). The de-duplication
removed no condominium or apartment record, so the filed n's were not overstated by duplicates.
The October feed clears 37,495 resales through the guards against the filed 37,722, and the
difference is the rolling window. On that feed the gradient reads +20.70% (0–5, n=192, 13
districts), +10.25% (6–10, n=10,496), −0.04% (11–15, n=12,101), +1.40% (16–20, n=4,308), −12.47%
(21–30, n=7,372), −25.30% (31+, n=3,026) against the filed +19.79 / +9.92 / +0.07 / +1.39 / −12.40
/ −25.23; the entry anchor +45.71% (n=33,293) against +45.22% (n=34,623); 21,651 rows dropped for
a non-standard lease and 1,183 for a thin cell against 22,054 and 1,208. No bucket median moved by
more than half a point, no bucket changed feasibility, the gradient is still not monotone, and the
old end is still stable year by year.

One figure did move, and it is window drift rather than correction: the interpolated zero crossing
reads 13.0 years on the October feed against the filed 18.8, because the 11–15 median moved from
+0.07% to −0.04% and the interpolation now lands between the 6–10 and 11–15 midpoints instead of
beyond the 16–20 plateau. The record above already declined to place the crossing more precisely
than a range; this re-run says the range is 11 to 20 years, not 15 to 20, and that a plateau
sitting at zero makes any single crossing figure a property of the month's sample. The 2026 row
of the by-year table also filled in (6–10 +13.1%, 11–15 +0.6%, 16–20 +0.1%, 21–30 −12.5%, 31+
−25.0%) and the 2021 0–5 cell fell below the 30-transaction floor as 2021-08 left the window. The
filed figures stand as the record of the August feed; `reviews/launch_vs_resale_result.json` is
unchanged.

**What the assumed treatment would have done.** With the removal widened to every record (same
run, `reviews/2026-10-04_launch-vs-resale-result_dedup-all.json`) the gradient medians move by at
most 0.07pp, but the entry anchor's n falls from 33,293 to 30,200 and the resales cleared from
37,495 to 37,237, by discarding sales URA counts. Filed for comparison; not the record.
