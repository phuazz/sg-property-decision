#!/usr/bin/env python3
"""Tests for fetch_data.dedup_records - the step that drops exact duplicate LANDED records from the
URA transaction and rental feeds before anything in live.json is counted.

The step is a pure function over URA-shaped records, so this runs with no key and no network.
It pins: an exact duplicate of a landed house (the project's name and street plus every field on
the record) is dropped and counted; a landed record that differs on any field is a different
house and is kept; the first of each identical group survives and order is preserved; a project
served as two objects under one name still de-duplicates across them; identical NON-landed
records are left in place and counted as left, because the census showed them to be distinct
sales; strata landed is outside the scope; the input is not mutated; the stats shape that
live.json._meta.dedup carries; and the wiring - the cached _ura_projects and the rental pull both
run the step, and the landed summary counts the de-duplicated feed.

Then the guard is verified by making it fail, as every guard in this repo is. Three mutations are
applied in-process and the SAME checks are re-run under each; the suite passes only if every
mutation is caught:
  keep-duplicates   the record key never collides, so nothing is removed
  scope-all         the removal applies to every record, so identical condominium sales vanish
  coarse-key        the key drops a field (area), so two houses that differ only there collapse

Usage: python scripts/test_dedup.py                       # exit 0 = pass
       python scripts/test_dedup.py --mutate keep-duplicates    # run the checks under one mutation and
       python scripts/test_dedup.py --mutate scope-all          #   watch them go red (exit 1); exit 2 means
       python scripts/test_dedup.py --mutate coarse-key         #   the mutation was NOT caught
"""
import sys, os, copy, datetime, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import fetch_data as F

RUN = datetime.date(2026, 10, 4)      # Python dates: months are 1-indexed; the fixture's month is 0926


def tx(pt, price, floor="-", area=150.0, sale="3", mmyy="0926", tenure="Freehold", toa="Land", district="15"):
    return {"propertyType": pt, "contractDate": mmyy, "price": str(price), "typeOfSale": sale,
            "area": str(area), "typeOfArea": toa, "tenure": tenure, "district": district,
            "floorRange": floor, "noOfUnits": "1", "nettPrice": "-"}


def fixture():
    """ONE HOUSE: three terrace resales, the first served twice; two detached houses that differ
    only in land area; a condominium unit served twice (two mirror-image units, two sales); a
    strata terrace served twice. TWO HOUSE: one street served as two objects, each carrying the
    same detached resale once."""
    a = tx("Terrace House", 3_000_000)
    b = tx("Terrace House", 3_200_000)
    c = tx("Terrace House", 3_400_000)
    d1 = tx("Detached House", 9_000_000, area=400.0)
    d2 = dict(d1, area="420.0")
    condo = tx("Condominium", 1_500_000, floor="06-10", area=90.0, toa="Strata", tenure="99 yrs lease commencing from 2015")
    strata = tx("Strata Terrace", 2_500_000, area=200.0, toa="Strata", tenure="99 yrs lease commencing from 2010")
    e = tx("Detached House", 12_000_000, area=600.0)
    return [
        {"project": "ONE HOUSE", "street": "ONE ROAD", "marketSegment": "OCR", "x": "1", "y": "1",
         "transaction": [a, dict(a), b, d1, d2, condo, dict(condo), strata, dict(strata), c]},
        {"project": "TWO HOUSE", "street": "TWO ROAD", "marketSegment": "OCR", "x": "2", "y": "2",
         "transaction": [e]},
        {"project": "TWO HOUSE", "street": "TWO ROAD", "marketSegment": "OCR", "x": "2", "y": "2",
         "transaction": [dict(e)]},
    ]


def rental_fixture():
    house = {"areaSqm": "150-200", "leaseDate": "0926", "propertyType": "Terrace House",
             "district": "15", "areaSqft": "1600-2200", "noOfBedRoom": "4", "rent": "8000"}
    flat = {"areaSqm": "90-100", "leaseDate": "0926", "propertyType": "Non-landed Properties",
            "district": "15", "areaSqft": "1000-1100", "noOfBedRoom": "3", "rent": "5000"}
    return [{"project": "ONE HOUSE", "street": "ONE ROAD", "rental": [house, dict(house), dict(house, rent="8200"), flat, dict(flat)]}]


