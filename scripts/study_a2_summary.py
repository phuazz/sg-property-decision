#!/usr/bin/env python3
"""Print test A2's result in the shape the pre-registration asks to see it.

A separate file rather than an inline heredoc in the workflow: the first attempt embedded this
as `run: |` with a `<<'PY'` heredoc, the Python landed at column 1, and the YAML stopped parsing
entirely — which GitHub reports as a workflow whose name is its own file path and a dispatch
that 422s. Not worth debugging twice.

Reads reviews/launch_vs_resale_result.json; prints nothing it did not find.
"""
import json
import sys


def main(path="reviews/launch_vs_resale_result.json") -> int:
    r = json.load(open(path, encoding="utf-8")).get("test_a2_lease_matched")
    if not r:
        print("no test_a2_lease_matched block in the result file")
        return 1

    # Two different baselines, printed together because conflating them is exactly the mistake
    # this summary was rewritten to prevent.
    full = json.load(open(path, encoding="utf-8")).get("test_a_launch_premium_pct") or {}
    print("\nTEST A — tenure matched on both sides, freehold and leasehold new sales together.")
    print("         This is the figure the published articles quote.")
    for seg, d in full.items():
        print(f"  {seg}: {d['median']:+.1f}%   p25 {d['p25']:+.1f} / p75 {d['p75']:+.1f}   n={d['n']}")

    print("\nA2 BASELINE — leasehold new sales vs ALL leasehold resale, no lease restriction.")
    print("         Not test A. This is the anchor the lease gradient below is read against,")
    print("         and it excludes freehold on both sides so the buckets are like-for-like.")
    for seg, d in (r.get("unrestricted_leasehold_baseline") or {}).items():
        print(f"  {seg}: {d['median']:+.1f}%   p25 {d['p25']:+.1f} / p75 {d['p75']:+.1f}   n={d['n']}")

    print("\nLEASE GRADIENT — same new sales, comparator restricted by lease remaining:")
    print(f"  {'lease':>7} {'seg':>4} {'median':>8} {'n':>6} {'districts':>10} {'mrt_m':>7}")
    for lab, block in (r.get("gradient") or {}).items():
        for seg, d in (block or {}).items():
            flag = "" if d.get("feasible") else "   INFEASIBLE — below the pre-registered floor"
            lost = d.get("districts_lost_vs_test_a") or []
            print(f"  {lab:>7} {seg:>4} {d['median']:>+7.1f}% {d['n']:>6} {d['districts']:>10} "
                  f"{str(d.get('comparator_median_mrt_m') or '-'):>7}{flag}")
            if lost:
                print(f"          districts lost vs test A ({len(lost)}): {', '.join(map(str, lost))}")

    dc = r.get("district_coverage") or {}
    if dc:
        print("
DISTRICT COVERAGE — how much of each segment survives the 85+ restriction:")
        for seg, d in dc.items():
            print(f"  {seg}: {d['surviving_85plus']} of {d['districts_with_new_sales']} districts"
                  f"  ({d['share']})   all: {','.join(d['all_districts'])}")

    pe = r.get("paired_lease_effect_pp") or {}
    if pe:
        print("
PAIRED LEASE EFFECT — same observation, two comparator pools.")
        print("         District, quarter, band and project are identical on each side,")
        print("         so this isolates lease from the district-mix change above.")
        for seg, d in pe.items():
            flag = "" if d.get("feasible") else "   INFEASIBLE"
            print(f"  {seg}: baseline {d['baseline_on_shared']:+.1f}% - lease-matched "
                  f"{d['lease_matched_on_shared']:+.1f}% = {d['median']:+.1f}pp"
                  f"   n={d['n']} districts={d['districts']}{flag}")

    fh = (r.get("freehold_control") or {}).get("FH") or {}
    print("\nFREEHOLD CONTROL — freehold new sales against freehold resale:")
    for seg, d in fh.items():
        print(f"  {seg}: {d['median']:+.1f}%   n={d['n']}")
    if not fh:
        print("  (none survived the cell floor)")

    print("\ncoverage:", json.dumps(r.get("coverage"), indent=2))
    print("\nceiling:", r.get("_ceiling"))
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
