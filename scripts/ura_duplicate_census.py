#!/usr/bin/env python3
"""Census of exact duplicate records in the two URA Data Service feeds this repo reads.

WHY. The free PMI_Resi_Transaction feed can carry one caveat as two or three records that are
identical on every field, so a count built on the raw feed is overstated while URA's own
published counts are not. This repo had never de-duplicated. Before a de-duplication step is
assumed to matter for every property type, this measures it: how many exact duplicates the
feed carries, by property type and by sale type, and the same for the rental feed.

Two keys are counted, because they answer different questions:
  full   the project name and street plus every field URA puts on the record. Two records equal
         on this key are the same caveat served twice; nothing a buyer would call two
         transactions can collide on it.
  nine   project, street, propertyType, tenure, area, price, contractDate, typeOfSale, district.
         It omits floorRange, typeOfArea, noOfUnits and nettPrice, so for non-landed stock two
         different units on different floors at the same size and price in the same month
         collide on it. The gap between the two counts is what a nine-field de-duplication
         would remove beyond the exact duplicates.

Runs in CI only: URA_ACCESS_KEY is a repository secret and never leaves GitHub. Read-only
against URA; commits nothing. Aggregate counts only, no record is printed.

    URA_ACCESS_KEY=... python scripts/ura_duplicate_census.py --out census.json
"""
import argparse, collections, datetime, json, os, pathlib, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import fetch_data as F

NINE_FIELDS = ("propertyType", "tenure", "area", "price", "contractDate", "typeOfSale", "district")
SALE = {"1": "1 new sale", "2": "2 sub-sale", "3": "3 resale"}


def key_full(proj, rec):
    return (str(proj.get("project")), str(proj.get("street")),
            tuple(sorted((str(k), str(v)) for k, v in rec.items())))


def key_nine(proj, rec):
    return (str(proj.get("project")), str(proj.get("street"))) + tuple(str(rec.get(k)) for k in NINE_FIELDS)


def category(pt):
    """Roll URA's propertyType labels up to the groups the tool and the studies use."""
    lt = F._landed_type(pt)
    if lt == "Strata":
        return "strata landed"
    if lt:
        return "landed (non-strata)"
    if pt in ("Condominium", "Apartment"):
        return "condominium / apartment"
    if pt == "Executive Condominium":
        return "executive condominium"
    return "other"


def census_transactions(projs):
    recs, full, months = [], collections.Counter(), []
    for proj in projs:
        for t in proj.get("transaction", []) or []:
            kf = key_full(proj, t)
            full[kf] += 1
            recs.append((str(t.get("propertyType")), str(t.get("typeOfSale", "")).strip(), kf, key_nine(proj, t)))
            mi = F._midx(t.get("contractDate", ""))
            if mi:
                months.append(mi)
    cells = collections.defaultdict(lambda: {"records": 0, "dup_full": 0, "dup_nine": 0})
    seen_f, seen_n = set(), set()
    groups_by_cat = collections.defaultdict(collections.Counter)
    for pt, sale, kf, kn in recs:
        c = cells[(pt, sale)]
        c["records"] += 1
        if kf in seen_f:
            c["dup_full"] += 1
        else:
            seen_f.add(kf)
            if full[kf] > 1:
                groups_by_cat[category(pt)][full[kf]] += 1
        if kn in seen_n:
            c["dup_nine"] += 1
        else:
            seen_n.add(kn)

    def rollup(pred):
        out = {"records": 0, "dup_full": 0, "dup_nine": 0}
        for (pt, sale), c in cells.items():
            if pred(pt, sale):
                for k in out:
                    out[k] += c[k]
        out["rate_full"] = round(out["dup_full"] / out["records"], 4) if out["records"] else None
        out["rate_nine"] = round(out["dup_nine"] / out["records"], 4) if out["records"] else None
        return out

    def fmt_month(mi):
        return f"{(mi - 1) // 12}-{(mi - 1) % 12 + 1:02d}"   # month index = year*12 + month, months 1-indexed

    cats = sorted({category(pt) for pt, _s in cells})
    sales = sorted({s for _pt, s in cells})
    return {
        "window": {"from": fmt_month(min(months)), "to": fmt_month(max(months))} if months else None,
        "total": rollup(lambda pt, s: True),
        "by_category": {cat: rollup(lambda pt, s, cat=cat: category(pt) == cat) for cat in cats},
        "by_category_and_sale": {f"{cat} | {SALE.get(sale, sale)}":
                                 rollup(lambda pt, s, cat=cat, sale=sale: category(pt) == cat and s == sale)
                                 for cat in cats for sale in sales},
        "by_property_type_and_sale": {f"{pt} | {SALE.get(sale, sale)}": {
                                          **c, "rate_full": round(c["dup_full"] / c["records"], 4),
                                          "rate_nine": round(c["dup_nine"] / c["records"], 4)}
                                      for (pt, sale), c in sorted(cells.items())},
        "duplicate_group_sizes_full_key": {cat: {str(size): n for size, n in sorted(g.items())}
                                           for cat, g in sorted(groups_by_cat.items())},
    }


