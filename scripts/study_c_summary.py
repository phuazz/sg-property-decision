#!/usr/bin/env python3
"""Print test C's result in the shape the pre-registration asks to see it.

A separate file rather than an inline heredoc in the workflow, for the reason recorded in
study_a2_summary.py: Python at column 1 inside a `run: |` block stops the YAML parsing entirely.

Reads reviews/launch_vs_resale_result.json; prints nothing it did not find.
"""
import json
import sys


def main(path="reviews/launch_vs_resale_result.json") -> int:
    r = json.load(open(path, encoding="utf-8")).get("test_c_age_decay")
    if not r:
        print("no test_c_age_decay block in the result file")
        return 1

    a = r.get("entry_anchor_new_sales")
    if a:
        flag = "" if a.get("feasible") else "   INFEASIBLE"
        print(f"\nENTRY ANCHOR — new sales against the same all-age resale cells.")
        print(f"  {a['median']:+.1f}%   p25 {a['p25']:+.1f} / p75 {a['p75']:+.1f}   "
              f"n={a['n']}  districts={a['districts']}{flag}")

    print("\nDECAY GRADIENT — resale premium over its own district-quarter-band cell, by age.")
    print("         Cell pools all ages, project excluded from its own cell, size in the key.")
    print(f"  {'age':>7} {'median':>8} {'p25':>7} {'p75':>7} {'n':>6} {'distr':>6} {'sqft':>6}")
    for lab, d in (r.get("gradient") or {}).items():
        flag = "" if d.get("feasible") else "   INFEASIBLE — below a pre-registered floor"
        print(f"  {lab:>7} {d['median']:>+7.1f}% {d['p25']:>+6.1f} {d['p75']:>+6.1f} "
              f"{d['n']:>6} {d['districts']:>6} {d['median_sqft']:>6}{flag}")

    print("\nPRE-REGISTERED PREDICTION — stated 2026-08-10 before this run:")
    ph = r.get("prediction_held") or {}
    for k, v in ph.items():
        mark = {True: "HELD", False: "FAILED", None: "not assessable"}.get(v, str(v))
        print(f"  {k:<28} {mark}")
    print(f"  zero crossing measured at age {r.get('zero_crossing_age')}"
          f"   (predicted 11-15)")
    print(f"  monotone decreasing: {r.get('monotone_decreasing')}")

    by = r.get("gradient_by_year") or {}
    if by:
        print("\nRISK 3 GUARD — same gradient computed per calendar year. If the shape is stable")
        print("         across years, a pure cohort story is harder to sustain.")
        labs = sorted({l for row in by.values() for l in row},
                      key=lambda x: int(x.split("-")[0].rstrip("+")))
        print(f"  {'year':>6}" + "".join(f"{l:>9}" for l in labs))
        for y in sorted(by):
            print(f"  {y:>6}" + "".join(
                (f"{by[y][l]:>+8.1f}%" if l in by[y] else f"{'.':>9}") for l in labs))

    print("\ncoverage:", json.dumps(r.get("coverage"), indent=2))
    print("\nceiling:", r.get("_ceiling"))
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
