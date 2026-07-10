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
   liquidity buffer is there. The module shows the interest-rate spread, a net-worth projection under
   all-cash vs max-loan-invest-the-rest, and the forced-seller buffer (months of instalments covered).
3. **Type — HDB vs condo vs landed** — a profile-aware scorecard across entry quantum, liquidity,
   appreciation track record and outlook, gross yield, leverage eligibility, restrictions and
   inflation-tracking.
4. **Where — segment & land bids** — CCR/RCR/OCR/landed/HDB on price ($psf), gross yield, 2026 momentum,
   and **recent GLS land bids** ($psf per plot ratio + bidder count). Land bids are the forward input the
   brief asked for: a competitive winning bid sets a floor under nearby future launch and resale prices
   (`launch psf ≈ land psf ppr × ~1.8–2.0`). The $1.2–1.5m brief is mapped to the segments/districts it
   actually fits.

## Data sources

All dashboard data is built from **primary public sources**, deliberately independent of the licensed
broker research that informed the framework (see IP firewall below).

- **Regulatory & loan constants** (`data/rules.json`) — MAS / MoneySense (TDSR 55% @ 4% floor, MSR 30%,
  LTV 75/45/35 + the age-65 tenure cliff, tenure caps), IRAS (ABSD, BSD). Verified in force July 2026.
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

| Feed | Source | Access | State |
|---|---|---|---|
| URA PPI (All Residential) | data.gov.sg `d_97f8a2e9...` | Open API, no auth | **live** |
| URA PPI by segment (CCR/RCR/OCR) | data.gov.sg `d_f65e490a...` | Open API | **live** (official q/q momentum) |
| HDB Resale Price Index | data.gov.sg `d_14f63e59...` | Open API | **live** |
| HDB resale transactions → median $/psf | data.gov.sg `d_8b84c4ee...` (235k rows) | Open API | **live** (latest month) |
| GLS tender awards (land $psf ppr + bids) | URA Past-Sale-Sites `.xlsx` | Scrape page for href → download | **live** |
| URA private transactions → official segment $psf | URA Data Service `PMI_Resi_Transaction` | Free daily token | **gated** on `URA_ACCESS_KEY` (skips cleanly) |
| 3M compounded SORA / package rates | MAS API portal / aggregators | Key / no feed | **curated** (SORA one line in `rules.json`) |

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
├── scripts/
│   ├── fetch_data.py      # pull live public feeds → data/live.json
│   └── pipeline.py        # merge live over baseline, inline into template.html → docs/index.html
├── .github/workflows/
│   └── refresh.yml        # weekly: fetch_data + pipeline, commit the rebuilt page
├── docs/index.html        # BUILT — deployable GitHub Pages output (data inlined)
└── README.md
```

Refresh + build: `python scripts/fetch_data.py && python scripts/pipeline.py`.
Build only (uses last `live.json`): `python scripts/pipeline.py`.
Local dev: `npx serve .` (source, fetch-fallback to the curated baseline) or `npx serve docs` (built).

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
   formulae at the stress floor; a bank's actual assessment (income recognition, variable-income haircuts,
   guarantor rules, CPF usage limits) will differ. Confirm with a banker/broker before committing.

## Status

Built and **published** 2026-07-10 (Personal, public, `etf-starter-sg` style) at
https://phuazz.github.io/sg-property-decision/ and added to the phuazz.github.io hub. Four modules live;
loan-engine maths verified in-browser on both the LTV-bound and MSR-bound paths; live data wired
(data.gov.sg indices + segment momentum + HDB medians, URA GLS land bids) with a weekly refresh Action;
official segment $psf is gated on a free URA Data Service key. The licensed broker PDFs stay private in
OneDrive (IP firewall).

_Last updated: 2026-07-10._
