# CLAUDE.md — sg-property-decision

Layers on the vault `C:\dev\CLAUDE.md`. Context: **Personal** (a decision tool built to help friends
buy a home). Not Navigo, not CGSI.

## Non-negotiables specific to this project

- **Not financial / mortgage / tax advice.** Every surface is an educational illustration of published
  rules and public data. Keep the not-advice framing and the "verify with a banker/broker" caveats.
- **IP firewall.** The DBS / Goldman / Macquarie property notes are licensed, exclusive-use research
  (the Goldman note bars redistribution and AI-input use). They stay in
  `OneDrive\Main\sg-property-decision\research\`, never in this repo. Never put broker target prices,
  RNAV calls or proprietary framing into any file here. Use only public facts, sourced to the primary
  publisher (URA / HDB / MAS / SingStat / IRAS). Same rule as `etf-starter-sg`, `event-studies`.
- **Derived-not-vendor data.** `data/*.json` is built from public sources; every figure carries a
  `source`, and portal-aggregated / computed / flash values are `flag`ged. Do not present a flagged or
  single-source number as confident. No transcription drift — numbers on the page must match the JSON.
- **Rules are the constants.** TDSR 55% @ 4% floor, MSR 30%, LTV 75/45/35 with the >30y/>25y/age-65
  cliff, ABSD/BSD tables — all in `data/rules.json`. If a cooling measure changes, update the JSON once
  and the whole tool follows. Confirm any rule against MAS / MoneySense / IRAS before changing it.
- **Dates via a library, months indexed explicitly** (vault rule). Any tenure/age/date arithmetic uses
  a date library with month-boundary and year-boundary tests; never compute from memory.

## Architecture

Standard vault dashboard: `template.html` (source, styled per `C:\dev\design.md`) → `python scripts/pipeline.py`
→ `docs/index.html`. Work on `template.html`, never hand-edit the built `docs/index.html`. Keep the fetch
fallback so `npx serve .` works standalone in dev.

## Status / entry point

Data layer done (`rules.json`, `market.json`). Dashboard modules: Affordability & loan · Buy-vs-rent /
cash-vs-mortgage · Type (HDB/condo/landed) · Where (segment + GLS land bids). Private repo.
