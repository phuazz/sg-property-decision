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


def developer_sales_crosscheck(projs, launches):
    """Are identical new-sale records one sale served twice, or several identical units sold?

    URA's developer-sales feed counts UNITS sold to date per project from developers' returns
    (Options to Purchase), independently of caveats. For a project whose first new-sale caveat
    falls well inside the transaction window, every unit it has sold is inside the window too,
    so its new-sale caveat count has a ceiling: it cannot legitimately exceed units sold. If the
    raw count exceeds that ceiling and the de-duplicated count sits under it, the duplicates are
    an artefact; if the raw count already sits at or under it, they are distinct sales.
    """
    if not launches or not launches.get("rows"):
        return {"available": False}
    months = [F._midx(t.get("contractDate", "")) for p in projs for t in p.get("transaction", []) or []]
    months = [m for m in months if m]
    window_start = min(months)
    by = {}
    for proj in projs:
        name = str(proj.get("project") or "").strip().upper()
        c = by.setdefault(name, {"raw": 0, "keys": set(), "first": None, "last": None})
        for t in proj.get("transaction", []) or []:
            if str(t.get("typeOfSale", "")).strip() != "1":
                continue
            c["raw"] += 1
            c["keys"].add(key_full(proj, t))
            mi = F._midx(t.get("contractDate", ""))
            if mi:
                c["first"] = mi if c["first"] is None else min(c["first"], mi)
                c["last"] = mi if c["last"] is None else max(c["last"], mi)

    def fmt(mi):
        return None if mi is None else f"{(mi - 1) // 12}-{(mi - 1) % 12 + 1:02d}"

    rows = []
    for p in launches["rows"]:
        c = by.get(str(p.get("project") or "").strip().upper())
        if not c or not c["raw"] or not p.get("sold"):
            continue
        dedup = len(c["keys"])
        rows.append({"project": p["project"], "launched": p.get("units"), "sold_to_date": p["sold"],
                     "caveats_raw": c["raw"], "caveats_dedup": dedup,
                     "first_new_sale": fmt(c["first"]), "last_new_sale": fmt(c["last"]),
                     "in_window_launch": c["first"] >= window_start + 3,
                     "raw_over_sold": round(c["raw"] / p["sold"], 3), "dedup_over_sold": round(dedup / p["sold"], 3)})
    inw = [r for r in rows if r["in_window_launch"]]
    agg = {"projects_matched": len(rows), "in_window_launches": len(inw),
           "sum_sold_to_date": sum(r["sold_to_date"] for r in inw),
           "sum_caveats_raw": sum(r["caveats_raw"] for r in inw),
           "sum_caveats_dedup": sum(r["caveats_dedup"] for r in inw),
           "projects_raw_above_sold": sum(1 for r in inw if r["caveats_raw"] > r["sold_to_date"]),
           "projects_dedup_above_sold": sum(1 for r in inw if r["caveats_dedup"] > r["sold_to_date"])}
    if agg["sum_sold_to_date"]:
        agg["raw_over_sold"] = round(agg["sum_caveats_raw"] / agg["sum_sold_to_date"], 3)
        agg["dedup_over_sold"] = round(agg["sum_caveats_dedup"] / agg["sum_sold_to_date"], 3)
    return {"available": True, "developer_sales_asof": launches.get("asof"), "window_start": fmt(window_start),
            "aggregate": agg, "projects": sorted(rows, key=lambda r: -r["sold_to_date"])}


def quarterly_counts(projs):
    """Condominium/apartment new sales and resales per contract quarter, raw and de-duplicated on the
    full key, for comparison with the counts URA publishes each quarter."""
    raw, keys = collections.Counter(), collections.defaultdict(set)
    for proj in projs:
        for t in proj.get("transaction", []) or []:
            if t.get("propertyType") not in ("Condominium", "Apartment"):
                continue
            mi = F._midx(t.get("contractDate", ""))
            sale = str(t.get("typeOfSale", "")).strip()
            if not mi or sale not in ("1", "3"):
                continue
            q = f"{(mi - 1) // 12}-Q{((mi - 1) % 12) // 3 + 1}"
            raw[(q, sale)] += 1
            keys[(q, sale)].add(key_full(proj, t))
    out = {}
    for (q, sale), n in sorted(raw.items()):
        out.setdefault(q, {})[SALE[sale]] = {"raw": n, "dedup_full": len(keys[(q, sale)])}
    return out


