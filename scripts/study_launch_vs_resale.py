#!/usr/bin/env python3
"""
study_launch_vs_resale.py — Does buying at new launch beat buying resale?

PRE-REGISTERED DESIGN. Read this header before reading results. The hypothesis under
test comes from property-research memos 2026-07-27 / 2026-07-31 (agent source, hand-picked
pairs) and its counterweight 2024-08-01 (Stacked Homes, distribution but a statistical tie
on hit-rate and a possible CCR-only effect).

WHAT WE CANNOT DO
    Free URA caveats (PMI_Resi_Transaction) carry no unit identity — no address, stack or
    floor number. A true repeat-sales study (buy unit X, sell unit X) is therefore
    IMPOSSIBLE on this data; it needs REALIS. Any claim of "realised return per buyer" from
    this script would be false. We measure project-level $psf paths instead.

WHAT WE TEST INSTEAD

    Test A — the launch premium at entry.
        Per project-quarter with New Sale transactions, median new-sale $psf against the
        CONTEMPORANEOUS district resale median $psf, within size band and tenure class.
        Answers: what do you pay extra, at entry, to buy new?

    Test B — is the premium earned back? (the flagship)
        For projects that launched in-window and later show resale transactions:
            entry     = project median new-sale $psf at launch quarter
            exit      = project median resale  $psf at latest quarter with enough volume
            benchmark = district resale median $psf over the SAME quarters
        Report annualised project $psf growth MINUS annualised district resale growth.
        Positive => the launch buyer beat the district. Negative => a premium paid and
        not recovered. Matched on calendar time and district, which the Stacked design is not.

PRE-REGISTERED NULL
    If the excess in Test B straddles zero with wide dispersion and no stable segment
    pattern, the finding is "this is not a rule you can lean on" — and that is the result
    we publish. It is more useful than either the agent claim or the editorial one.

THREE (FOUR) WAYS THIS COULD BE SILENTLY WRONG
    1. MIX SHIFT. A project-quarter median $psf moves with which unit sizes happened to
       transact; a quarter of small units reads as a price rise. Mitigated by computing
       within size bands and enforcing MIN_CELL_N. Never compare across size bands.
    2. SELECTION ON RESALE EXISTENCE. A project only enters Test B if somebody resold.
       SSD (16/12/8/4% within 4 years) makes early sellers non-random. Mitigated by
       reporting the share of in-window launches with zero resale volume, and by the
       MIN_HOLD_QUARTERS floor. The sample is conditioned; say so in any write-up.
    3. TENURE AND FLOOR CONFOUND. Launch inventory and resale stock differ in freehold
       share and floor mix. Mitigated by stratifying on tenure class; floor is recorded
       but NOT controlled (floorRange is coarse) — declare it as a residual confound.
    4. ONE REGIME. The URA window is ~5 years. It covers one rate path, the 2023 ABSD
       step and the Jul-2025 SSD change. A result here is a period estimate, not a law.

USAGE
    python scripts/study_launch_vs_resale.py --self-test     # no key needed
    python scripts/study_launch_vs_resale.py --run           # needs URA_ACCESS_KEY

Dates: contractDate is "MMYY". Month index and quarter index are derived with explicit
month arithmetic (Python months are 1-indexed) and covered by boundary tests in --self-test.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import statistics
import sys
from collections import defaultdict

SQM_TO_SQFT = 10.7639
MIN_CELL_N = 5           # minimum transactions before a project-quarter median is trusted
MIN_HOLD_QUARTERS = 16   # 4 years — below the SSD lock, resales are non-random
CONDO_TYPES = ("Condominium", "Apartment")
SALE_NEW, SALE_SUB, SALE_RESALE = "1", "2", "3"


# ---------------------------------------------------------------- date helpers

def month_index(mmyy: str):
    """'MMYY' -> absolute month index (year*12 + month), or None.

    Matches scripts/fetch_data.py::_midx. Months are 1-indexed. The 2000+YY convention
    means this is valid for 2000-2099 only; pre-2000 caveats would misparse.
    """
    try:
        mm, yy = int(str(mmyy)[:2]), int(str(mmyy)[2:])
    except (ValueError, TypeError):
        return None
    if not 1 <= mm <= 12 or not 0 <= yy <= 99:
        return None
    return (2000 + yy) * 12 + mm


def quarter_index(mmyy: str):
    """'MMYY' -> absolute quarter index. Q1 = Jan-Mar."""
    mi = month_index(mmyy)
    if mi is None:
        return None
    year, month = divmod(mi - 1, 12)          # month now 0-indexed
    return year * 4 + month // 3


def quarter_label(qidx: int) -> str:
    year, q = divmod(qidx, 4)
    return f"{year}Q{q + 1}"


# ---------------------------------------------------------------- classification

def size_band(sqft: float) -> int:
    """0 <600, 1 600-850, 2 850-1150, 3 >=1150 sqft. Mirrors fetch_data.py::_sizeband."""
    return 0 if sqft < 600 else 1 if sqft < 850 else 2 if sqft < 1150 else 3


def tenure_class(tenure: str) -> str:
    """'FH' for freehold/999-year, 'LH' for a dated leasehold, 'UNK' otherwise."""
    t = str(tenure or "")
    if "Freehold" in t:
        return "FH"
    m = re.search(r"(\d+)\s*yrs?\s*lease", t, re.I)
    if m:
        return "FH" if int(m.group(1)) >= 900 else "LH"
    return "UNK"


def flatten(projects: list) -> list:
    """URA payload -> flat transaction rows. Drops anything unusable rather than guessing."""
    rows = []
    for proj in projects or []:
        name = proj.get("project")
        district = proj.get("district")
        segment = proj.get("marketSegment")
        for t in proj.get("transaction", []) or []:
            if t.get("propertyType") not in CONDO_TYPES:
                continue
            qi = quarter_index(t.get("contractDate", ""))
            if qi is None:
                continue
            try:
                sqft = float(t["area"]) * SQM_TO_SQFT
                price = float(t["price"])
            except (KeyError, TypeError, ValueError):
                continue
            if sqft <= 0 or price <= 0:
                continue
            rows.append({
                "project": name,
                "district": district,
                "segment": segment,
                "quarter": qi,
                "psf": price / sqft,
                "band": size_band(sqft),
                "tenure": tenure_class(t.get("tenure")),
                "sale": str(t.get("typeOfSale", "")).strip(),
            })
    return rows


# ---------------------------------------------------------------- aggregation

def _medians(rows, keyfn, min_n=MIN_CELL_N):
    """Group rows by keyfn -> {key: (median psf, n)}, dropping cells below min_n."""
    buckets = defaultdict(list)
    for r in rows:
        buckets[keyfn(r)].append(r["psf"])
    return {k: (statistics.median(v), len(v)) for k, v in buckets.items() if len(v) >= min_n}


def test_a_launch_premium(rows) -> dict:
    """New-sale $psf vs contemporaneous district resale $psf, within size band and tenure."""
    new = _medians([r for r in rows if r["sale"] == SALE_NEW],
                   lambda r: (r["project"], r["quarter"], r["band"], r["tenure"], r["district"], r["segment"]))

    # Same self-contamination guard as Test B: a project must not benchmark against itself.
    dist_vals = defaultdict(list)
    for r in rows:
        if r["sale"] == SALE_RESALE:
            dist_vals[(r["district"], r["quarter"], r["band"], r["tenure"])].append((r["project"], r["psf"]))

    prem = defaultdict(list)
    for (proj, q, band, ten, district, seg), (npsf, _n) in new.items():
        vals = [p for pj, p in dist_vals.get((district, q, band, ten), []) if pj != proj]
        if len(vals) < MIN_CELL_N:
            continue                      # no like-for-like resale benchmark that quarter
        prem[seg].append((npsf / statistics.median(vals) - 1) * 100.0)

    return {seg: _describe(v) for seg, v in sorted(prem.items()) if v}


def test_b_premium_recovery(rows) -> dict:
    """Project $psf growth from launch, minus district resale growth over the same quarters."""
    by_proj_q_new = _medians([r for r in rows if r["sale"] == SALE_NEW],
                             lambda r: (r["project"], r["quarter"]))
    by_proj_q_res = _medians([r for r in rows if r["sale"] == SALE_RESALE],
                             lambda r: (r["project"], r["quarter"]))
    # District benchmark must EXCLUDE the project being measured. A large launch resells in
    # volume and would otherwise drag its own benchmark toward itself, biasing excess to zero
    # exactly where the effect matters most. Keep project labels so we can drop them per project.
    dist_vals = defaultdict(list)
    for r in rows:
        if r["sale"] == SALE_RESALE:
            dist_vals[(r["district"], r["quarter"])].append((r["project"], r["psf"]))

    def district_median_ex(district, q, exclude_project):
        vals = [p for proj, p in dist_vals.get((district, q), []) if proj != exclude_project]
        return (statistics.median(vals), len(vals)) if len(vals) >= MIN_CELL_N else None

    proj_meta = {}
    for r in rows:
        proj_meta.setdefault(r["project"], (r["district"], r["segment"]))

    launch_q = {}
    for (proj, q), _ in by_proj_q_new.items():
        launch_q[proj] = min(q, launch_q.get(proj, q))

    exit_q = {}
    for (proj, q), _ in by_proj_q_res.items():
        exit_q[proj] = max(q, exit_q.get(proj, q))

    excess, skipped_no_resale, skipped_short = defaultdict(list), 0, 0
    for proj, q0 in launch_q.items():
        q1 = exit_q.get(proj)
        if q1 is None:
            skipped_no_resale += 1
            continue
        if q1 - q0 < MIN_HOLD_QUARTERS:
            skipped_short += 1
            continue
        district, segment = proj_meta.get(proj, (None, None))
        d0 = district_median_ex(district, q0, proj)
        d1 = district_median_ex(district, q1, proj)
        if not d0 or not d1:
            continue
        years = (q1 - q0) / 4.0
        proj_cagr = (by_proj_q_res[(proj, q1)][0] / by_proj_q_new[(proj, q0)][0]) ** (1 / years) - 1
        dist_cagr = (d1[0] / d0[0]) ** (1 / years) - 1
        excess[segment].append({
            "project": proj, "segment": segment, "years": round(years, 2),
            "from": quarter_label(q0), "to": quarter_label(q1),
            "excess_pa_pct": (proj_cagr - dist_cagr) * 100.0,
        })

    return {
        "by_segment": {s: _describe([e["excess_pa_pct"] for e in v]) for s, v in sorted(excess.items())},
        "all": _describe([e["excess_pa_pct"] for v in excess.values() for e in v]),
        "detail": sorted((e for v in excess.values() for e in v), key=lambda e: e["excess_pa_pct"]),
        "coverage": {
            "launched_in_window": len(launch_q),
            "skipped_no_resale_yet": skipped_no_resale,
            "skipped_hold_under_4y": skipped_short,
        },
    }


def _describe(vals):
    """Distribution, not just the mean — the mean is what made the source claims misleading."""
    v = sorted(vals)
    if not v:
        return None
    def pct(p):
        return v[min(len(v) - 1, int(p * len(v)))]
    return {
        "n": len(v),
        "median": round(statistics.median(v), 2),
        "mean": round(statistics.fmean(v), 2),
        "p10": round(pct(0.10), 2), "p25": round(pct(0.25), 2),
        "p75": round(pct(0.75), 2), "p90": round(pct(0.90), 2),
        "share_positive_pct": round(100.0 * sum(1 for x in v if x > 0) / len(v), 1),
    }


# ---------------------------------------------------------------- self-test

def _tx(mmyy, price, sqm, sale, tenure="99 yrs lease commencing from 2020"):
    return {"contractDate": mmyy, "price": str(price), "area": str(sqm),
            "typeOfSale": sale, "propertyType": "Condominium", "tenure": tenure}


def self_test() -> int:
    fails, ran = [], []

    def check(label, got, want):
        ran.append(label)
        if got != want:
            fails.append(f"{label}: got {got!r}, want {want!r}")

    # --- date boundaries (vault rule: one month boundary, one year boundary) ---
    check("month Dec2021", month_index("1221"), 2021 * 12 + 12)
    check("month Jan2022", month_index("0122"), 2022 * 12 + 1)
    check("month boundary is consecutive",
          month_index("0122") - month_index("1221"), 1)
    check("year boundary Dec->Jan crosses a quarter",
          quarter_index("0122") - quarter_index("1221"), 1)
    check("Mar/Apr is a quarter boundary",
          quarter_index("0422") - quarter_index("0322"), 1)
    check("Jan/Feb/Mar share a quarter",
          {quarter_index("0122"), quarter_index("0222"), quarter_index("0322")},
          {quarter_index("0122")})
    check("quarter label", quarter_label(quarter_index("0322")), "2022Q1")
    check("quarter label Q4", quarter_label(quarter_index("1122")), "2022Q4")
    check("bad input is None", month_index("xxxx"), None)
    check("month 13 rejected", month_index("1322"), None)

    # --- classification ---
    check("size band lower edge", size_band(599.9), 0)
    check("size band 600 edge", size_band(600), 1)
    check("size band 1150 edge", size_band(1150), 3)
    check("tenure freehold", tenure_class("Freehold"), "FH")
    check("tenure 999y counts as FH", tenure_class("999 yrs lease commencing from 1875"), "FH")
    check("tenure 99y", tenure_class("99 yrs lease commencing from 2020"), "LH")

    # --- Test B end to end, with a KNOWN answer -------------------------------
    # DISTRICT resale benchmark: 1000 -> 1200 psf over exactly 5 years (20 quarters).
    # NEWPROJ launches at 1200 psf and resells at 1320 psf over the same 5 years.
    #   project CAGR  = (1320/1200)^(1/5) - 1 = 1.9245%
    #   district CAGR = (1200/1000)^(1/5) - 1 = 3.7137%
    #   excess        = -1.789241 %/yr -> -1.7892 (a launch premium NOT earned back)
    # Expected value recomputed independently of this harness before being asserted.
    sqm = 100.0
    sqft = sqm * SQM_TO_SQFT

    def units(psf, n, mmyy, sale, project):
        # Do NOT round the price: rounding to whole dollars perturbs the recovered $psf and
        # makes the expected CAGR non-exact, which would force a tolerance into an
        # exact-equality check. The fixture is arithmetic, not a realistic price.
        return [_tx(mmyy, psf * sqft, sqm, sale) for _ in range(n)]

    payload = [
        {"project": "BENCHMARK ONE", "district": "19", "marketSegment": "OCR",
         "transaction": units(1000, MIN_CELL_N, "0121", SALE_RESALE, "BENCHMARK ONE")
                      + units(1200, MIN_CELL_N, "0126", SALE_RESALE, "BENCHMARK ONE")},
        {"project": "NEWPROJ", "district": "19", "marketSegment": "OCR",
         "transaction": units(1200, MIN_CELL_N, "0121", SALE_NEW, "NEWPROJ")
                      + units(1320, MIN_CELL_N, "0126", SALE_RESALE, "NEWPROJ")},
    ]

    rows = flatten(payload)
    check("flatten kept all rows", len(rows), MIN_CELL_N * 4)

    b = test_b_premium_recovery(rows)
    detail = {e["project"]: e for e in b["detail"]}
    if "NEWPROJ" not in detail:
        fails.append(f"Test B dropped NEWPROJ; coverage={b['coverage']}")
    else:
        got = round(detail["NEWPROJ"]["excess_pa_pct"], 4)
        check("Test B excess p.a.", got, -1.7892)
        check("Test B holding years", detail["NEWPROJ"]["years"], 5.0)
        check("Test B window", (detail["NEWPROJ"]["from"], detail["NEWPROJ"]["to"]),
              ("2021Q1", "2026Q1"))

    # A project resold inside the SSD lock must be excluded, not silently averaged in.
    short = [{"project": "QUICKFLIP", "district": "19", "marketSegment": "OCR",
              "transaction": units(1200, MIN_CELL_N, "0121", SALE_NEW, "QUICKFLIP")
                           + units(1400, MIN_CELL_N, "0123", SALE_RESALE, "QUICKFLIP")}]
    b2 = test_b_premium_recovery(flatten(short))
    check("sub-4y hold excluded", b2["coverage"]["skipped_hold_under_4y"], 1)
    check("sub-4y produced no rows", len(b2["detail"]), 0)

    # SELF-CONTAMINATION GUARD. Adding a second, identical benchmark project must not change
    # NEWPROJ's excess: its own resales are excluded from the district median either way.
    # Without the exclusion this figure moves (it was -2.8062 when NEWPROJ polluted its own
    # benchmark), which is how this bias was found.
    payload2 = payload + [
        {"project": "BENCHMARK TWO", "district": "19", "marketSegment": "OCR",
         "transaction": units(1000, MIN_CELL_N, "0121", SALE_RESALE, "BENCHMARK TWO")
                      + units(1200, MIN_CELL_N, "0126", SALE_RESALE, "BENCHMARK TWO")},
    ]
    d2 = {e["project"]: e for e in test_b_premium_recovery(flatten(payload2))["detail"]}
    check("excess is invariant to benchmark size",
          round(d2.get("NEWPROJ", {}).get("excess_pa_pct", 0), 4), -1.7892)

    # Cells below MIN_CELL_N must be dropped, not trusted.
    thin = [{"project": "THIN", "district": "19", "marketSegment": "OCR",
             "transaction": units(1200, MIN_CELL_N - 1, "0121", SALE_NEW, "THIN")
                          + units(1400, MIN_CELL_N - 1, "0126", SALE_RESALE, "THIN")}]
    check("thin cells dropped", len(test_b_premium_recovery(flatten(thin))["detail"]), 0)

    # Test A: NEWPROJ at 1200 vs district resale 1000 in the same quarter = +20%.
    a = test_a_launch_premium(rows)
    check("Test A premium median", a.get("OCR", {}).get("median"), 20.0)

    if fails:
        print("SELF-TEST FAILED")
        for f in fails:
            print("  -", f)
        return 1
    print(f"SELF-TEST PASSED ({len(ran)} checks) - date boundaries, banding, "
          "self-contamination guard, SSD-hold and thin-cell exclusions, both tests.")
    return 0


# ---------------------------------------------------------------- run

def load_live(key: str) -> list:
    import urllib.request
    ua = {"User-Agent": "Mozilla/5.0"}

    def get(url, headers):
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=90) as r:
            return json.loads(r.read().decode())

    token = get("https://eservice.ura.gov.sg/uraDataService/insertNewToken/v1",
                {**ua, "AccessKey": key}).get("Result")
    hdr = {**ua, "AccessKey": key, "Token": token}
    out = []
    for batch in (1, 2, 3, 4):
        out += get("https://eservice.ura.gov.sg/uraDataService/invokeUraDS/v1"
                   f"?service=PMI_Resi_Transaction&batch={batch}", hdr).get("Result", [])
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--self-test", action="store_true", help="verify the logic on synthetic fixtures; no key needed")
    ap.add_argument("--run", action="store_true", help="run against live URA data; needs URA_ACCESS_KEY")
    ap.add_argument("--out", default="reviews/launch_vs_resale_result.json")
    args = ap.parse_args()

    if args.self_test or not args.run:
        return self_test()

    key = os.environ.get("URA_ACCESS_KEY")
    if not key:
        print("URA_ACCESS_KEY is not set.\n"
              "Register a free AccessKey at https://eservice.ura.gov.sg/maps/api/reg.html,\n"
              "then set it in your shell and re-run. The key is never read or stored by this script\n"
              "beyond the request it makes.", file=sys.stderr)
        return 2

    print("Self-test first (a harness that fails its own tests must not produce results)...")
    if self_test() != 0:
        return 1

    rows = flatten(load_live(key))
    print(f"\n{len(rows):,} condo/apartment transactions in window.")
    result = {
        "_design": "pre-registered; see module docstring",
        "_caveats": ["no unit identity - project-level psf, NOT repeat sales",
                     "sample conditioned on a resale existing (SSD selection)",
                     "floor mix not controlled",
                     "~5-year window = one rate/cooling regime"],
        "test_a_launch_premium_pct": test_a_launch_premium(rows),
        "test_b_premium_recovery": test_b_premium_recovery(rows),
    }
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)

    b = result["test_b_premium_recovery"]
    print("\nTest A — launch premium at entry (% over contemporaneous district resale):")
    for seg, d in (result["test_a_launch_premium_pct"] or {}).items():
        print(f"  {seg}: median {d['median']}%  (p25 {d['p25']} / p75 {d['p75']}, n={d['n']})")
    print("\nTest B — excess $psf growth vs district, per annum (FLAGSHIP):")
    print(f"  coverage: {b['coverage']}")
    for seg, d in (b["by_segment"] or {}).items():
        if d:
            print(f"  {seg}: median {d['median']}%/yr, {d['share_positive_pct']}% positive (n={d['n']})")
    if b["all"]:
        print(f"  ALL: median {b['all']['median']}%/yr, {b['all']['share_positive_pct']}% positive "
              f"(n={b['all']['n']}, p10 {b['all']['p10']} / p90 {b['all']['p90']})")
        print("\nRead against the pre-registered null: dispersion straddling zero means "
              '"not a rule you can lean on", which is the publishable finding.')
    print(f"\nWritten to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
