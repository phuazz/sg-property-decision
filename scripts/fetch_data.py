#!/usr/bin/env python3
"""Fetch live public data into data/live.json (overlaid on the curated market.json by pipeline.py).

No-auth feeds (refresh automatically, incl. in CI):
  - URA Private Residential Property Price Index (All Residential)      data.gov.sg
  - URA PPI by market segment (CCR / RCR / OCR, non-landed)             data.gov.sg
  - HDB Resale Price Index                                             data.gov.sg
  - HDB resale transactions -> latest-month median price & $psf         data.gov.sg
  - Government Land Sales awards (land $psf ppr + bids)                 URA Past-Sale-Sites .xlsx

Key-gated feeds (skip cleanly unless the secret is present):
  - URA private transactions -> official segment median condo $psf      env URA_ACCESS_KEY

Every feed is wrapped so one failure does not abort the others; failures are
recorded in live.json._meta.errors so a partial refresh is transparent.
Usage: python scripts/fetch_data.py
"""
import io, os, re, sys, json, time, statistics, datetime, pathlib
import requests

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "live.json"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) sg-property-decision/1.0"}
DG = "https://data.gov.sg/api/action/datastore_search"

def GET(url, headers=None, timeout=45, tries=4):
    """requests.get with backoff on 429 / 5xx (data.gov.sg rate-limits datacentre IPs)."""
    last = None
    for i in range(tries):
        r = requests.get(url, headers=headers or UA, timeout=timeout)
        if r.status_code in (429, 502, 503, 504):
            last = r
            if i < tries - 1:
                time.sleep(2 * (i + 1) + 1)
                continue
        r.raise_for_status()
        return r
    last.raise_for_status()
    return last

def qkey(q):
    y, qq = q.split("-Q"); return int(y) * 4 + int(qq)

def qoq(path):
    return round(path[-1][1] / path[-2][1] - 1, 4) if len(path) >= 2 else None

def yoy(path):
    return round(path[-1][1] / path[-5][1] - 1, 4) if len(path) >= 5 else None

def dg_all(rid, limit=3000):
    return GET(f"{DG}?resource_id={rid}&limit={limit}").json()["result"]["records"]

def dg_tail(rid, n=4000):
    """Last n records (highest _id = most recent). datastore_search returns the
    first rows by default, so page to the tail via offset to get current months.
    n=4000 covers ~1.5 months of HDB resales (kept modest to avoid 429s in CI)."""
    total = GET(f"{DG}?resource_id={rid}&limit=1", timeout=30).json()["result"]["total"]
    off = max(0, total - n)
    return GET(f"{DG}?resource_id={rid}&limit={n}&offset={off}", timeout=60).json()["result"]["records"]

# ---- planning area -> market segment (for GLS colouring) ----
# Approximation: URA defines CCR by postal district (9/10/11 + Downtown Core + Sentosa),
# not by planning area. Bukit Timah PA spans CCR districts (10/11) and OCR (21) but is
# tagged RCR here; the page flags segment tags as approximate for this reason.
CCR = {"downtown core","orchard","newton","river valley","rochor","museum","singapore river",
       "marina south","straits view","tanglin","marina east"}
RCR = {"kallang","geylang","queenstown","bukit merah","toa payoh","marine parade","novena",
       "bishan","southern islands","outram","bukit timah"}
def region_of(pa):
    p = (pa or "").strip().lower()
    if p in CCR: return "CCR"
    if p in RCR: return "RCR"
    return "OCR"

def ura_ppi():
    recs = dg_all("d_97f8a2e995022d311c6c68cfda6d034c")
    allr = sorted([r for r in recs if r["property_type"] == "All Residential"], key=lambda r: qkey(r["quarter"]))
    path = [(r["quarter"], float(r["index"])) for r in allr][-9:]
    return {"label": "URA Private Residential PPI (All Residential)", "base": "2009-Q1=100",
            "level": path[-1][1], "level_asof": path[-1][0], "yoy": yoy(path), "qoq": qoq(path),
            "q_path": [{"q": q, "index": v} for q, v in path],
            "source": "data.gov.sg d_97f8a2e9 (URA)"}

def hdb_rpi():
    recs = dg_all("d_14f63e595975691e7c24a27ae4c07c79")
    path = [(r["quarter"], float(r["index"])) for r in sorted(recs, key=lambda r: qkey(r["quarter"]))][-9:]
    return {"label": "HDB Resale Price Index", "base": "2009-Q1=100",
            "level": path[-1][1], "level_asof": path[-1][0], "yoy": yoy(path), "qoq": qoq(path),
            "q_path": [{"q": q, "index": v} for q, v in path],
            "source": "data.gov.sg d_14f63e59 (HDB)"}

def ura_locality():
    recs = dg_all("d_f65e490a8ad430f60a9a3d9df2bff2a0")
    name = {"Core Central Region": "CCR", "Rest of Central Region": "RCR", "Outside Central Region": "OCR"}
    out = {}
    for seg_long, seg in name.items():
        rows = sorted([r for r in recs if r["market_segment"] == seg_long], key=lambda r: qkey(r["quarter"]))
        path = [(r["quarter"], float(r["price_index"])) for r in rows][-5:]
        out[seg] = {"level": path[-1][1], "asof": path[-1][0], "qoq": qoq(path), "yoy_est": yoy(path)}
    out["_source"] = "data.gov.sg d_f65e490a (URA non-landed by segment)"
    return out

