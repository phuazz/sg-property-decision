# Property Decision · Singapore

A home-buying decision tool for Singapore: **should you buy HDB, condo or landed — and if you buy,
how much to borrow versus pay in cash, and where.** Public educational dashboard (vault dashboard
convention, `template.html` → `pipeline.py` → `docs/index.html`, deploys to `phuazz.github.io`).
**Not financial advice.**

It defaults to a worked example — a 42-year-old buying a ~S$1.35m suburban condo, who wants good
location, good liquidity, and enough cash to cover 2–3 years of instalments so as never to be a forced
seller — but any age, income, budget, property type and buyer profile can be entered.

## The decision framework (four modules)

1. **Affordability & loan** — the gate. Enter age, income, cash/CPF, existing debt, price, property
   type and citizenship; the engine returns max loan tenure (and the age-65 LTV cliff), max loan under
   LTV **and** TDSR (and MSR for HDB/EC), the monthly instalment at the 4% stress floor **and** at the
   live package rate, and the full upfront cash bill (downpayment split, BSD, ABSD). This is where the
   "42 means a shorter loan" point becomes a number: at 42 full 75% LTV caps tenure at 23 years.
2. **Buy vs rent · cash vs mortgage** — the debate. With 3-month SORA near 1% and packages ~1.3–1.7%,
   the mortgage rate sits **below** both property's long-run inflation-plus-real return and a balanced
   portfolio's expected return, so borrowing and keeping cash invested wins on expected value — *if* the
   liquidity buffer is there. The module shows the interest-rate spread (carry net of running costs), a
   year-one own-vs-rent decomposition (rent avoided, interest, maintenance + tax, returns forgone on the
   upfront, expected appreciation), prepay-vs-invest compounding, and the forced-seller buffer measured
   three ways (package rate, stress rate, including running costs) — plus the SSD exit lock (16/12/8/4%
   within 4 years of purchase).
3. **Type — HDB vs condo vs landed** — a profile-aware scorecard across entry quantum, liquidity,
   appreciation track record and outlook, gross yield, leverage eligibility, restrictions and
   inflation-tracking.
4. **Where — segment & land bids** — CCR/RCR/OCR/landed/HDB on price ($psf), gross yield, 2026 momentum,
   and **recent GLS land bids** ($psf per plot ratio + bidder count). Land bids are the forward input the
   brief asked for: a competitive winning bid sets a floor under nearby future launch and resale prices
   (`launch psf ≈ land psf ppr × 2.1–2.8, median 2.3` — derived weekly, see below). The $1.2–1.5m brief is mapped to the segments/districts it
   actually fits. **Unsold new-launch inventory by district** (added 2026-08-06) aggregates the URA
   developer-sales feed up to district level — projects, units launched, units unsold, cumulative % sold
   and the district's resale momentum beside it. It exists because a national "supply glut" headline says
   nothing about the district you are actually buying in, and the overhang is not evenly spread: it
   concentrates in D1/D9/D23/D21, while five districts (D4, D8, D13, D14, D20) have no active launch in
   the file at all. Three limits are stated on the card: a district showing nothing means *no active
   launch in this month's file*, not zero unsold homes; % sold is cumulative since launch, not a rate,
   and the feed carries no launch date; and resale listings are not counted.

## Data sources

All dashboard data is built from **primary public sources**, deliberately independent of the licensed
broker research that informed the framework (see IP firewall below).

- **Regulatory & loan constants** (`data/rules.json`) — MAS / MoneySense (TDSR 55% and MSR 30% at the
  higher of the 4% floor or the actual rate; LTV 75/45/35 + the age-65 tenure cliff; tenure caps — an
  EC from a developer follows the private 35y cap per MAS Notice 632, with the >30y reduced-LTV cliff
  and a note that many banks cap EC tenure at 30y in practice; HDB concessionary loan 75% / no minimum
  cash / 3% floor / 25y-or-age-65; 30% variable-income haircut), IRAS (ABSD, BSD, and SSD 16/12/8/4%
  within 4 years wef 4 Jul 2025). Verified in force July 2026.