def census_rentals(rentals):
    full, recs = collections.Counter(), []
    for proj in rentals:
        for c in proj.get("rental", []) or []:
            kf = key_full(proj, c)
            full[kf] += 1
            recs.append((str(c.get("propertyType")), kf))
    cells, seen = collections.defaultdict(lambda: {"records": 0, "dup_full": 0}), set()
    for pt, kf in recs:
        cells[category(pt)]["records"] += 1
        if kf in seen:
            cells[category(pt)]["dup_full"] += 1
        else:
            seen.add(kf)
    for c in cells.values():
        c["rate_full"] = round(c["dup_full"] / c["records"], 4) if c["records"] else None
    tot = {"records": sum(c["records"] for c in cells.values()),
           "dup_full": sum(c["dup_full"] for c in cells.values())}
    tot["rate_full"] = round(tot["dup_full"] / tot["records"], 4) if tot["records"] else None
    return {"total": tot, "by_category": dict(sorted(cells.items())),
            "periods": F._rental_periods(datetime.date.today())}


def pct(x):
    return "n/a" if x is None else f"{x:.1%}"


def markdown(report):
    tx, rt = report["transactions"], report["rentals"]
    L = [f"## URA duplicate census — {report['run_at']}", "",
         f"PMI_Resi_Transaction, contract months {tx['window']['from']} to {tx['window']['to']}. "
         "`dup` = records beyond the first in each group of identical records; `full` key = project, "
         "street and every field on the record; `nine` key = project, street, propertyType, tenure, "
         "area, price, contractDate, typeOfSale, district.", "",
         "| Category | Sale type | Records | Dup (full) | Rate | Dup (nine) | Rate |",
         "|---|---|---:|---:|---:|---:|---:|"]
    for cat, c in tx["by_category"].items():
        L.append(f"| **{cat}** | all | {c['records']:,} | {c['dup_full']:,} | {pct(c['rate_full'])} | "
                 f"{c['dup_nine']:,} | {pct(c['rate_nine'])} |")
        for k, cs in tx["by_category_and_sale"].items():
            if k.startswith(cat + " | ") and cs["records"]:
                L.append(f"| {cat} | {k.split(' | ')[1]} | {cs['records']:,} | {cs['dup_full']:,} | "
                         f"{pct(cs['rate_full'])} | {cs['dup_nine']:,} | {pct(cs['rate_nine'])} |")
    t = tx["total"]
    L.append(f"| **all** | all | {t['records']:,} | {t['dup_full']:,} | {pct(t['rate_full'])} | "
             f"{t['dup_nine']:,} | {pct(t['rate_nine'])} |")
    L += ["", "Duplicate group sizes on the full key (groups, by category):", ""]
    for cat, g in tx["duplicate_group_sizes_full_key"].items():
        L.append(f"- {cat}: " + ", ".join(f"{n:,} groups of {size}" for size, n in g.items()))
    L += ["", "By URA propertyType and sale type:", "",
          "| propertyType | Sale type | Records | Dup (full) | Rate | Dup (nine) | Rate |",
          "|---|---|---:|---:|---:|---:|---:|"]
    for k, c in tx["by_property_type_and_sale"].items():
        pt, sale = k.split(" | ")
        L.append(f"| {pt} | {sale} | {c['records']:,} | {c['dup_full']:,} | {pct(c['rate_full'])} | "
                 f"{c['dup_nine']:,} | {pct(c['rate_nine'])} |")
    L += ["", f"PMI_Resi_Rental, reference quarters {', '.join(rt['periods'])} (full key only):", "",
          "| Category | Records | Dup (full) | Rate |", "|---|---:|---:|---:|"]
    for cat, c in rt["by_category"].items():
        L.append(f"| {cat} | {c['records']:,} | {c['dup_full']:,} | {pct(c['rate_full'])} |")
    L.append(f"| **all** | {rt['total']['records']:,} | {rt['total']['dup_full']:,} | {pct(rt['total']['rate_full'])} |")
    return "\n".join(L) + "\n"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="ura_duplicate_census.json")
    args = ap.parse_args()
    key = os.environ.get("URA_ACCESS_KEY")
    if not key:
        sys.exit("URA_ACCESS_KEY is not set; this census runs in CI, where the key is a repository secret.")
    projs = F._ura_projects_raw(key)
    rentals = F._ura_rentals_raw(key)
    report = {"run_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "source": "URA Data Service PMI_Resi_Transaction (4 batches) and PMI_Resi_Rental "
                        "(4 reference quarters), as served, before any cleaning",
              "transactions": census_transactions(projs), "rentals": census_rentals(rentals)}
    md = markdown(report)
    print(md)
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as fh:
            fh.write(md)
    pathlib.Path(args.out).write_text(json.dumps(report, indent=1), encoding="utf-8")
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