def rental_quarterly_counts(rentals):
    """Rental contracts per reference quarter (leaseDate), landed against the rest, raw and de-duplicated."""
    raw, keys = collections.Counter(), collections.defaultdict(set)
    for proj in rentals:
        for c in proj.get("rental", []) or []:
            mi = F._midx(c.get("leaseDate", ""))
            if not mi:
                continue
            q = f"{(mi - 1) // 12}-Q{((mi - 1) % 12) // 3 + 1}"
            cat = "landed (non-strata)" if category(str(c.get("propertyType"))) == "landed (non-strata)" else "other"
            raw[(q, cat)] += 1
            keys[(q, cat)].add(key_full(proj, c))
    out = {}
    for (q, cat), n in sorted(raw.items()):
        out.setdefault(q, {})[cat] = {"raw": n, "dedup_full": len(keys[(q, cat)])}
    return out


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

    x = report.get("developer_sales_crosscheck") or {}
    if x.get("available"):
        a = x["aggregate"]
        L += ["", f"### New-sale caveats against URA developer sales (units sold to date, file {x['developer_sales_asof']})", "",
              f"Transaction window opens {x['window_start']}; an in-window launch has its first new-sale caveat at least "
              f"three months later, so all its sales are inside the window. {a['projects_matched']} selling projects matched "
              f"by name, {a['in_window_launches']} launched in-window.", "",
              f"- in-window launches: units sold to date {a['sum_sold_to_date']:,}; new-sale caveats raw {a['sum_caveats_raw']:,} "
              f"({a.get('raw_over_sold')} of units sold), de-duplicated {a['sum_caveats_dedup']:,} ({a.get('dedup_over_sold')})",
              f"- projects whose RAW caveat count exceeds units sold: {a['projects_raw_above_sold']}; after de-duplication: {a['projects_dedup_above_sold']}",
              "", "| Project | Launched | Sold to date | Caveats raw | Caveats dedup | First new sale | In-window | raw/sold | dedup/sold |",
              "|---|---:|---:|---:|---:|---|---|---:|---:|"]
        for r in x["projects"]:
            L.append(f"| {r['project']} | {r['launched'] if r['launched'] is not None else '—'} | {r['sold_to_date']:,} | {r['caveats_raw']:,} | "
                     f"{r['caveats_dedup']:,} | {r['first_new_sale']} | {'yes' if r['in_window_launch'] else 'no'} | "
                     f"{r['raw_over_sold']} | {r['dedup_over_sold']} |")
    else:
        L += ["", "Developer-sales cross-check unavailable this run."]

    L += ["", "### Condominium / apartment counts by contract quarter, raw and de-duplicated (full key)", "",
          "| Quarter | New sale raw | New sale dedup | Resale raw | Resale dedup |", "|---|---:|---:|---:|---:|"]
    for q, d in report["quarterly_counts"].items():
        n, r = d.get("1 new sale", {}), d.get("3 resale", {})
        L.append(f"| {q} | {n.get('raw', 0):,} | {n.get('dedup_full', 0):,} | {r.get('raw', 0):,} | {r.get('dedup_full', 0):,} |")
    L += ["", "### Rental contracts by reference quarter, raw and de-duplicated (full key)", "",
          "| Quarter | Landed raw | Landed dedup | Other raw | Other dedup |", "|---|---:|---:|---:|---:|"]
    for q, d in report["rental_quarterly_counts"].items():
        l, o = d.get("landed (non-strata)", {}), d.get("other", {})
        L.append(f"| {q} | {l.get('raw', 0):,} | {l.get('dedup_full', 0):,} | {o.get('raw', 0):,} | {o.get('dedup_full', 0):,} |")
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
    try:
        launches = F.ura_new_launches()      # developer sales: units sold to date per selling project
        if launches and launches.get("error"):
            print(f"  note: developer-sales feed unavailable ({launches['error']})")
            launches = None
    except Exception as e:
        print(f"  note: developer-sales feed unavailable ({e!r})")
        launches = None
    report = {"run_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
              "source": "URA Data Service PMI_Resi_Transaction (4 batches) and PMI_Resi_Rental "
                        "(4 reference quarters), as served, before any cleaning",
              "transactions": census_transactions(projs), "rentals": census_rentals(rentals),
              "developer_sales_crosscheck": developer_sales_crosscheck(projs, launches),
              "quarterly_counts": quarterly_counts(projs),
              "rental_quarterly_counts": rental_quarterly_counts(rentals)}
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