- **Market snapshot** (`data/market.json`) — URA PPI + rental index and HDB RPI (levels + quarterly path),
  segment $psf and gross yields, 2-bed quantum by segment, the 2026 GLS tender table, and the 8 May 2026
  EC policy change. Every figure carries a source; portal aggregations and computed/flash values are flagged.
- **Rates** — 3-month compounded SORA 1.12% (MAS, 8 Jul 2026); package rates ~1.3–1.7% fixed / ~1.4–2.1%
  floating (aggregators; broker-promo, curated — no public feed exists for package rates).

### Live data (wired)

`scripts/fetch_data.py` refreshes `data/live.json`, which `pipeline.py` overlays on the curated
`market.json` (the baseline stands if `live.json` is absent, so `npx serve .` still works). A GitHub
Action (`.github/workflows/refresh.yml`) re-runs it weekly and commits the rebuilt page, so the LIVE
pill and the numbers stay current without manual runs.

Failures are visible, not silent: a feed that fails at refresh turns the pill amber (`LIVE · partial`,
hover lists the feeds; the footer repeats them) while curated baseline values stand for it, each figure
keeps its own as-of label, and if **every** feed fails `fetch_data.py` exits non-zero and keeps the
previous `live.json` so the page never claims a fresh fetch it did not get. A fetch older than 14 days
flips the pill to `LIVE · stale (Nd)`.

| Feed | Source | Access | State |
|---|---|---|---|
| URA PPI (All Residential) | data.gov.sg `d_97f8a2e9...` | Open API, no auth | **live** |
| URA PPI by segment (CCR/RCR/OCR) | data.gov.sg `d_f65e490a...` | Open API | **live** (official q/q momentum) |
| HDB Resale Price Index | data.gov.sg `d_14f63e59...` | Open API | **live** |
| HDB resale transactions → median $/psf | data.gov.sg `d_8b84c4ee...` (235k rows) | Open API | **live** (latest month) |
| GLS tender awards (land $psf ppr + bids) | URA Past-Sale-Sites `.xlsx` | Scrape page for href → download | **live** |
| URA private transactions → official segment $psf | URA Data Service `PMI_Resi_Transaction` | Free daily token | **gated** on `URA_ACCESS_KEY` (skips cleanly) |
| 3M compounded SORA / package rates | MAS API portal / aggregators | Key / no feed | **curated** (SORA one line in `rules.json`) |
| Land bid → launch price multiple | the two rows above, joined | Derived in `fetch_data.land_to_launch` | **live** where the URA key is set, else the last good value |

To light up official segment $psf: register for a free URA Data Service AccessKey
(`https://eservice.ura.gov.sg/maps/api/reg.html`) and set it as the `URA_ACCESS_KEY` env var / repo
secret. REALIS ($1,960/yr or $87/day) is the paid escape hatch for unit-level addresses, exact dates and
pre-2020 history; the free stack covers ~90% of the analytical value.

## Architecture (vault dashboard convention)

```
sg-property-decision/
├── template.html          # source, styled per C:\dev\design.md (fetch-fallback to data/ for standalone dev)
├── data/
│   ├── rules.json         # regulatory + loan-engine constants (sourced, dated)
│   ├── market.json        # curated baseline: indices, segment $psf/yields, quantum, GLS, EC policy, example
│   └── live.json          # BUILT by fetch_data.py — data.gov.sg + URA GLS overlay (gitignored? no: committed by CI)
├── engine/engine.js       # loan engine, extracted; kept bit-identical to the copy in template.html
├── scripts/
│   ├── fetch_data.py      # pull live public feeds → data/live.json
│   ├── pipeline.py        # merge live over baseline, inline into template.html → docs/index.html
│   ├── test_engine_parity.js   # engine/engine.js == the engine inlined in template.html
│   └── test_lease_labels.js    # lease labels, tenure buckets, sort order, and the live rows
├── .github/workflows/
│   ├── ci.yml             # every push/PR: both tests + the build-drift check
│   └── refresh.yml        # weekly: tests, fetch_data + pipeline, commit the rebuilt page
├── docs/index.html        # BUILT — deployable GitHub Pages output (data inlined)
└── README.md
```

