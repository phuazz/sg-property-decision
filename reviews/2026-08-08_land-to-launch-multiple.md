# Land bid to launch price — what multiple does a GLS win actually become?

- Run: 2026-08-08 (Sat) · `scripts/fetch_data.py::land_to_launch`, verified live in CI
  (workflow_dispatch run 31238970168, `Refresh live data`, 04:15 UTC)
- Data: URA Past-Sale-Sites `.xlsx` (residential awards) × URA `PMI_Resi_Developer_Sales`
  (refPeriod 0626, 50 currently-selling projects). Both public; the developer-sales side is
  gated on `URA_ACCESS_KEY`, which stays in GitHub.
- Result: `data/live.json` → `land_to_launch` (pairs emitted for audit); curated fallback in
  `data/market.json` → `gls.land_to_launch`
- Prompted by a correction: the tool had been publishing a stale rule of thumb.

## Correction, 2026-08-08 (same day, after publication)

**The multiple was published with more precision than the data supports.** The launch side of
every pair is URA's `medianPrice` for a *single reference month* (0626), and across all eight
pairs that month carries **24 transactions in total** — six down to one apiece, and one pair with
none. Recomputing the identical method on the previous month's snapshot (0526) gives a raw median
of **2.46×**, not 2.31×, and a deflated median of **2.27×**, not 2.11×.

What survives unchanged: **no pair falls inside the old 1.75–2.05 band on either month's basis**,
raw. The correction to the stale rule is robust and the direction is not in doubt.

What was overstated: the third significant figure, and the strength of the deflated claim. On the
published June basis **four of the eight deflated pairs sit inside the old band** (three on the
May basis), and the deflated median clears the band's top by only 3%. "The old rule was too low
even before the market moved" holds on the median and should not be read as holding pair by pair.

See *Stability of the launch side* below. The article that cites this record carries the same
correction.

## Correction, 2026-08-16 (Sun): both ends of the published range sit on hybrid sites

**The denominator is not always a residential land rate, and this record never said so.** The
multiple divides a launch price charged on condominium strata by a land rate struck on the whole
site's gross floor area. Where part of that GFA is *not* sellable strata, the two sides are not
measuring the same thing and the multiple reads **high**. Two of the eight pairs are in that
position, and they are **the two ends of the range this page publishes**.

### Zyon Grand — a quarter of the plot was never for sale

URA awarded **Zion Road (Parcel A)** as one of two pilot sites for long-stay Serviced Apartments
(SA2). The award release states the condition outright: *"A minimum 20,000 m² of GFA is to be set
aside for Long-Stay Serviced Apartments (SA2) use"*, against a maximum permissible GFA of
**85,557 m²** — so **at least 23.4%** of the floor area behind the $1,202 psf ppr land rate.
URA's SA2 circular settles what that floor area is: SA2 is *"expected to be owned en-bloc and
operated by a single operator"*, so **none of it is ever sold as strata**. CDL's own launch
release describes the built form — a 36-storey serviced-apartment tower plus a retail galleria with
F&B, a supermarket and a childcare centre — alongside the 706-unit condominium.

The numerator is the 706-unit condominium alone. The denominator is blended across all of it.
Serviced-apartment floor area is worth less per square foot to a developer than sellable strata, so
the condominium's true land cost is **above** $1,202 and **2.83× is overstated**.

This record earlier judged the strata-to-GFA shift unquantifiable because it *"needs the plans"*.
That was right about the DC22-09 harmonisation and **wrong to be carried over to this**: the
*minimum* set-aside is published. What is not published is the split as built, which is why the
correction below is a flag and an illustration, not a restatement.

| f = SA2 floor area's worth per sq ft, as a fraction of condo strata | implied residential land $psf | × on $3,400 | × on $3,050 |
|---|---:|---:|---:|
| 1.00 *(no discount — the published basis)* | 1,202 | 2.83× | 2.54× |
| 0.80 | 1,261 | 2.70× | 2.42× |
| 0.60 | 1,326 | 2.56× | 2.30× |
| 0.40 | 1,398 | 2.43× | 2.18× |

