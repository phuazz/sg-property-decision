# New launch versus resale — can it be tested on public data?

- Run: 2026-08-01 (Sat) · `scripts/study_launch_vs_resale.py` via the `study-launch-vs-resale`
  workflow (runs in CI so `URA_ACCESS_KEY` never leaves GitHub)
- Data: URA `PMI_Resi_Transaction`, condo/apartment, observed window **2021Q3 – 2026Q3**
- Result: `reviews/launch_vs_resale_result.json`
- Design pre-registered in the script docstring before any data was pulled.

## Verdict

**The flagship hypothesis cannot be tested on free URA data. Not "unproven" — untestable.**
A separate, weaker question (the entry gap) is answerable and is reported below.

The hypothesis under test came from three Eric Chiew videos (property-research memos
2026-07-24/27/31), which assert that good resale generally out-performs new launch, each on a
hand-picked pair of transactions. The editorial counterweight (Stacked Homes, memo 2024-08-01)
argues the same side on a distribution, but finds a statistical tie on hit-rate (91% vs 89.8%)
and disclaims significance testing.

## Why it is untestable here

A new launch's first meaningful resale arrives roughly four or more years after purchase — the
binding constraint is the later of construction (TOP, typically ~3.5 years) and the SSD lock
(16/12/8/4% within four years). The free URA window is 5.25 years. That leaves about 1.25 years
of usable launch dates, and 0.75 years after excluding launches too close to the window edge to
be identified as launches at all.

Observed coverage bears the arithmetic out exactly:

| | projects |
|---|---|
| with new-sale transactions in window | 184 |
| excluded — first new sale at the window edge (not identifiable as a launch) | 86 |
| genuinely launched in window | 98 |
| …of those, no resale has occurred yet | 94 |
| …of those, resold inside the four-year SSD lock | 4 |
| **qualifying for the test** | **0** |

Testing this properly needs roughly eight to ten years of transaction history with unit
identity. That means REALIS (S$1,960/yr), or starting an archive now and waiting. Free URA
caveats also carry no unit identity at all, so even with a longer window this design measures
project-level $psf paths, never realised per-buyer return.

## A result that was wrong, and how it was caught

The first run returned a clean-looking **−4.04%/yr** excess across 24 projects, with only 8.3%
positive — apparently strong support for the agent claim. It was an artefact and is **void**.

Every "launch" quarter in that run was 2021Q3 or 2021Q4, the first two quarters of the data
window. Avenue South Residence, Treasure at Tampines, Parc Clematis and Jadescape all launched
in 2018–19 and were merely still selling remaining units when the window opened. The code took
`min(quarter with a new sale)` as the launch quarter, which is the first quarter *visible*, not
the launch. A late-phase developer price is biased high, which biases the excess down and
manufactured the entire finding.

Worth recording because nothing about the output looked wrong: the sign was consistent, the
dispersion was tight, the segment ordering was plausible, and it agreed with the prior. It was
caught only by reading the per-project detail and noticing that all 24 launch dates were
identical to the window start.

An earlier bug was caught by the self-test before any live run: projects were included in the
district benchmark they were measured against, so a large launch dragged its own benchmark
toward itself and flattened the excess exactly where the effect matters most.

## What is answerable — the entry gap

New-sale $psf against the **contemporaneous district resale median**, same size band, same
tenure class, project excluded from its own benchmark:

| Segment | Median gap | p25 – p75 | n | Positive |
|---|---|---|---|---|
| OCR | **+34.4%** | +24.4 to +42.6 | 493 | 99.4% |
| RCR | **+62.1%** | +48.2 to +76.4 | 547 | 100% |
| CCR | **+82.7%** | +70.7 to +97.2 | 333 | 100% |

**Read this precisely.** It is *not* "how much you overpay". The district resale median mixes
every vintage, including stock thirty years old, so the gap blends the genuine new-build premium
(fit-out, warranty, facilities, no near-term capex) with a plain age-and-condition difference and
with location within the district. Notably it is far larger than the ~40% Stacked quoted, which
is itself a reason to treat it as a vintage gap rather than a premium.

What it does answer honestly is the size-versus-location trade-off: on a fixed budget, buying
new instead of existing costs roughly a third more per square foot in OCR and over half more in
RCR and CCR. That is a real constraint on what a given budget reaches, and it is computed from
primary data rather than asserted.

## What this means for the dashboard

The tool must not tell readers that resale beats new launch. We could not test it, and neither
the agent source nor the editorial source has shown it at the strength they imply.

The publishable position is stronger than the pre-registered null: **nobody can demonstrate this
from public Singapore transaction data, so treat any confident claim built on a handful of
project comparisons with suspicion.** The entry gap, by contrast, is large, segment-dependent and
measurable, and it is what a buyer actually faces on day one.

## Caveats

- Project-level $psf, never realised per-buyer return — no unit identity in the data.
- The entry gap is not size-adjusted beyond four bands, and floor mix is not controlled
  (`floorRange` is too coarse).
- One regime: 2021Q3–2026Q3 spans one rate path, the 2023 ABSD step and the July 2025 SSD change.
- The gap compares a project against a district aggregate, so location within district is
  uncontrolled.
