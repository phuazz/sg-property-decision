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
| 2.83× | Zyon Grand | RCR | Zion Road (Parcel A) | 2024-04-16 | 1,202 | 3,400 | 89.8% |

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

### Open item: what `medianPrice` actually measures

This record and the dashboard both label the launch side an **asking price**. That may be wrong.
URA publishes `medianPrice` inside `PMI_Resi_Developer_Sales`, a transactions dataset, alongside
`soldToDate` and `unitsAvail`, which suggests it is the median of units *sold* in the reference
month rather than an asking price for available stock. Against that, Nava Grove's figure moved
from 2,770 to 2,686 while its `soldToDate` did not change at all, which no reading explains
cleanly and may indicate an upstream revision.

Neither label is safe to rely on until it is checked against URA's own data dictionary. It does
not change the multiple, but it changes what the multiple *means* — a transacted median is
stronger evidence than an asking price, and the caveat below currently claims the weaker one
without having established it.

## What the multiple is not

All four of these are stated on the page, because each is a way to misread the figure.

1. **Not a launch-day price, and not a settled one.** It uses each project's median for the most
   recent reference month — a handful of units, sometimes one. Developers raise prices as a
   project sells through, so the multiple drifts up with take-up, and it also moves with which
   units happened to transact that month.
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
- Asking price, not transacted price, on the launch side — **unverified**, and possibly the
  reverse. See the open item under *Stability of the launch side*.
- One regime: awards spanning 2022–2024 sit across a single rate path and the 2023 ABSD step.
- The deflation uses the all-residential PPI, not a segment index, so a CCR site is deflated by a
  national number.