def hdb_resale():
    recs = dg_tail("d_8b84c4ee58e3cfc0ece0d773c8ca6abc", 4000)
    latest = max(r["month"] for r in recs)
    cur = [r for r in recs if r["month"] == latest]
    def psf(r):
        area = float(r["floor_area_sqm"]) * 10.7639
        return float(r["resale_price"]) / area if area else None
    prices = [float(r["resale_price"]) for r in cur]
    psfs = [p for p in (psf(r) for r in cur) if p]
    by_type = {}
    for t in sorted(set(r["flat_type"] for r in cur)):
        tp = [float(r["resale_price"]) for r in cur if r["flat_type"] == t]
        by_type[t] = {"n": len(tp), "median_price": round(statistics.median(tp))}
    return {"asof_month": latest, "n": len(cur),
            "median_price": round(statistics.median(prices)),
            "median_psf": round(statistics.median(psfs)),
            "by_type": by_type, "source": "data.gov.sg d_8b84c4ee (HDB resale register)"}

def gls():
    page = GET("https://www.ura.gov.sg/Corporate/Land-Sales/Past-Sale-Sites").text
    href = re.findall(r'href="([^"]+Vacant Sites[^"]*\.xlsx[^"]*)"', page)
    if not href:
        raise RuntimeError("GLS xlsx href not found on Past-Sale-Sites page")
    import pandas as pd
    xb = GET(href[0].replace(" ", "%20"), timeout=90).content
    df = pd.read_excel(io.BytesIO(xb), sheet_name=0, header=0)
    df.columns = [str(c).split("\n")[0].strip() for c in df.columns]
    df = df.rename(columns={"Successful Tender Price": "price",
                            "$psm per GFA or $psm per GPR": "psm", "No. of Bids": "bids",
                            "Date of Award": "award", "Name of Successful Tenderer": "tenderer",
                            "Planning Area": "pa", "Type of Development Allowed": "use"})
    df = df[df["use"].astype(str).str.contains("Residential", case=False, na=False)].copy()
    df["award"] = pd.to_datetime(df["award"], errors="coerce")
    df = df.dropna(subset=["award", "psm"])
    df["year"] = df["award"].dt.year
    df["psf_ppr"] = (df["psm"].astype(float) / 10.7639).round(0)
    cur_yr = int(df["year"].max())
    avg_cur = df[df["year"] == cur_yr]["psf_ppr"].mean()
    avg_prev = df[df["year"] == cur_yr - 1]["psf_ppr"].mean()
    recent = df.sort_values("award").tail(10).iloc[::-1]
    tenders = [{"site": str(r["Location"]), "pa": str(r["pa"]), "region": region_of(r["pa"]),
                "close": r["award"].strftime("%Y-%m"), "psf_ppr": int(r["psf_ppr"]),
                "bids": int(r["bids"]) if str(r["bids"]).replace(".0", "").isdigit() else None,
                "tenderer": str(r["tenderer"])[:60]} for _, r in recent.iterrows()]
    return {"tenders_recent": tenders, "avg_psf_ppr_year": {str(cur_yr): round(float(avg_cur)),
            str(cur_yr - 1): round(float(avg_prev))}, "yoy": round(float(avg_cur / avg_prev - 1), 3),
            "asof": recent.iloc[0]["award"].strftime("%Y-%m-%d"),
            "source": "URA Past-Sale-Sites .xlsx (residential awards)"}

def ura_transactions():
    key = os.environ.get("URA_ACCESS_KEY")
    if not key:
        return None
    tok = GET("https://eservice.ura.gov.sg/uraDataService/insertNewToken/v1",
              headers={**UA, "AccessKey": key}, timeout=30).json().get("Result")
    hdr = {**UA, "AccessKey": key, "Token": tok}
    seg_psf = {"CCR": [], "RCR": [], "OCR": []}
    seg_map = {"CCR": "CCR", "RCR": "RCR", "OCR": "OCR"}
    for batch in (1, 2, 3, 4):
        j = GET(f"https://eservice.ura.gov.sg/uraDataService/invokeUraDS/v1?service=PMI_Resi_Transaction&batch={batch}",
                headers=hdr, timeout=60).json()
        for proj in j.get("Result", []):
            seg = seg_map.get(proj.get("marketSegment"))
            if not seg: continue
            for t in proj.get("transaction", []):
                if t.get("propertyType") not in ("Condominium", "Apartment"): continue
                try:
                    area = float(t["area"]) * 10.7639
                    if area: seg_psf[seg].append(float(t["price"]) / area)
                except (KeyError, ValueError, ZeroDivisionError):
                    pass
    out = {s: {"median_psf": round(statistics.median(v)), "n": len(v)} for s, v in seg_psf.items() if v}
    out["_source"] = "URA Data Service PMI_Resi_Transaction (rolling 5y, condo/apartment)"
    return out or None

def main():
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    live = {"_meta": {"fetched": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "errors": {}}}
    feeds = {"ura_ppi": ura_ppi, "hdb_rpi": hdb_rpi, "locality": ura_locality,
             "hdb_resale": hdb_resale, "gls": gls, "segments_official": ura_transactions}
    for name, fn in feeds.items():
        try:
            val = fn()
            if val is not None:
                live[name] = val
                print(f"  ok   {name}")
            else:
                print(f"  skip {name} (no key / no data)")
        except Exception as e:
            live["_meta"]["errors"][name] = repr(e)
            print(f"  FAIL {name}: {e!r}")
    fetched_any = any(name in live for name in feeds)
    if not fetched_any:
        # Every feed failed: keep the previous live.json rather than overwriting it
        # with an empty shell, and fail the run so CI surfaces it.
        print("::error::all live feeds failed - keeping the previous data/live.json")
        sys.exit(1)
    for name in live["_meta"]["errors"]:
        print(f"::warning::live feed failed: {name} - curated baseline values will stand for it")
    OUT.write_text(json.dumps(live, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size/1024:.1f} KB); errors: {list(live['_meta']['errors'])}")

if __name__ == "__main__":
    main()