def run_checks():
    """Every assertion, as a list of failure strings. Run intact, then under each mutation."""
    fails = []

    def eq(label, got, want):
        if got != want:
            fails.append(f"{label}: got {got!r}, want {want!r}")

    fx = fixture()
    before = copy.deepcopy(fx)
    clean, st = F.dedup_records(fx, "transaction")

    eq("records counted", st["records"], 12)
    eq("landed records in scope", st["in_scope"], 8)
    eq("landed exact duplicates removed", st["removed"], 2)
    eq("kept = records - removed", st["kept"], 10)
    eq("rate on the in-scope records", st["rate_in_scope"], round(2 / 8, 4))
    eq("ONE HOUSE keeps nine records", len(clean[0]["transaction"]), 9)
    eq("the first of an identical pair survives, order preserved",
       [t["price"] for t in clean[0]["transaction"]],
       ["3000000", "3200000", "9000000", "9000000", "1500000", "1500000", "2500000", "2500000", "3400000"])
    eq("two houses differing only in land area are both kept",
       sorted(t["area"] for t in clean[0]["transaction"] if t["propertyType"] == "Detached House"), ["400.0", "420.0"])
    eq("identical condominium records are distinct sales and are kept",
       sum(1 for t in clean[0]["transaction"] if t["propertyType"] == "Condominium"), 2)
    eq("strata landed is outside the scope and is kept",
       sum(1 for t in clean[0]["transaction"] if t["propertyType"] == "Strata Terrace"), 2)
    eq("identical records left in place are counted", st["identical_left_in_place"], 2)
    eq("duplicates across two objects of one project are removed", [len(p["transaction"]) for p in clean[1:]], [1, 0])
    eq("input not mutated", fx, before)
    eq("groups by size", st["duplicate_groups_by_size"], {"2": 2})
    eq("removed by property type", st["removed_by_property_type"], {"Terrace House": 1, "Detached House": 1})
    for k in ("records", "in_scope", "removed", "kept", "rate_in_scope", "identical_left_in_place",
              "duplicate_groups_by_size", "removed_by_property_type", "scope", "key"):
        if k not in st:
            fails.append(f"stats carry {k}")
    eq("empty feed", F.dedup_records([], "transaction")[1]["removed"], 0)

    # The rental feed runs the same step, same scope, on its own list name.
    rclean, rst = F.dedup_records(rental_fixture(), "rental")
    eq("rental: the landed exact duplicate is removed", rst["removed"], 1)
    eq("rental: the contract differing in rent is kept, identical flats are kept", len(rclean[0]["rental"]), 4)
    eq("rental: identical non-landed rows counted as left", rst["identical_left_in_place"], 1)

    # Wiring: the aggregations read the cached, de-duplicated feed, and the stats reach _DEDUP.
    F._URA_PROJECTS = None
    F._DEDUP.clear()
    saved_raw, saved_rent, saved_env = F._ura_projects_raw, F._ura_rentals_raw, os.environ.get("URA_ACCESS_KEY")
    F._ura_projects_raw = lambda key: fixture()
    F._ura_rentals_raw = lambda key: rental_fixture()
    os.environ["URA_ACCESS_KEY"] = "fixture"
    try:
        projs = F._ura_projects("fixture")
        eq("_ura_projects serves the de-duplicated feed", sum(len(p["transaction"]) for p in projs), 10)
        eq("_ura_projects records its stats", F._DEDUP.get("transactions", {}).get("removed"), 2)
        land = F._landed_summary(projs, RUN)
        eq("landed summary counts three terraces, not four", land["by_type"]["Terrace"]["n"], 3)
        eq("landed summary counts three detached, not four", land["by_type"]["Detached"]["n"], 3)
        eq("landed summary still counts both strata records", land["n_strata_excluded"], 2)
        F._district_rent_psf("fixture")
        eq("the rental pull records its stats", F._DEDUP.get("rentals", {}).get("removed"), 1)
    finally:
        F._ura_projects_raw, F._ura_rentals_raw = saved_raw, saved_rent
        F._URA_PROJECTS = None
        F._DEDUP.clear()
        if saved_env is None:
            os.environ.pop("URA_ACCESS_KEY", None)
        else:
            os.environ["URA_ACCESS_KEY"] = saved_env
    return fails


def _coarse_key(proj, rec):
    return (str(proj.get("project")), str(proj.get("street")),
            tuple(sorted((str(k), str(v)) for k, v in rec.items() if k != "area")))


MUTATIONS = {
    # the key never collides, so the step keeps every record
    "keep-duplicates": ("_record_key", lambda proj, rec: object()),
    # the removal applies to every record, so identical condominium sales vanish
    "scope-all": ("_dedup_applies", lambda rec: True),
    # the key drops a field, so two houses that differ only there read as one
    "coarse-key": ("_record_key", _coarse_key),
}


def run_mutated(name):
    attr, mut = MUTATIONS[name]
    original = getattr(F, attr)
    setattr(F, attr, mut)
    try:
        return run_checks()
    finally:
        setattr(F, attr, original)


def main():
    args = sys.argv[1:]
    if "--mutate" in args:
        name = args[args.index("--mutate") + 1]
        fails = run_mutated(name)
        print(f"mutation {name}: {len(fails)} check(s) fail" + ("" if fails else " - the guard did NOT catch it"))
        for f in fails:
            print("  - " + f)
        return 1 if fails else 2

    fails = run_checks()
    caught = []
    for name in MUTATIONS:
        mf = run_mutated(name)
        if mf:
            caught.append(f"{name} ({len(mf)} checks fail)")
        else:
            fails.append(f"mutation {name} NOT caught - the de-duplication guard is not load-bearing")
    if fails:
        print(f"FAIL ({len(fails)}):")
        for f in fails:
            print("  - " + f)
        return 1
    print("ok dedup: landed exact duplicates dropped and counted, near-duplicates kept, identical non-landed "
          "records kept and counted, strata out of scope, cross-object, order, rentals, wiring into "
          "_ura_projects / _district_rent_psf / landed summary; mutations caught: " + "; ".join(caught))
    return 0


if __name__ == "__main__":
    sys.exit(main())