Refresh + build: `python scripts/fetch_data.py && python scripts/pipeline.py`.
Build only (uses last `live.json`): `python scripts/pipeline.py`.
Local dev: `npx serve .` (source, fetch-fallback to the curated baseline) or `npx serve docs` (built).

### Tests

Plain Node, no dependencies, both finish in seconds. Each slices its subject out of `template.html`
at run time rather than duplicating it, so neither can drift away from what the page actually runs.

```
node scripts/test_engine_parity.js    # engine parity, ~1.04m cases across the full input grid
node scripts/test_lease_labels.js     # lease labels + tenure buckets, and every live project row
```

`test_engine_parity.js` asserts `engine/engine.js` is bit-identical to the engine still inlined in
`template.html`, so the extraction stays provably a no-op. `test_lease_labels.js` pins both sides of
every label cut (a 999-year lease is not a 9,999-year one — ROXY SQUARE has 9,968 years left), asserts
the tenure filter can never contradict the Lease column, and fails if a refresh brings in a lease the
label rules cannot name.

**Both run on every push and PR** (`ci.yml`), alongside a check that `docs/index.html` still matches a
rebuild — so a `template.html` edit must carry its rebuild in the same commit. The weekly refresh runs
them too: engine parity before the fetch, lease labels after it and *before* the commit, so wrong data
never reaches the live page (stale-but-correct data still does, by design).

## IP firewall

