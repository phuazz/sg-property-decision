# Property Decision · Singapore

A home-buying decision tool for Singapore: **should you buy HDB, condo or landed — and if you buy,
how much to borrow versus pay in cash, and where.** Private educational dashboard (vault dashboard
convention, `template.html` → `pipeline.py` → `docs/index.html`). **Not financial advice.**

Built for a specific brief — a 42-year-old who needs a home soon, budget S$1.2–1.5m, 2- or 3-bedroom
condo, wants good location, good liquidity, and enough cash to cover 2–3 years of instalments so as
never to be a forced seller — but generalised so any profile can be entered.

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

### Live-pull upgrade path (documented, not yet wired)

The snapshot can be refreshed live later; the sources are mapped and endpoint-verified:

| Feed | Source | Access |
|---|---|---|
| HDB resale transactions | data.gov.sg `d_8b84c4ee58e3cfc0ece0d773c8ca6abc` | Open CKAN API, no auth (235k rows to 2026-07) |
| HDB flat rentals | data.gov.sg `d_c9f57187485a850908655db0e8cfe651` | Open API, block-level monthly |
| URA private transactions / rentals | URA Data Service `PMI_Resi_Transaction` / `PMI_Resi_Rental` | Free daily token (register for AccessKey); Tue/Fri + 15th refresh |
| GLS tender awards | URA Past-Sale-Sites `.xlsx` (439 sites 1993→) | Bulk download, scrape page for current href; EC/HDB-agent sites scrape HDB |
| URA PPI / HDB RPI | data.gov.sg `d_97f8a2e9...` / `d_14f63e59...` | Open API |
| 3M compounded SORA | MAS domestic-interest-rates page | Daily CSV/scrape (or MAS API-portal key) |
| Mortgage package rates | aggregators / bank pages | No API — stays curated |

REALIS ($1,960/yr or $87/day) is the only paid escape hatch, adding unit-level addresses, exact dates
and pre-2020 history; the free stack covers ~90% of the analytical value for a personal tool.

## Architecture (vault dashboard convention)

```
sg-property-decision/
├── template.html          # source, styled per C:\dev\design.md (fetch-fallback to data/ for standalone dev)
├── data/
│   ├── rules.json         # regulatory + loan-engine constants (sourced, dated)
│   └── market.json        # indices, segment $psf/yields, quantum, GLS tenders, EC policy, the brief
├── scripts/
│   └── pipeline.py        # inline data into template.html → docs/index.html
├── docs/index.html        # BUILT — deployable output (data inlined)
└── README.md
```

Build: `python scripts/pipeline.py`. Local dev: `npx serve .` (source, fetch-fallback) or `npx serve docs` (built).

## IP firewall

The three broker notes that informed the framework (DBS Singapore Residential 2026 outlook; Goldman EC-policy
note; Macquarie interest-rates note) are **licensed, exclusive-use research** — the Goldman note explicitly
prohibits redistribution and use as AI input. They are filed **privately in OneDrive**
(`OneDrive\Main\sg-property-decision\research\`), never committed here, and their proprietary content
(target prices, RNAV calls, house framing) never appears in this repo. Only underlying **public facts**
(URA GLS results, the PPI, SORA) are used, sourced directly from the primary publisher. Same discipline as
`etf-starter-sg` and `event-studies`.

## Three ways this could mislead (read before trusting a number)

1. **Curated snapshot, not live.** Prices, yields and rates are a July-2026 snapshot; a fast-moving rate or
   a new cooling measure dates it. Rates and indices carry an `asof`; re-run before relying on the numbers.
2. **Segment medians hide dispersion.** $psf and yield are segment aggregates (several portal-sourced); a
   specific project/district/floor/lease can differ materially. The tool guides *where to look*, not *which unit*.
3. **The loan engine is an illustration of the rules, not an approval.** It applies the published TDSR/MSR/LTV
   formulae at the stress floor; a bank's actual assessment (income recognition, variable-income haircuts,
   guarantor rules, CPF usage limits) will differ. Confirm with a banker/broker before committing.

## Status

Scaffolded 2026-07-10 (Personal). Data layer complete and verified; dashboard build in progress.
Private repo (gitignored at the vault root like the other lab repos). A stripped, generalised educational
snapshot could be published to the hub later, the way `etf-starter-sg` was — decision deferred to the owner.

_Last updated: 2026-07-10._