**Illustrative arithmetic on the published minimum, not an estimate.** `f` is not observable from
free public data and no value of it is asserted here. What the table shows is that the direction is
one-way and the magnitude is not small: on any discount at all, Zyon Grand stops being the top of
the range. On the launch basis with a mid-range discount it lands around 2.3×, which is the middle
of the pack. **The Sen at 2.78× — a plain residential plot — is the more defensible ceiling.**

### The other seven, checked

| Pair | Site | URA "Type of Development Allowed" | Non-strata GFA | Cleared against |
|---|---|---|---|---|
| Upperhouse | Orchard Boulevard | Residential **with Commercial at 1st Storey** | commercial, quantum not published | pr24-07 |
| Nava Grove | Pine Grove (Parcel B) | Residential | none | pr23-42, workbook |
| 8@BT | Bukit Timah Link | Residential | none | workbook, SA2 pilot list |
| Norwood Grand | Champions Way | Residential | none | workbook, SA2 pilot list |
| Promenade Peak | Zion Road (Parcel B) | Residential | none | pr24-40 |
| River Green | River Valley Green (Parcel A) | Residential | none | pr24-33 |
| The Sen | De Souza Avenue | Residential | none | pr24-40 |
| Zyon Grand | Zion Road (Parcel A) | Residential **with Commercial at 1st Storey** | commercial **+ SA2 ≥ 20,000 m² (≥23.4%)** | pr24-15, pr23-48, DC23-11 |

Two of eight. The SA2 pilot is a closed list of **two parcels** — Zion Road (Parcel A) and Upper
Thomson Road (Parcel A), per pr23-48 — and only the first is in this sample, which is what lets the
remaining six be cleared on the workbook's use column rather than one release at a time. Bukit
Timah Link and Champions Way were cleared on those two signals alone; the other four were checked
against their award releases directly.

**Note the workbook does not know about SA2.** Zion Road (Parcel A) reads there as ordinary
"Residential with Commercial at 1st Storey" — identical to Orchard Boulevard, where the
non-residential share is a strip of shops rather than a quarter of the plot. The workbook column
alone would have flagged the site but understated it by an order of magnitude, so the set-aside is
carried as a curated entry keyed to the site, with its source.

### What this does to the published figures

Nothing is corrected. The flag is emitted per pair and the restricted subsets alongside, exactly as
`gfa_basis` is:

| Basis | n | Median | Range |
|---|---:|---:|---|
| All pairs (as published) | 8 | 2.31× | 2.13×–2.83× |
| Strata-only | 6 | **2.31×** | **2.20×–2.78×** |
| Post-harmonisation (page headline) | 7 | 2.33× | 2.13×–2.83× |
| Post-harmonisation **and** strata-only | 5 | **2.33×** | **2.20×–2.78×** |

**The median does not move at all; the range pulls in at both ends.** That is the Kassia shape
again — a pair that looks fine in isolation, leaves the median alone and damages the *range*, which
is the figure the page publishes and the figure the "Est. launch $psf" column scales.

**The column keeps the all-pairs-post-harmonisation basis, and the page now says why.** Switching
it to the double-restricted subset would buy a median that does not change and a range 0.05×–0.07×
tighter, at the cost of running the estimate column off **n = 5** — exactly the withhold floor, so
one project finishing its sales would take the column out entirely. Month-to-month noise on these
endpoints is around 0.3× (see *Stability of the launch side*), which is five times the tightening
on offer. The honest fix is the caveat, not the narrower sample. The page now names both flagged
projects, states the ≥23% set-aside, gives the strata-only band and tells the reader to anchor on
the middle rather than the ends.

Three of the ten sites the estimate column prices are themselves hybrid — Bayshore Drive
(Commercial and Residential), Dunearn Road and Dover Drive (Residential with Commercial at 1st
Storey). Applying a blended-basis multiple to a blended-basis land rate is the more nearly
like-for-like operation, so this is an argument for flagging both sides rather than for purifying
the sample.

### The reference month is not the launch, and the endpoint is being read as if it were

Stated separately because it compounds with the above and is a different error. Zyon Grand's 2.83×
uses its **current reference-month median — 5 units in 06-2026 at $3,400 psf**. The launch was
priced materially lower: CDL's release of **26 October 2025 (Sun)** records **590 of 706 units
(84%) sold at an average selling price of S$3,050 psf**. On the launch basis the multiple is
**2.54×, not 2.83×**.

