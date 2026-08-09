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

    print("\nUNMATCHED — test A, comparator is all resale in the district:")
    for seg, d in (r.get("unmatched_test_a_for_reference") or {}).items():
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
