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

WAYS THIS COULD BE SILENTLY WRONG
    0. LEFT-CENSORED LAUNCH QUARTER. **This one actually happened.** The first live run
       reported -4.04%/yr excess across 24 projects and every "launch" quarter was 2021Q3 or
       2021Q4 - the first two quarters of the data window. Those were not launches. Avenue
       South Residence, Treasure at Tampines, Parc Clematis and Jadescape all launched in
       2018-19 and were still selling remaining units when the window opened. A late-phase
       price is biased HIGH (developers raise prices as they sell through), which biases the
       excess DOWN and manufactured the entire result. That run is VOID. Projects whose first
       visible new sale falls within CENSOR_BUFFER_QUARTERS of the window start are now
       excluded and counted separately. The deeper consequence: a ~5-year window cannot hold
       both a genuine launch and a resale 4+ years later, so this test may be infeasible on
       free URA data. If coverage comes back at or near zero, THAT is the finding.
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
import datetime
import json
import os
import re
import statistics
import sys
from collections import defaultdict

SQM_TO_SQFT = 10.7639
MIN_CELL_N = 5           # minimum transactions before a project-quarter median is trusted
MIN_HOLD_QUARTERS = 16   # 4 years — below the SSD lock, resales are non-random
CENSOR_BUFFER_QUARTERS = 2  # a "launch" this close to the window start is probably not one
MIN_YEAR_CELLS = 20      # per segment per year, before a year is reported as a trend point

# --- Test A2, pre-registered 2026-08-08 in reviews/2026-08-08_lease-matched-entry-gap_PREREG.md
# Test A compares a new sale against ALL resale in its district, most of which has decades less
# lease to run, so the gap blends the new-build premium with a plain lease difference. A2 is the
# same estimand with the comparator additionally restricted by lease remaining.
LEASE_PRIMARY_MIN = 85            # the like-for-like read a buyer of a fresh 99 actually faces
LEASE_BUCKETS = ((85, 9999, "85+"), (70, 84, "70-84"), (55, 69, "55-69"), (0, 54, "<55"))
MIN_SEGMENT_N = 20                # pre-registered stop condition: below this, report infeasible
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


def lease_left(tenure: str, cur_year: int):
    """'Freehold' -> 'FH'; '99 yrs lease commencing from 1998' -> remaining years; else None.

    Deliberately identical to fetch_data.py::_lease_left, including measuring the remaining term
    from the CURRENT year rather than the transaction date. Two reasons. The dashboard's published
    lease figures use that convention, so a divergence here would put the study and the site on
    different definitions of the same word. And it is the conservative direction: measuring from
    today understates remaining lease on older transactions, which can only pull comparators OUT
    of the 85+ bucket, never into it.
    """
    t = str(tenure or "")
    if "Freehold" in t:
        return "FH"
    m = re.search(r"(\d+)\s*yr?s?\s*lease\s*commencing\s*from\s*(\d{4})", t, re.I)
    if m:
        return max(0, int(m.group(1)) - (cur_year - int(m.group(2))))
    return None


def lease_bucket(ll):
    """Remaining-years int -> bucket label, or None for FH/unparseable."""
    if not isinstance(ll, int):
        return None
    for lo, hi, lab in LEASE_BUCKETS:
        if lo <= ll <= hi:
            return lab
    return None


def flatten(projects: list) -> list:
    """URA payload -> flat transaction rows. Drops anything unusable rather than guessing."""
    rows = []
    cur_year = datetime.date.today().year
    for proj in projects or []:
        name = proj.get("project")
        district = proj.get("district")
        segment = proj.get("marketSegment")
        px, py = proj.get("x"), proj.get("y")
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
                # District lives on the TRANSACTION in PMI_Resi_Transaction, not on the project.
                # fetch_data.py reads t["district"] in three places; this script read
                # proj["district"], which is absent, so every row carried district=None and every
                # "district" comparator pool was silently a NATIONAL one. The project-level
                # fallback is kept only because the synthetic fixtures set it there.
                "district": t.get("district") or district,
                "segment": segment,
                "quarter": qi,
                "psf": price / sqft,
                "band": size_band(sqft),
                "tenure": tenure_class(t.get("tenure")),
                "sale": str(t.get("typeOfSale", "")).strip(),
                "lease": lease_left(t.get("tenure"), cur_year),
                "x": px, "y": py,
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