This record already says the multiple is *"not a launch-day price"*, and that remains the first
item under *What the multiple is not*. It is not enough. The caveat is prose while **2.83× is the
published number**, and a range endpoint gets read as the thing it is nearest to — a launch price.
The two corrections push the same way: reference-month rather than launch, and blended rather than
residential land. Both inflate, and they inflate the same pair, which is the one setting the top of
the published range.

### Guards

| Guard | Verified by making it fail | Load-bearing? |
|---|---|---|
| Prohibition clauses must not flag | Removing the negation handling makes "Condominium (Service Apartment will not be allowed)" flag as serviced-apartments | **Yes** — 3 sites in the workbook name a use in order to forbid it |
| Nested-bracket exclusions must not swallow real uses | `[^)]*` lets `(… Commercial … (Excluding Hospital))` strip the commercial component; `[^()]*` does not | **Yes** — caught before publication |
| Workbook use column present | Renaming it makes Upperhouse silently lose its flag; the run now warns instead | **Yes** — the one failure that looks like a clean sample |
| Curated set-aside key still resolves | Renaming the key drops Zyon Grand's SA2 component and its share; the run warns | **Yes** |
| Subsets withhold below `LTL_MIN_PAIRS` | Raising the floor to 6 withholds `harmonised_strata_only` (n=5); to 7 withholds `strata_only` (n=6) | **Yes** — the strata-only sets are thin by construction |
| Overlay carries new feed fields to the page | An unknown field in the feed now emits a build warning | **Yes** — see below |

**The overlay guard exists because this failure had already happened twice.** `pipeline.py` copies
*named* fields from the feed onto the curated baseline, so a new field is invisible to the template
until it is named there — and nothing errors. It swallowed `harmonised_only` once (the page quietly
kept serving the wider all-pairs median) and it swallowed `strata_only` and
`harmonised_strata_only` on the first build of this correction. Caught by reading the rendered
page, not the source, which is the third time in this project's records that the artefact and the
inputs disagreed. The build now warns on any feed field that is neither carried nor explicitly
listed as not-for-page.

### Unresolved

The **unit split is not confirmed**. Secondary portals give Zion Road (Parcel A) as 735
conventional units plus 435–500 SA units; URA's pr23-48 gives roughly **535 SA units and 1,275
conventional across both pilot sites combined**, which does not reconcile with 435–500 on this
parcel alone. No URA source found states the per-parcel unit split, so it is **not used anywhere in
this correction** — the arithmetic above rests on the published GFA set-aside, which is primary.
Flagged rather than resolved.

### Sources for this correction

All primary, all public.

