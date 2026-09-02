#!/usr/bin/env python3
"""Tests for fetch_data._landed_summary - the landed price bands the Start page's budget input
reads once it climbs past the condo market, and the Type tab grades landed against.

The aggregation is a pure function over URA-shaped records, so this runs with no key and no
network. It pins: type bucketing survives URA's capitalisation ('Semi-Detached House' as well
as 'Semi-detached'); strata-landed is counted but never priced; new sales are out; the 12-month
window is exact on a month boundary and across a year boundary (contractDate is 'mmyy'); a thin
type is withheld rather than published on a handful of deals; a region band needs its own
minimum sample; and the output shape template.html reads.

Usage: python scripts/test_landed_summary.py
Exit 0 = pass. Exit 1 = failure, with every failing case printed.
"""
import sys, pathlib, datetime
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import fetch_data as F

fails = []
def eq(label, got, want):
    if got != want:
        fails.append(f"{label}: got {got!r}, want {want!r}")
def ok(label, cond):
    if not cond:
        fails.append(label)

def tx(pt, mmyy, price, sale="3", area=150.0, toa="Land", tenure="Freehold"):
    """One URA-shaped transaction. area is sqm as URA gives it; 150 sqm = 1,615 sqft."""
    return {"propertyType": pt, "contractDate": mmyy, "price": str(price), "typeOfSale": sale,
            "area": str(area), "typeOfArea": toa, "tenure": tenure, "district": "15"}

def proj(seg, *txs):
    return {"project": "LANDED HOUSING DEVELOPMENT", "marketSegment": seg, "transaction": list(txs)}

# ---- type bucketing: every label URA has used, both capitalisations, and the non-landed set ----
for label, want in [
    ("Terrace", "Terrace"), ("Terrace House", "Terrace"),
    ("Semi-detached", "Semi-detached"), ("Semi-Detached House", "Semi-detached"),
    ("Detached", "Detached"), ("Detached House", "Detached"),
    ("Strata Terrace", "Strata"), ("Strata Semi-detached", "Strata"), ("Strata Detached", "Strata"),
    ("Condominium", None), ("Apartment", None), ("Executive Condominium", None), (None, None), ("", None),
]:
    eq(f"_landed_type({label!r})", F._landed_type(label), want)

# ---- the window, on a month boundary and across a year boundary ----
# Run month September 2026: a September 2025 contract is exactly 12 months back and is OUT;
# October 2025 is 11 months back and IN.
run = datetime.date(2026, 9, 2)                           # Python dates: months are 1-indexed
big = [tx("Terrace", "1025", 3_000_000 + 10_000 * i) for i in range(F.LANDED_MIN_N)]
r = F._landed_summary([proj("OCR", *big, tx("Terrace", "0925", 9_900_000))], run)
eq("month boundary: Sep-2025 excluded at a Sep-2026 run", r["by_type"]["Terrace"]["n"], F.LANDED_MIN_N)
eq("month boundary: window is 12 months", r["window_months"], 12)
eq("asof is the run month", r["asof"], "2026-09")
# Run month January 2026: January 2025 is OUT, February 2025 and December 2025 are IN.
run_jan = datetime.date(2026, 1, 15)
r = F._landed_summary([proj("OCR", tx("Detached", "0125", 20_000_000), tx("Detached", "0225", 21_000_000),
                            tx("Detached", "1225", 22_000_000))], run_jan)
eq("year boundary: Jan-2025 out, Feb-2025 and Dec-2025 in", r["by_type"]["Detached"]["n"], 2)
eq("year boundary: asof", r["asof"], "2026-01")
# An unparseable contract date is dropped, not crashed on.
r = F._landed_summary([proj("OCR", tx("Terrace", "", 3_000_000), tx("Terrace", None, 3_000_000))], run)
eq("bad contractDate dropped", r["n"], 0)

# ---- resale only; strata counted but never priced; non-landed ignored entirely ----
r = F._landed_summary([proj("RCR",
        tx("Terrace", "0826", 4_000_000, sale="1"),          # new sale: out
        tx("Terrace", "0826", 4_100_000, sale="2"),          # sub-sale: out
        tx("Terrace", "0826", 4_200_000),                    # resale: in
        tx("Strata Terrace", "0826", 2_500_000),             # strata-landed: censused, excluded
        tx("Condominium", "0826", 1_500_000))], run)