def test_a_by_year(rows) -> dict:
    """Test A, split by calendar year — is the new-build premium widening or narrowing?

    The headline Test A is a single median across the whole window, which cannot tell a
    level from a trend. The article says as much; this answers it. Same comparison, same
    self-contamination guard, grouped by the year the comparison falls in.

    A year is reported only if every segment in it clears MIN_YEAR_CELLS, so a thin
    partial year at either end of the window cannot masquerade as a turning point.
    """
    new = _medians([r for r in rows if r["sale"] == SALE_NEW],
                   lambda r: (r["project"], r["quarter"], r["band"], r["tenure"], r["district"], r["segment"]))
    dist_vals = defaultdict(list)
    for r in rows:
        if r["sale"] == SALE_RESALE:
            dist_vals[(r["district"], r["quarter"], r["band"], r["tenure"])].append((r["project"], r["psf"]))

    by = defaultdict(list)
    for (proj, q, band, ten, district, seg), (npsf, _n) in new.items():
        vals = [p for pj, p in dist_vals.get((district, q, band, ten), []) if pj != proj]
        if len(vals) < MIN_CELL_N:
            continue
        by[(seg, q // 4)].append((npsf / statistics.median(vals) - 1) * 100.0)

    years = sorted({y for _s, y in by})
    out, dropped = {}, []
    for y in years:
        cells = {seg: by.get((seg, y), []) for seg in ("CCR", "RCR", "OCR")}
        if any(len(v) < MIN_YEAR_CELLS for v in cells.values()):
            dropped.append({"year": y, "n": {s: len(v) for s, v in cells.items()}})
            continue
        out[str(y)] = {seg: _describe(v) for seg, v in cells.items()}
    return {"by_year": out, "dropped_thin_years": dropped,
            "min_cells_per_segment_year": MIN_YEAR_CELLS}


def test_a2_lease_matched(rows, mrt_by_project=None) -> dict:
    """Test A with the resale comparator additionally restricted by lease remaining.

    Pre-registered 2026-08-08. Identical to test A in every respect - same estimand, same size
    band, same tenure class, same self-contamination guard, same MIN_CELL_N floor - except that
    the comparator pool is split by how much lease it has left.

    Primary: comparator restricted to leasehold with LEASE_PRIMARY_MIN+ years remaining.
    Secondary: the same gap against each lease bucket, because the SHAPE across buckets is the
    finding. A monotone gradient is the signature of a lease effect; a flat one falsifies the
    premise the study was built on.

    What this can and cannot say, stated here because the write-up must not overreach: stock with
    85+ years remaining is also newer, better specified and more likely near a station, since
    recent land release is transit-oriented by policy. Matching on lease therefore partly matches
    on the newness being priced. **This bounds the blend; it does not decompose it.** The true
    newness premium is no LARGER than the lease-matched gap. It is not equal to it.
    """
    mrt_by_project = mrt_by_project or {}
    new = _medians([r for r in rows if r["sale"] == SALE_NEW],
                   lambda r: (r["project"], r["quarter"], r["band"], r["tenure"], r["district"], r["segment"]))

    # One comparator pool per lease bucket, plus freehold kept apart (pre-registered: excluded
    # from the primary, reported separately).
    labels = [lab for _lo, _hi, lab in LEASE_BUCKETS] + ["FH"]
    pools = {lab: defaultdict(list) for lab in labels}
    unparseable = 0
    for r in rows:
        if r["sale"] != SALE_RESALE:
            continue
        key = (r["district"], r["quarter"], r["band"])
        if r["lease"] == "FH":
            pools["FH"][key].append((r["project"], r["psf"]))
            continue
        lab = lease_bucket(r["lease"])
        if lab is None:
            unparseable += 1
            continue
        pools[lab][key].append((r["project"], r["psf"]))

    def gap_against(pool, want_tenure):
        """Returns {segment: [gap%]}, plus the districts and projects that survived."""
        prem, districts, comparators = defaultdict(list), defaultdict(set), []
        for (proj, q, band, ten, district, seg), (npsf, _n) in new.items():
            if ten != want_tenure:
                continue
            vals = [p for pj, p in pool.get((district, q, band), []) if pj != proj]
            if len(vals) < MIN_CELL_N:
                continue
            prem[seg].append((npsf / statistics.median(vals) - 1) * 100.0)
            districts[seg].add(district)
            comparators += [pj for pj, _p in pool.get((district, q, band), []) if pj != proj]
        return prem, districts, comparators

    # ---- the full test-A comparison, recomputed here so the loss is measured, not assumed -----
    all_pool = defaultdict(list)
    for r in rows:
        if r["sale"] == SALE_RESALE:
            all_pool[(r["district"], r["quarter"], r["band"])].append((r["project"], r["psf"]))
    base_prem, base_districts, _ = gap_against(all_pool, "LH")

    out = {"primary": {}, "gradient": {}, "freehold_control": {}, "coverage": {}}

    for lab in labels:
        want = "FH" if lab == "FH" else "LH"
        prem, districts, comparators = gap_against(pools[lab], want)
        block = {}
        for seg, vals in sorted(prem.items()):
            d = _describe(vals)
            d["districts"] = len(districts[seg])
            # Guard 1: a segment carried by a handful of districts is not a segment.
            d["districts_lost_vs_test_a"] = sorted(base_districts.get(seg, set()) - districts[seg])
            d["feasible"] = len(vals) >= MIN_SEGMENT_N
            # Guard 3: location drift made visible rather than assumed absent.
            dists = [mrt_by_project[p] for p in comparators if p in mrt_by_project]
            d["comparator_median_mrt_m"] = round(statistics.median(dists)) if dists else None
            block[seg] = d
        (out["freehold_control"] if lab == "FH" else out["gradient"])[lab] = block

    out["primary"] = out["gradient"].get("85+", {})
    out["unmatched_test_a_for_reference"] = {seg: _describe(v) for seg, v in sorted(base_prem.items()) if v}
    out["coverage"] = {
        "min_comparators_per_cell": MIN_CELL_N,
        "min_comparisons_per_segment": MIN_SEGMENT_N,
        "lease_unparseable_resale_rows": unparseable,
        "lease_measured_from": "current year, as fetch_data.py::_lease_left does",
    }
    out["_ceiling"] = ("Bounds the blend, does not decompose it: lease and newness are collinear "
                       "by construction, so the true newness premium is no larger than the "
                       "lease-matched gap, not equal to it.")
    return out


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

    # LEFT-CENSORING GUARD. `min(quarter with a new sale)` is NOT the launch quarter for a
    # project that launched before the data window opened - it is merely the first quarter we
    # can see, i.e. a late-phase price. Developers raise prices as they sell through, so a
    # censored entry is biased HIGH, which biases the excess DOWN. The first run of this study
    # returned -4%/yr on 24 projects whose "launch" quarters were all the window's first two
    # quarters (Avenue South Residence, Treasure at Tampines, Parc Clematis and Jadescape all
    # actually launched in 2018-19). That result was an artefact of this, and is void.
    window_start = min(r["quarter"] for r in rows)

    launch_q, censored = {}, set()
    for (proj, q), _ in by_proj_q_new.items():
        launch_q[proj] = min(q, launch_q.get(proj, q))
    for proj, q in list(launch_q.items()):
        if q <= window_start + CENSOR_BUFFER_QUARTERS:
            censored.add(proj)
            del launch_q[proj]

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
            "window": [quarter_label(window_start),
                       quarter_label(max(r["quarter"] for r in rows))],
            "genuinely_launched_in_window": len(launch_q),
            "skipped_left_censored": len(censored),
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

    # --- response decoding (a strict utf-8 decode killed the first live run) ---
    check("utf-8 body decodes", decode_body("PARC CLEMATIS".encode("utf-8"), "utf-8"), "PARC CLEMATIS")
    check("cp1252 body does not raise",
          decode_body("CAFÉ ROYALE".encode("cp1252"), None), "CAFÉ ROYALE")
    check("bogus declared charset falls through",
          decode_body("PARC".encode("utf-8"), "not-a-charset"), "PARC")
    check("undecodable bytes still return a string",
          isinstance(decode_body(b"\xff\xfe\x00\x01", None), str), True)

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

    def units(psf, n, mmyy, sale):
        # Do NOT round the price: rounding to whole dollars perturbs the recovered $psf and
        # makes the expected CAGR non-exact, forcing a tolerance into an exact-equality check.
        return [_tx(mmyy, psf * sqft, sqm, sale) for _ in range(n)]

    def proj(name, *groups):
        return {"project": name, "district": "19", "marketSegment": "OCR",
                "transaction": [t for g in groups for t in g]}

    # Anchors the observed window at 2020Q1 so NEWPROJ's 2021Q1 launch sits clear of the
    # left-censoring buffer and is treated as a genuine launch.
    anchor = proj("WINDOW ANCHOR", units(900, MIN_CELL_N, "0120", SALE_RESALE))

    # DISTRICT resale benchmark: 1000 -> 1200 psf over exactly 5 years (20 quarters).
    # NEWPROJ launches at 1200 psf and resells at 1320 psf over the same 5 years.
    #   project CAGR  = (1320/1200)^(1/5) - 1 = 1.924488%
    #   district CAGR = (1200/1000)^(1/5) - 1 = 3.713729%
    #   excess        = -1.789241 %/yr -> -1.7892 (a launch premium NOT earned back)
    # Expected value recomputed independently of this harness before being asserted.
    payload = [
        anchor,
        proj("BENCHMARK ONE", units(1000, MIN_CELL_N, "0121", SALE_RESALE),
                              units(1200, MIN_CELL_N, "0126", SALE_RESALE)),
        proj("NEWPROJ", units(1200, MIN_CELL_N, "0121", SALE_NEW),
                        units(1320, MIN_CELL_N, "0126", SALE_RESALE)),
    ]

    rows = flatten(payload)
    check("flatten kept all rows", len(rows), MIN_CELL_N * 5)

    b = test_b_premium_recovery(rows)
    detail = {e["project"]: e for e in b["detail"]}
    if "NEWPROJ" not in detail:
        fails.append(f"Test B dropped NEWPROJ; coverage={b['coverage']}")
    else:
        check("Test B excess p.a.", round(detail["NEWPROJ"]["excess_pa_pct"], 4), -1.7892)
        check("Test B holding years", detail["NEWPROJ"]["years"], 5.0)
        check("Test B window", (detail["NEWPROJ"]["from"], detail["NEWPROJ"]["to"]),
              ("2021Q1", "2026Q1"))
    check("genuine launch is counted", b["coverage"]["genuinely_launched_in_window"], 1)
    check("genuine launch is not flagged censored", b["coverage"]["skipped_left_censored"], 0)
    check("observed window reported", b["coverage"]["window"], ["2020Q1", "2026Q1"])

    # LEFT-CENSORING GUARD — the bug that voided the first live run. Without the anchor,
    # LATEPHASE's first visible new sale IS the window's opening quarter, so it cannot be
    # shown to be a launch (it is more likely a late phase of an older project) and must be
    # excluded rather than measured.
    censored_fx = [
        proj("BENCHMARK ONE", units(1000, MIN_CELL_N, "0121", SALE_RESALE),
                              units(1200, MIN_CELL_N, "0126", SALE_RESALE)),
        proj("LATEPHASE", units(1200, MIN_CELL_N, "0121", SALE_NEW),
                          units(1320, MIN_CELL_N, "0126", SALE_RESALE)),
    ]
    cov_c = test_b_premium_recovery(flatten(censored_fx))["coverage"]
    check("left-censored launch excluded", cov_c["skipped_left_censored"], 1)
    check("left-censored launch not measured", cov_c["genuinely_launched_in_window"], 0)

    # A project resold inside the SSD lock must be excluded, not silently averaged in.
    short = [anchor, proj("QUICKFLIP", units(1200, MIN_CELL_N, "0121", SALE_NEW),
                                       units(1400, MIN_CELL_N, "0123", SALE_RESALE))]
    b2 = test_b_premium_recovery(flatten(short))
    check("sub-4y hold excluded", b2["coverage"]["skipped_hold_under_4y"], 1)
    check("sub-4y produced no rows", len(b2["detail"]), 0)

    # SELF-CONTAMINATION GUARD. Adding a second, identical benchmark project must not move
    # NEWPROJ's excess: its own resales are excluded from the district median either way.
    # Without the exclusion this read -2.8062, which is how the bias was found.
    payload2 = payload + [
        proj("BENCHMARK TWO", units(1000, MIN_CELL_N, "0121", SALE_RESALE),
                              units(1200, MIN_CELL_N, "0126", SALE_RESALE)),
    ]
    d2 = {e["project"]: e for e in test_b_premium_recovery(flatten(payload2))["detail"]}
    check("excess is invariant to benchmark size",
          round(d2.get("NEWPROJ", {}).get("excess_pa_pct", 0), 4), -1.7892)

    # Cells below MIN_CELL_N must be dropped, not trusted.
    thin = [anchor, proj("THIN", units(1200, MIN_CELL_N - 1, "0121", SALE_NEW),
                                 units(1400, MIN_CELL_N - 1, "0126", SALE_RESALE))]
    check("thin cells dropped", len(test_b_premium_recovery(flatten(thin))["detail"]), 0)

    # Test A: NEWPROJ at 1200 vs district resale 1000 in the same quarter = +20%.
    a = test_a_launch_premium(rows)
    check("Test A premium median", a.get("OCR", {}).get("median"), 20.0)

    # --- Test A2: lease parsing, bucket edges, and the restricted comparator ---------------
    Y = datetime.date.today().year
    check("lease FH", lease_left("Freehold", Y), "FH")
    check("999-year term classes as FH", tenure_class("999 yrs lease commencing from 1875"), "FH")
    check("lease remaining arithmetic", lease_left(f"99 yrs lease commencing from {Y - 10}", Y), 89)
    check("lease never negative", lease_left("99 yrs lease commencing from 1900", Y), max(0, 99 - (Y - 1900)))
    check("lease unparseable", lease_left("Leasehold", Y), None)
    check("bucket 85 is 85+", lease_bucket(85), "85+")
    check("bucket 84 is 70-84", lease_bucket(84), "70-84")
    check("bucket 70 is 70-84", lease_bucket(70), "70-84")
    check("bucket 69 is 55-69", lease_bucket(69), "55-69")
    check("bucket 55 is 55-69", lease_bucket(55), "55-69")
    check("bucket 54 is <55", lease_bucket(54), "<55")
    check("bucket FH is None", lease_bucket("FH"), None)

    # A new sale at 1200 psf against two resale pools in the SAME cell differing only by lease:
    # long-lease at 1000 (gap +20%) and short-lease at 800 (gap +50%). If A2 works, the primary
    # reads the long-lease pool and the gradient widens as lease shortens.
    LONG = f"99 yrs lease commencing from {Y - 5}"
    SHORT = f"99 yrs lease commencing from {Y - 50}"
    def resale_at(psf, tenure, sqm=100):
        return [_tx("0324", int(psf * sqm * SQM_TO_SQFT), sqm, SALE_RESALE, tenure)
                for _ in range(MIN_CELL_N)]
    a2rows = flatten([
        proj("A2NEW", units(1200, MIN_CELL_N, "0324", SALE_NEW)),
        proj("A2LONG", resale_at(1000, LONG)),
        proj("A2SHORT", resale_at(800, SHORT)),
    ])
    a2 = test_a2_lease_matched(a2rows)
    check("A2 primary uses the long-lease pool", a2["primary"].get("OCR", {}).get("median"), 20.0)
    check("A2 gradient widens on short lease", a2["gradient"]["<55"].get("OCR", {}).get("median"), 50.0)
    check("A2 empty middle bucket stays empty", a2["gradient"]["70-84"], {})
    check("A2 marks a thin segment infeasible", a2["primary"].get("OCR", {}).get("feasible"), False)

    # A project must not benchmark against itself in A2 either.
    solo = flatten([proj("SOLO", units(1200, MIN_CELL_N, "0324", SALE_NEW),
                                 units(1000, MIN_CELL_N, "0324", SALE_RESALE))])
    check("A2 self-contamination guard", test_a2_lease_matched(solo)["primary"], {})

    # District must be read off the transaction, and two districts must never pool together.
    # This is the bug that made the first live A2 run report districts=1 in every cell: the
    # comparator pool was keyed on district=None, so all 26 districts formed one pool and the
    # "district resale median" every published figure rests on was a national median.
    def tx_in(dist, psf, sale, mmyy="0324", sqm=100, tenure=LONG):
        out = []
        for _ in range(MIN_CELL_N):
            t = _tx(mmyy, psf * sqm * SQM_TO_SQFT, sqm, sale, tenure)
            t["district"] = dist
            out.append(t)
        return out
    twod = flatten([
        {"project": "D9NEW", "marketSegment": "CCR", "transaction": tx_in("09", 2000, SALE_NEW)},
        {"project": "D9COMP", "marketSegment": "CCR", "transaction": tx_in("09", 1000, SALE_RESALE)},
        {"project": "D27COMP", "marketSegment": "CCR", "transaction": tx_in("27", 500, SALE_RESALE)},
    ])
    check("district is read from the transaction", {r["district"] for r in twod}, {"09", "27"})
    # D9NEW must price off D9 alone (2000/1000 = +100%), never blended with the cheap D27 pool.
    check("districts do not pool together",
          test_a2_lease_matched(twod)["primary"].get("CCR", {}).get("median"), 100.0)

    # Freehold comparators must not leak into the primary.
    fh = flatten([proj("FHNEW", units(1200, MIN_CELL_N, "0324", SALE_NEW)),
                  proj("FHCOMP", resale_at(1000, "Freehold"))])
    check("A2 primary ignores freehold comparators", test_a2_lease_matched(fh)["primary"], {})

    # Tenure must match on BOTH sides. A freehold new sale may not be priced off a leasehold
    # pool, however long that pool's lease. Without this the mutation "drop the tenure match"
    # goes unnoticed, which is how it was found.
    def new_at(psf, tenure, sqm=100, mmyy="0324"):
        return [_tx(mmyy, psf * sqm * SQM_TO_SQFT, sqm, SALE_NEW, tenure) for _ in range(MIN_CELL_N)]
    xten = flatten([proj("XFHNEW", new_at(1200, "Freehold")),
                    proj("XLHCOMP", resale_at(1000, LONG))])
    x = test_a2_lease_matched(xten)
    check("A2 will not price a freehold new sale off a leasehold pool", x["primary"], {})
    check("A2 freehold control also empty without a freehold comparator", x["freehold_control"]["FH"], {})

    # ...and the freehold control does fire when both sides are freehold.
    fhpair = flatten([proj("FHNEW2", new_at(1200, "Freehold")),
                      proj("FHCOMP2", resale_at(1000, "Freehold"))])
    check("A2 freehold control reports a freehold-vs-freehold gap",
          test_a2_lease_matched(fhpair)["freehold_control"]["FH"].get("OCR", {}).get("median"), 20.0)

    if fails:
        print("SELF-TEST FAILED")
        for f in fails:
            print("  -", f)
        return 1
    print(f"SELF-TEST PASSED ({len(ran)} checks) - date boundaries, banding, "
          "self-contamination guard, SSD-hold and thin-cell exclusions, both tests.")
    return 0


# ---------------------------------------------------------------- run

def decode_body(raw: bytes, charset: str | None = None) -> str:
    """Decode a URA response body.

    The URA payload is NOT reliably UTF-8 — some project names carry cp1252 bytes, which
    raises UnicodeDecodeError on a strict utf-8 decode partway through a multi-megabyte
    batch. fetch_data.py never hit this because `requests` sniffs the charset for it.
    Try the declared charset, then utf-8, then cp1252; latin-1 cannot fail, so it is the
    terminal fallback. Project names are grouping keys, so a consistent decode matters
    more than perfect fidelity, but we prefer a correct one where available.
    """
    for enc in [c for c in (charset, "utf-8", "cp1252") if c]:
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("latin-1")


def load_live(key: str) -> list:
    import urllib.request
    ua = {"User-Agent": "Mozilla/5.0"}

    def get(url, headers):
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=120) as r:
            return json.loads(decode_body(r.read(), r.headers.get_content_charset()))

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

    payload = load_live(key)
    rows = flatten(payload)
    print(f"\n{len(rows):,} condo/apartment transactions in window.")
    # Census the key the comparator pools are built on. The first A2 run reported districts=1
    # in every cell because district was read off the project rather than the transaction and
    # came back None, silently merging all 26 into one national pool. A count that can be read
    # in the log costs nothing and makes that failure impossible to miss again.
    ndist = len({r["district"] for r in rows if r["district"]})
    print(f"{ndist} distinct districts; "
          f"{sum(1 for r in rows if not r['district']):,} rows carry no district.")
    if ndist < 20:
        print("::warning::fewer districts than expected — comparator pools may be merging")

    # Guard 3 of the A2 pre-registration: report the comparator's distance to MRT, so a drift in
    # WHERE the surviving stock sits is visible rather than assumed absent. Best-effort — the
    # study still runs, and says so, if the station feed or pyproj is unavailable.
    mrt = {}
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from fetch_data import _add_mrt
        pts = [{"project": p.get("project"), "x": p.get("x"), "y": p.get("y")} for p in payload or []]
        _add_mrt(pts)
        mrt = {p["project"]: p["mrt_m"] for p in pts if p.get("mrt_m") is not None}
        print(f"MRT distances resolved for {len(mrt):,} projects.")
    except Exception as e:
        print(f"  note: A2 location guard unavailable ({e!r}); gap still reported, drift not measured")
    result = {
        "_design": "pre-registered; see module docstring",
        "_caveats": ["no unit identity - project-level psf, NOT repeat sales",
                     "sample conditioned on a resale existing (SSD selection)",
                     "floor mix not controlled",
                     "~5-year window = one rate/cooling regime"],
        "test_a_launch_premium_pct": test_a_launch_premium(rows),
        "test_a_by_year": test_a_by_year(rows),
        "test_a2_lease_matched": test_a2_lease_matched(rows, mrt_by_project=mrt),
        "test_b_premium_recovery": test_b_premium_recovery(rows),
    }
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as fh:
        json.dump(result, fh, indent=2)

    b = result["test_b_premium_recovery"]
    print("\nTest A — launch premium at entry (% over contemporaneous district resale):")
    for seg, d in (result["test_a_launch_premium_pct"] or {}).items():
        print(f"  {seg}: median {d['median']}%  (p25 {d['p25']} / p75 {d['p75']}, n={d['n']})")
    ty = result["test_a_by_year"]
    if ty["by_year"]:
        print("\nTest A by year — is the premium widening? (median %, n per cell)")
        for y in sorted(ty["by_year"]):
            row = " · ".join(f"{seg} {d['median']:+.1f}% (n={d['n']})"
                             for seg, d in ty["by_year"][y].items() if d)
            print(f"  {y}: {row}")
        if ty["dropped_thin_years"]:
            print(f"  dropped as too thin: {[d['year'] for d in ty['dropped_thin_years']]}")
    else:
        print("\nTest A by year — no year had enough comparisons in every segment.")

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