The three broker notes that informed the framework (DBS Singapore Residential 2026 outlook; Goldman EC-policy
note; Macquarie interest-rates note) are **licensed, exclusive-use research** — the Goldman note explicitly
prohibits redistribution and use as AI input. They are filed **privately in OneDrive**
(`OneDrive\Main\sg-property-decision\research\`), never committed here, and their proprietary content
(target prices, RNAV calls, house framing) never appears in this repo. Only underlying **public facts**
(URA GLS results, the PPI, SORA) are used, sourced directly from the primary publisher. Same discipline as
`etf-starter-sg` and `event-studies`.

## Three ways this could mislead (read before trusting a number)

1. **Partly live, partly curated.** Indices, segment momentum, GLS land bids and HDB medians refresh live
   (weekly Action); SORA and package rates are curated, and a new cooling measure would date the rules until
   `rules.json` is updated. The LIVE pill shows the data date; rules carry their own `asof`.
2. **Segment medians hide dispersion.** $psf and yield are segment aggregates (several portal-sourced); a
   specific project/district/floor/lease can differ materially. The tool guides *where to look*, not *which unit*.
3. **The loan engine is an illustration of the rules, not an approval.** It applies the published TDSR/MSR/LTV
   formulae at the higher of the floor or your rate, with the 30% variable-income haircut; a bank's actual
   assessment (income recognition, income-weighted average age on joint loans, guarantor rules, CPF usage
   limits, valuation vs price) will differ. Confirm with a banker/broker before committing.

## Status

Built and **published** 2026-07-10 (Personal, public, `etf-starter-sg` style) at
https://phuazz.github.io/sg-property-decision/ and added to the phuazz.github.io hub. Four modules live;
loan-engine maths verified in-browser on both the LTV-bound and MSR-bound paths; live data wired
(data.gov.sg indices + segment momentum + HDB medians, URA GLS land bids) with a weekly refresh Action;
official segment $psf is gated on a free URA Data Service key. The licensed broker PDFs stay private in
OneDrive (IP firewall).

**Post-publication review + fix pass (2026-07-10, same day):** severity-ranked review memo, then patches —
stress test corrected to the higher of the floor or the actual rate (was fixed 4%); EC tenure resolved
against the MAS Notice 632 text (21 Aug 2025 revision): the 30y cap covers "HDB Flat" only, so ECs
follow the private 35y cap with the >30y reduced-LTV cliff — the widely quoted "30y max" is bank
practice, shown as a note; HDB
concessionary-loan mode added (75%, no minimum cash, 3% floor, 25y-or-age-65); SSD (4 Jul 2025 schedule)
encoded in `rules.json` and surfaced as the "exit lock"; 30% variable-income haircut and optional
remaining-lease warnings (CPF-to-95 pro-rating, bank lease thresholds); buffer restated at the stress
rate and including estimated running costs; year-one own-vs-rent card (the appreciation slider now
drives it); live-fetch failures made visible (amber partial/stale pill, footer note, CI all-fail guard);
GLS notes flag the mix-unadjusted average, two-sided supply effect and planning-area segment
approximation; segment "read" labels made momentum-aware; landing-page hook copy and the $1.4m
affordability note corrected. Engine re-verified against an independent Python recomputation
(14 cases, exact agreement).

**Unsold-inventory card (2026-08-06).** Added to the Where module, computed client-side from the
existing `new_launches` feed — no pipeline or fetch change. Verified against the standing
pre-publication check (`C:\dev\MOBILE_CHECK.md`): static pass, and rendered at a real 390px viewport
with the table scrolling inside its own container, no page-level horizontal scroll and nothing under
11px. The card was prompted by a live error caught in a related brief — a national supply figure had
been applied to a single district without checking that district, which reversed the conclusion.

**Test + CI guard layer (2026-08-08).** The weekly refresh commits and pushes to a live page with
nobody watching, so it now runs the tests before it publishes rather than beside it. The same two
tests plus a build-drift check run on every push and PR. Guards were verified by making them fail,
not just by watching them pass: injecting a raw tenure string and a negative remaining term into two
live rows fails the run with both projects named, and an unrebuilt `template.html` edit fails the
drift check. Prompted by a real defect the tests now pin — ROXY SQUARE, a 9,999-year lease, was
labelled `999-yr` because every span above 200 years collapsed to one label.

**Land-bid multiple re-derived (2026-08-08).** The tool had been telling readers a winning land bid
becomes a launch price at roughly `× 1.8–2.0`. Re-derived from public data, the real figure is
materially higher. Pairing each currently-selling project (URA developer sales) with the state-land
site its developer won — matched on the registered tenderer entity, which in Singapore is a
single-purpose vehicle named for the plot — gives **eight pairs at 2.13× to 2.83×, median 2.31×**.
Not one sits inside the old band. The stale rule was quoted in three places (the explainer, the
"Est. launch $psf" column, and this README), so the column had been publishing low estimates for
every site in the table, not just narrating a wrong rule.

What the figure is not, all of which is now stated on the page: it uses each project's *current*
median asking price, not its launch-day price; it is not a developer margin, because the sites were
awarded 24–44 months ago and the multiple carries the market's own move over that period (restating
each price at the URA PPI level of its award quarter pulls the band to 1.93×–2.66×, median 2.11×);
all eight are state land, and a collective sale prices differently; and it predicts nothing about
demand — the two highest multiples are 90% and 38% sold.

It now recomputes weekly in `fetch_data.land_to_launch` rather than sitting in prose waiting to go
stale again, which per the vault rule means it needs a guard layer: awards are windowed to six years,
an entity that won more than one site in the window is dropped as unattributable, pairs outside a
1.5–3.5× sanity band are dropped and *listed* rather than silently trimmed, and the whole result is
withheld (leaving the last good value in place) below five pairs or on an implausible median. Each
guard was verified by making it fail. The window is load-bearing: without it a perennial corporate
entity rather than an SPV matched a 2010 award at $321 psf ppr and produced a spurious 6.4× pair.

_Last updated: 2026-08-08._