eq("resale only", r["by_type"]["Terrace"]["n"], 1)
eq("strata excluded from n", r["n"], 1)
eq("strata counted", r["n_strata_excluded"], 1)
eq("census names the strata label", r["property_type_census"].get("Strata Terrace"), 1)
ok("census ignores non-landed", "Condominium" not in r["property_type_census"])

# ---- thin types are withheld, published ones carry the p10..p90 band ----
few = [tx("Semi-detached", "0626", 5_000_000 + 100_000 * i) for i in range(F.LANDED_MIN_N - 1)]
r = F._landed_summary([proj("OCR", *few)], run)
s = r["by_type"]["Semi-detached"]
eq("thin type: n", s["n"], F.LANDED_MIN_N - 1)
eq("thin type: band withheld", s["price_p"], None)
eq("thin type: flagged", s["thin"], True)
eq("absent type: n is 0", r["by_type"]["Detached"]["n"], 0)
eq("absent type: band withheld", r["by_type"]["Detached"]["price_p"], None)
prices = [3_000_000 + 50_000 * i for i in range(25)]
r = F._landed_summary([proj("OCR", *[tx("Terrace", "0726", p) for p in prices])], run)
t = r["by_type"]["Terrace"]
eq("published band equals _pctiles of the prices", t["price_p"], F._pctiles(prices))
eq("published band is five figures", len(t["price_p"]), 5)
ok("band is non-decreasing", all(a <= b for a, b in zip(t["price_p"], t["price_p"][1:])))
eq("published: not thin", t["thin"], False)
eq("freehold share", t["fh_share"], 1.0)
eq("land size median (150 sqm)", t["land_sqft_p50"], 1615)
eq("region band on the same sample", t["by_region"]["OCR"]["n"], 25)
eq("region median", t["by_region"]["OCR"]["median_price"], round(sorted(prices)[12]))

# ---- region bands need their own minimum; strata-area records do not feed the land size ----
half = F.LANDED_MIN_N // 2
mixed = [proj("OCR", *[tx("Terrace", "0526", 3_000_000, tenure="99 yrs lease commencing from 1990", toa="Strata")
                       for _ in range(half)]),
         proj("CCR", *[tx("Terrace", "0526", 8_000_000) for _ in range(F.LANDED_MIN_N)])]
r = F._landed_summary(mixed, run)
t = r["by_type"]["Terrace"]
eq("national n pools regions", t["n"], half + F.LANDED_MIN_N)
ok("thin region withheld", "OCR" not in t["by_region"])
eq("region at the minimum is published", t["by_region"]["CCR"]["n"], F.LANDED_MIN_N)
eq("freehold share counts only freehold records", t["fh_share"], round(F.LANDED_MIN_N / (half + F.LANDED_MIN_N), 3))
eq("land size ignores strata-area records", t["land_sqft_p50"], 1615)
r = F._landed_summary([proj(None, *[tx("Terrace", "0526", 3_000_000) for _ in range(F.LANDED_MIN_N)])], run)
eq("no marketSegment: no region band, national band still published", r["by_type"]["Terrace"]["by_region"], {})
ok("no marketSegment: national band published", r["by_type"]["Terrace"]["price_p"] is not None)

# ---- bad records: a non-numeric or zero price is dropped, nothing else is ----
r = F._landed_summary([proj("OCR", tx("Terrace", "0526", "n/a"), tx("Terrace", "0526", 0),
                            tx("Terrace", "0526", 3_000_000, area="abc"))], run)
eq("bad prices dropped, bad area kept", r["by_type"]["Terrace"]["n"], 1)
eq("bad area: no land size", r["by_type"]["Terrace"]["land_sqft_p50"], None)

# ---- the shape the page reads, and the feed gate the main loop applies ----
r = F._landed_summary([], run)
for k in ("asof", "window_months", "n", "min_n_per_type", "n_strata_excluded", "by_type",
          "property_type_census", "source"):
    ok(f"output carries {k}", k in r)
eq("empty feed: n is 0", r["n"], 0)
eq("empty feed fails the data gate (so it is carried forward, not published)", F._has_data(r), False)
eq("published feed passes the data gate",
   F._has_data(F._landed_summary([proj("OCR", *big)], run)), True)
eq("landed_resale is wired as a feed", callable(getattr(F, "landed_resale", None)), True)

if fails:
    print(f"FAIL ({len(fails)}):")
    for f in fails:
        print("  - " + f)
    sys.exit(1)
print("ok landed summary: bucketing, window (month + year boundary), resale-only, strata, thin, "
      "regions, bad records, shape")