- [pr24-15](https://www.ura.gov.sg/Corporate/Media-Room/Media-Releases/pr24-15) — Zion Road
  (Parcel A) award, 16 Apr 2024: tenderer, $1,106,888,000 at $12,937.43/m² GFA, site 15,277.9 m²,
  max GFA 85,557 m², and the SA2 minimum 20,000 m² set-aside.
- [pr23-48](https://www.ura.gov.sg/Corporate/Media-Room/Media-Releases/pr23-48) — the SA2 pilot,
  naming Zion Road (Parcel A) and Upper Thomson Road (Parcel A) as the only two sites.
- [DC23-11](https://www.ura.gov.sg/Corporate/Guidelines/Circulars/dc23-11) — SA2 guidelines: three-
  month minimum stay, and SA2 *"expected to be owned en-bloc and operated by a single operator"*.
- [pr24-07](https://www.ura.gov.sg/Corporate/Media-Room/Media-Releases/pr24-07) (Orchard
  Boulevard), [pr24-33](https://www.ura.gov.sg/Corporate/Media-Room/Media-Releases/pr24-33) (River
  Valley Green Parcel A), [pr24-40](https://www.ura.gov.sg/Corporate/Media-Room/Media-Releases/pr24-40)
  (De Souza Avenue, Zion Road Parcel B) — award particulars and use conditions.
- [CDL news release, 26 Oct 2025](https://www.cdl.com.sg/newsroom/84-of-units-at-zyon-grand-sold-on-launch-weekend)
  — *"590 out of 706 units (84%) sold at an average selling price of S$3,050 psf"*, and the
  36-storey long-stay serviced-apartment tower alongside the retail galleria.
- URA Past-Sale-Sites workbook — the `Type of Development Allowed` column, already the source for
  the land side of every pair.

## Verdict

**The published rule was materially too low, and it was wrong in the table as well as in the
prose.** The tool told readers a winning land bid becomes a launch price at roughly
`× 1.8–2.0`. On the eight state-land sites that can be paired with a project now selling on
them, the observed range is **2.13× to 2.83×, median 2.31×**. Not one pair falls inside the old
band.

Net of market drift the gap narrows but does not close: restating each launch price at the URA
PPI level of its own award quarter gives **1.93× to 2.66×, median 2.11×**. So the old rule was
too low even before the market moved, and roughly half the headline gap is drift the original
rule could not have anticipated. "Stale" is the fair description; "wrong when written" would
overstate it by about half.

## Method

The multiple is a project's current median new-sale $psf over the $psf per plot ratio its
developer paid for the site. The join is on the registered tenderer entity name, normalised by
upper-casing, stripping punctuation and dropping corporate-form tokens
(PTE/LTD/LIMITED/PRIVATE/AND/GROUP/HOLDINGS/NO), with JV strings split on `and` / `/` / `&`.

This works because Singapore developers tender through a single-purpose vehicle named for the
plot. All eight matches are exact SPV matches — Winchamp Investment to River Valley Green
(Parcel A), Valerian Residential to Zion Road (Parcel B), and so on — not fuzzy corporate-parent
matches. That is strong evidence the project sits on that plot, but **URA does not publish the
link**, so the pairing remains a derived inference and every pair is emitted for audit.

### Coverage

| | count |
|---|---|
| residential awards in the workbook | 214 |
| …awarded within the six-year window | 63 |
| currently-selling projects (developer sales) | 50 |
| …no GLS site matched in window (collective sale, older award, or name mismatch) | 42 |
| …matched more than one site (unattributable) | 0 |
| **qualifying pairs** | **8** |

The binding constraint is that most currently-selling projects sit on collective-sale land or on
GLS awards older than the window, neither of which this method can price.

## Result

| Multiple | Project | Seg | Site | Awarded | Land $psf ppr | Launch $psf | Sold |
|---|---|---|---|---|---|---|---|
| 2.13× | Upperhouse at Orchard Boulevard | CCR | Orchard Boulevard | 2024-02-21 | 1,617 | 3,437 | 81.4% |
| 2.20× | Nava Grove | RCR | Pine Grove (Parcel B) | 2023-11-15 | 1,223 | 2,686 | 99.6% |
| 2.25× | 8@BT | RCR | Bukit Timah Link | 2022-11-15 | 1,343 | 3,017 | 70.3% |
| 2.29× | Norwood Grand | OCR | Champions Way | 2023-09-18 | 904 | 2,072 | 90.5% |
| 2.33× | Promenade Peak | RCR | Zion Road (Parcel B) | 2024-08-07 | 1,304 | 3,037 | 71.3% |
| 2.35× | River Green | CCR | River Valley Green (Parcel A) | 2024-06-27 | 1,325 | 3,111 | 93.9% |
| 2.78× | The Sen | RCR | De Souza Avenue | 2024-08-07 | 841 | 2,341 | 38.3% |
| 2.83× | Zyon Grand ⚑ | RCR | Zion Road (Parcel A) | 2024-04-16 | 1,202 | 3,400 | 89.8% |

⚑ **hybrid site — the land $psf ppr is blended across floor area that is not all sellable strata,
so the multiple is overstated.** Upperhouse (2.13×, top row) carries the same flag. Both are the
ends of this range. See *Correction, 2026-08-16*.

Median 2.31×. Awards span 2022-11-15 to 2024-08-07, which is 24 to 44 months before the run date.

### Deflated to each award's own quarter

The raw multiple embeds however much the whole market moved while the project was being built.
Restating each launch price at the URA PPI (All Residential) level of its award quarter:

| Project | Award quarter | PPI then | Drift to 2026-Q2 | Raw | Deflated |
|---|---|---|---|---|---|
| 8@BT | 2022-Q4 | 188.6 | +16.3% | 2.25× | **1.93×** |
| Nava Grove | 2023-Q4 | 201.5 | +8.9% | 2.20× | 2.02× |
| Norwood Grand | 2023-Q3 | 196.0 | +11.9% | 2.29× | 2.05× |
| Upperhouse | 2024-Q1 | 204.3 | +7.4% | 2.13× | 1.98× |
| River Green | 2024-Q2 | 206.1 | +6.5% | 2.35× | 2.21× |
| Zyon Grand | 2024-Q2 | 206.1 | +6.5% | 2.83× | **2.66×** |
| Promenade Peak | 2024-Q3 | 204.7 | +7.2% | 2.33× | 2.17× |
| The Sen | 2024-Q3 | 204.7 | +7.2% | 2.78× | 2.59× |

Median 2.11×. A flat −6.5% haircut on the raw median (the two-year PPI move) gives 2.16×, which
is the wrong number: the older awards saw far more drift than the recent ones, and 8@BT alone
saw +16.3%.

## Stability of the launch side

The month-to-month movement, from the two feed snapshots either side of the run:

| Project | Units sold in Jun | May $psf | Jun $psf | May × | Jun × | Swing |
|---|---|---|---|---|---|---|
| Upperhouse at Orchard Boulevard | 5 | 3,439 | 3,437 | 2.13× | 2.13× | −0.00 |
| Nava Grove | 0 | 2,770 | 2,686 | 2.26× | 2.20× | −0.07 |
| 8@BT | 1 | 2,813 | 3,017 | 2.09× | 2.25× | +0.15 |
| Norwood Grand | 3 | 2,072 | 2,072 | 2.29× | 2.29× | +0.00 |
| Promenade Peak | 4 | 3,438 | 3,037 | 2.64× | 2.33× | **−0.31** |
| River Green | 1 | 3,482 | 3,111 | 2.63× | 2.35× | **−0.28** |
| The Sen | 6 | 2,410 | 2,341 | 2.87× | 2.78× | −0.08 |
| Zyon Grand | 4 | 3,361 | 3,400 | 2.80× | 2.83× | +0.03 |

Raw median 2.46× → 2.31×; range 2.09×–2.87× → 2.13×–2.83×. Deflated median 2.27× → 2.11×.

Two pairs move about 0.3× in a single month on one and four transactions. The endpoints and the
median are therefore month-dependent at the second decimal, and the caveat "one project entering
or leaving will move the endpoints" understates it: **one project selling four units** moves them.

The right way to state the finding is as a range with a stated basis — "on 2026-06 data, roughly
2.1× to 2.9×, median in the low-to-mid 2s" — not as 2.31×.

### Gross floor area is not strata area, and the definition moved mid-sample

The two sides of this ratio are measured on different bases and always have been: the land rate is
priced on **gross floor area**, the launch price is charged on **strata area**. That is tolerable
only while the mapping between them is stable, and it stopped being stable.

URA's [circular DC22-09](https://www.ura.gov.sg/Corporate/Guidelines/Circulars/dc22-09) harmonised
the floor-area definitions across URA, SLA, BCA and SCDF for **development applications submitted
on or after 2023-06-01**. All strata areas now count towards GFA, including air-conditioner ledges,
and voids are excluded from strata area. A given GFA entitlement therefore yields less sellable
strata than it did, which pushes this multiple **up** for reasons that have nothing to do with the
market.

Classifying by award date — a proxy, see below — the sample is 1 pre and 7 post:

| Basis | n | Median | Range |
|---|---:|---:|---|
| Post-harmonisation awards | 7 | **2.33×** | 2.13×–2.83× |
| All pairs (as published) | 8 | 2.31× | 2.13×–2.83× |

The effect on this sample is about **1% on the median**, because it is nearly all on one side and
so is the site the article applies it to (Thomson View, awarded 2024-11-25). It would not be small
on a set weighted the other way, and the dashboard applies this multiple to *every* GLS site in its
table, including older awards — which is where it matters.

**Award date is a proxy, and an imperfect one.** The rule keys off the development-application
submission date, which URA does not publish. A site awarded before the cutover could have submitted
its application after it and fall under the new rules. So `fetch_data.py` now emits a `gfa_basis`
tag per pair and a separate `harmonised_only` summary rather than correcting anything — the
classification is a flag for the consumer, not a claim about which regime a project is in.

The size of the strata-to-GFA shift itself is **not quantified here**. It cannot be measured from
free public data: it needs the plans.

### RESOLVED 2026-08-09: `medianPrice` is transacted, not asking

Settled at URA's own source, and against the label this record used.

URA's [Developers' Sales e-Service](https://eservice.ura.gov.sg/property-market-information/pmiResidentialDeveloperSalesPrice)
states that **"the prices and number of units sold in the month are based on Options to Purchase
issued by developers to purchasers"**, and the
[glossary](https://www.ura.gov.sg/Corporate/Property/Property-Data/definition-of-data-terms)
defines the threshold: a unit is sold once the developer gives the purchaser the option to
purchase against a booking fee.

So `medianPrice` is the median of units **sold** in the reference month. Calling it an asking
price was wrong — and wrong in the direction that *understated* the evidence, because a
transacted median is stronger than a quote. The feed note, the dashboard copy and the article
caveat are corrected.

The same documentation shows the payload carries **`soldInMonth`**, which this feed was not
reading. The thinness of each monthly median no longer has to be inferred by differencing
`soldToDate` across weekly snapshots:

| Pair | Multiple | Units behind the median |
|---|---:|---:|
| Upperhouse at Orchard Boulevard | 2.13× | 3 |
| Nava Grove | 2.20× | 1 |
| 8@BT | 2.25× | 1 |
| Norwood Grand | 2.29× | 3 |
| Promenade Peak | 2.33× | 4 |
| River Green | 2.35× | 1 |
| The Sen | 2.78× | 6 |
| Zyon Grand | 2.83× | 5 |
| **All eight** | | **24** |

The aggregate published on 2026-08-09 — 24 transactions across the eight, from six down to one
apiece — is **exactly right**. Three individual counts were not: Upperhouse was 5 not 3, Zyon
Grand 4 not 5, and Nava Grove 0 not 1.

**That last one closes the other open question.** This record flagged as unexplained that Nava
Grove's median moved from 2,770 to 2,686 while its `soldToDate` did not change. It did change —
by one unit — and the weekly snapshot comparison missed it. There is no upstream revision to
explain: a one-unit month simply moves a one-unit median. Inferring a count by differencing a
cumulative field across snapshots is the weaker method, and it is now retired in favour of the
published one.

## What the multiple is not

All four of these are stated on the page, because each is a way to misread the figure.

1. **Not a launch-day price, and not a settled one.** It uses each project's median for the most
   recent reference month — a handful of units, sometimes one. Developers raise prices as a
   project sells through, so the multiple drifts up with take-up, and it also moves with which
   units happened to transact that month. The gap is not decorative: Zyon Grand launched at an
   average **$3,050 psf** (CDL, 26 Oct 2025) and its 06-2026 reference month reads **$3,400**, so
   the multiple is **2.54× on the launch basis against the 2.83× published here**.
2. **Not a developer margin.** It carries the market's own move over 24 to 44 months. The
   deflated column is the closer proxy for what construction, financing and margin cost.
3. **State land only.** A collective sale prices differently, and 42 of the 50 selling projects
   could not be paired for exactly that kind of reason.
4. **Says nothing about demand.** The two richest multiples are Zyon Grand at 89.8% sold and The
   Sen at 38.3%. A high multiple is a pricing decision, not evidence it cleared.

## The outlier that shaped the guard design

A purely mechanical entity match returns a ninth pair: **Kassia at 6.37×**, from a **2010** award
at $321 psf ppr. It matched through Tripartite Developers, which is not a single-purpose vehicle
but a long-lived entity that has won sites over decades.

Nothing about that pair looks wrong in isolation — a real developer, a real award, a real project
— and the median barely moves when it is included (2.31× → 2.33×). What it destroys is the
*range*, which is the figure the page publishes: 2.13×–2.83× becomes 2.13×–6.37×.

This is the same failure shape as the 2026-08-01 study in this project, where every "launch"
quarter turned out to be the data-window start. Both times the output looked plausible and was
caught only by reading the per-row detail.

## Guards

The feed recomputes weekly in CI, so per the vault rule on unattended agents it ships with a
guard layer. Each was verified by making it fail, not by watching it pass.

| Guard | Setting | Verified by | Load-bearing? |
|---|---|---|---|
| Award window | 6 years | Widening to 40y readmits Kassia | **Yes** — the only guard that catches the 2010 award |
| Ambiguous entity | drop any entity winning >1 site in window | 12 entities dropped this run | **No** — costs and adds zero pairs; insurance, currently dormant |
| Outlier band | drop pairs outside 1.5–3.5×, and *list* them | At 40y, Kassia is dropped and recorded | **Yes** — holds the range even if the window is widened |
| Minimum pairs | withhold below n=5 | Truncated input returns `ok:false` | untriggered |
| Sane median | withhold outside 1.5–3.5× | Squeezing the band to (1.5, 2.0) returns `ok:false` | untriggered |

On withholding, the key is unset so the previous good value carries forward and the page falls
back to the `market.json` baseline rather than showing a broken number. Outliers are dropped
*and recorded* in `dropped_outliers` rather than silently trimmed.

**One gap worth naming.** On a withheld first run there is no previous value to carry forward, so
`land_to_launch` would simply be absent, the workflow's staleness gate would not fire, and the
page would quietly serve the baseline. That is the correct outcome for readers but the one
failure mode that does not announce itself.

## Live verification

Manual `workflow_dispatch` on 2026-08-08 04:15 UTC, the first execution on the real path:

```
ok   land_to_launch (n=8, median 2.31x)
```

All twelve upstream feeds returned data, `_meta.errors` empty, nothing carried forward,
`dropped_outliers` empty. The page took the live overlay — flag `derived from n=8 public pairs
(live)` — rather than the baseline, confirming the pipeline path. A scheduled routine checks the
first unattended run on 2026-08-10.

## What this means for the dashboard

The stale rule was in three places, and only one of them was prose. `data/market.json` carried
`factor_range: [1.75, 2.05]`, and the **"Est. launch $psf" column** computed from it — so the
table had been publishing low estimates for every site, not merely narrating a wrong rule. On
Peck Hay Road the column read $3,264–$3,823 against a corrected ~$4,308 ($3,972–$5,278).

Every figure in the copy is now read from the JSON rather than written into the sentence, so the
prose cannot drift from the data again. The column shows a median-based central estimate above
the full observed range.

## Relation to prior work

Builds on `reviews/2026-08-01_launch-vs-resale.md` (same project). That study found the
launch-versus-resale *growth* test infeasible on free URA data, because a launch's first
meaningful resale arrives four or more years out and the free window is 5.25 years. It closed by
naming land cost as a plausible driver it had not checked.

This study is feasible precisely where that one was not: **both sides are published
contemporaneously.** A land award and a current asking price need no unit identity and no waiting
for a resale event. It does not answer the growth question — it prices the entry level, not the
return — but it removes land cost from that study's untested list.

## Caveats

- **n = 8, and each pair is itself thin.** Too small to trim, so the full observed range is
  published rather than an interquartile band. One project entering or leaving moves the endpoints
  visibly — and so does one project selling four units, since the launch side is a single month's
  median. See *Stability of the launch side*.
- The SPV name match is a **derived inference**, not a published URA link. Strong, and auditable
  through the emitted pairs, but not authoritative.
- Project-level $psf throughout; no unit identity, so this is never a realised per-buyer figure.
  Same limitation as the 2026-08-01 study.
- **Transacted price on the launch side**, not an asking price — resolved 2026-08-09 against URA's
  own documentation; see the section above. It remains a single month, on one to six units per
  pair.
- One regime: awards spanning 2022–2024 sit across a single rate path and the 2023 ABSD step.
- The deflation uses the all-residential PPI, not a segment index, so a CCR site is deflated by a
  national number.
- **GFA basis is flagged, not corrected**, and classified by award date rather than by the
  development-application date the rule actually keys off. See the section above.
- **Two of the eight sites are hybrid**, and they are the two ends of the published range. Their
  land rate is blended across floor area that is not all sellable strata, so both multiples read
  high by an amount the public data cannot size. Flagged per pair (`hybrid_site`), not corrected;
  the strata-only subsets are emitted alongside. See *Correction, 2026-08-16*.
- **The launch side is a reference-month median, not the launch price.** Where a developer has
  published a launch ASP the two differ materially — 2.54× against 2.83× on Zyon Grand. The feed
  cannot read launch ASPs, so the record carries this and the page states the basis.
