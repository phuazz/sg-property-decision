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

Derived (needs two feeds, so it runs after the fetch loop):
  - land bid -> launch price multiple                                   GLS awards x developer sales

Every feed is wrapped so one failure does not abort the others; failures are
recorded in live.json._meta.errors so a partial refresh is transparent.
Usage: python scripts/fetch_data.py
"""
import io, os, re, sys, html, json, time, collections, statistics, datetime, pathlib, urllib.parse
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
MAX_UNIT_SQFT = 10000   # above this the "area" is land or strata, not a unit — see ura_project_scorecard
CCR = {"downtown core","orchard","newton","river valley","rochor","museum","singapore river",
       "marina south","straits view","tanglin","marina east"}
RCR = {"kallang","geylang","queenstown","bukit merah","toa payoh","marine parade","novena",
       "bishan","southern islands","outram","bukit timah"}
def region_of(pa):
    p = (pa or "").strip().lower()
    if p in CCR: return "CCR"
    if p in RCR: return "RCR"
    return "OCR"

PPI_RID = "d_97f8a2e995022d311c6c68cfda6d034c"   # URA Private Residential PPI, quarterly

def ura_ppi():
    recs = dg_all(PPI_RID)
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

HDB_TOWN = "MARINE PARADE"                                  # estate flat's town
HDB_RESALE_RID = "d_8b84c4ee58e3cfc0ece0d773c8ca6abc"

def hdb_town():
    """Full resale history for HDB_TOWN by flat type, plus every print of the largest flat type.

    hdb_resale() above is national and latest-month only. A thin town cannot be valued off one
    month: Marine Parade prints well under 200 flats a year and the sample for its largest type
    is smaller still, so the comp range has to come from the whole register. Filtered server-side
    rather than via dg_tail, which only reaches the most recent few thousand national records.
    """
    q = urllib.parse.urlencode({"resource_id": HDB_RESALE_RID, "limit": 8000,
                                "filters": json.dumps({"town": HDB_TOWN})})
    recs = GET(f"{DG}?{q}", timeout=90).json()["result"]["records"]
    if not recs:
        raise RuntimeError(f"no resale records for town={HDB_TOWN}")
    cur = datetime.date.today()
    now_i = cur.year * 12 + cur.month
    def mix(m):
        y, mm = m.split("-"); return int(y) * 12 + int(mm)
    def px(rs):
        return _pctiles([float(r["resale_price"]) for r in rs]) if len(rs) >= 6 else None
    by_type = {}
    for t in sorted(set(r["flat_type"] for r in recs)):
        rows = [r for r in recs if r["flat_type"] == t]
        sqm = [float(r["floor_area_sqm"]) for r in rows]
        by_type[t] = {"n_all": len(rows),
                      "n_12m": sum(1 for r in rows if now_i - mix(r["month"]) <= 12),
                      "n_36m": sum(1 for r in rows if now_i - mix(r["month"]) <= 36),
                      "price_p_12m": px([r for r in rows if now_i - mix(r["month"]) <= 12]),
                      "price_p_36m": px([r for r in rows if now_i - mix(r["month"]) <= 36]),
                      "sqm_range": [min(sqm), max(sqm)],
                      "models": dict(collections.Counter(r["flat_model"] for r in rows))}
    largest = max(by_type, key=lambda t: by_type[t]["sqm_range"][1])
    big = sorted(({"month": r["month"], "block": r["block"], "street": r["street_name"],
                   "type": r["flat_type"], "model": r["flat_model"],
                   "sqm": float(r["floor_area_sqm"]),
                   "sqft": round(float(r["floor_area_sqm"]) * 10.7639),
                   "storey": r["storey_range"], "price": round(float(r["resale_price"])),
                   "lease_from": r["lease_commence_date"], "remaining": r.get("remaining_lease")}
                  for r in recs if r["flat_type"] == largest), key=lambda r: r["month"])
    return {"town": HDB_TOWN, "asof_month": max(r["month"] for r in recs), "n": len(recs),
            "by_type": by_type, "largest_type": largest, "largest_rows": big,
            "lease_commence": dict(sorted(collections.Counter(
                r["lease_commence_date"] for r in recs).items())),
            "source": f"data.gov.sg {HDB_RESALE_RID[:10]} (HDB resale register), town={HDB_TOWN}"}

_GLS_FRAME = {}

def _gls_frame():
    """Residential awards from the URA Past-Sale-Sites workbook, downloaded once per run.

    Two feeds need it (gls and land_to_launch) and the workbook is a ~1MB download off a
    scraped href, so it is memoised rather than fetched twice.
    """
    if "df" not in _GLS_FRAME:
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
        _GLS_FRAME["df"] = df
    return _GLS_FRAME["df"]

def gls():
    df = _gls_frame()
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

DISTRICT_NAME = {
    "01": "Raffles Place / Marina", "02": "Tanjong Pagar / Anson", "03": "Tiong Bahru / Queenstown",
    "04": "Sentosa / Harbourfront", "05": "Buona Vista / Clementi / Dover", "06": "City Hall / Clarke Quay",
    "07": "Bugis / Beach Road", "08": "Little India / Farrer Park", "09": "Orchard / River Valley",
    "10": "Bukit Timah / Holland", "11": "Novena / Newton", "12": "Balestier / Toa Payoh",
    "13": "Macpherson / Potong Pasir", "14": "Geylang / Eunos", "15": "East Coast / Marine Parade",
    "16": "Bedok / Upper East Coast", "17": "Changi / Loyang", "18": "Tampines / Pasir Ris",
    "19": "Serangoon / Hougang / Punggol", "20": "Bishan / Ang Mo Kio", "21": "Upper Bukit Timah / Clementi Pk",
    "22": "Jurong", "23": "Bukit Batok / Choa Chu Kang", "24": "Lim Chu Kang / Tengah",
    "25": "Woodlands / Kranji", "26": "Upper Thomson / Mandai", "27": "Sembawang / Yishun",
    "28": "Seletar / Yio Chu Kang"}

def _ura_token(key):
    """Day token for the URA Data Service, or raise.

    A bad or expired access key does NOT return an HTTP error. It returns
    {"Status":"Error","Message":"Invalid Access Key","Result":""} with HTTP 200, and an empty
    token then yields well-formed but empty payloads from every downstream service. That is how
    the 7 Aug 2026 refresh silently emptied districts/projects/segments_official. Validate here
    so the feed raises and lands in _meta.errors with the cause named.
    """
    r = GET("https://eservice.ura.gov.sg/uraDataService/insertNewToken/v1",
            headers={**UA, "AccessKey": key}, timeout=30).json()
    tok = r.get("Result")
    if r.get("Status") != "Success" or not tok:
        raise RuntimeError(f"URA token refused: {r.get('Message') or r}. "
                           "Renew URA_ACCESS_KEY at https://eservice.ura.gov.sg/maps/api/reg.html")
    return tok

_URA_PROJECTS = None
def _ura_projects(key):
    """Pull PMI_Resi_Transaction once (4 district batches), cache for reuse across aggregations."""
    global _URA_PROJECTS
    if _URA_PROJECTS is not None:
        return _URA_PROJECTS
    tok = _ura_token(key)
    hdr = {**UA, "AccessKey": key, "Token": tok}
    projs = []
    for batch in (1, 2, 3, 4):
        projs += GET(f"https://eservice.ura.gov.sg/uraDataService/invokeUraDS/v1?service=PMI_Resi_Transaction&batch={batch}",
                     headers=hdr, timeout=60).json().get("Result", [])
    _URA_PROJECTS = projs
    return projs

def _midx(mmyy):
    """'mmyy' contract date -> month index (year*12+month) for windowing, or None."""
    try:
        return (2000 + int(mmyy[2:])) * 12 + int(mmyy[:2])
    except (ValueError, TypeError, IndexError):
        return None

def _pctiles(vals):
    """[p10, p25, p50, p75, p90] of a numeric list (for the fair-value distribution)."""
    v = sorted(vals)
    n = len(v)
    return [round(v[min(n - 1, int(p * n))]) for p in (0.10, 0.25, 0.50, 0.75, 0.90)]

def _sizeband(sqft):
    """Condo size band for like-for-like fair value: 0 <600, 1 600-850, 2 850-1150, 3 >=1150 sqft. Boundaries mirror the template."""
    return 0 if sqft < 600 else 1 if sqft < 850 else 2 if sqft < 1150 else 3

def _lease_left(tenure, cur_year):
    """'Freehold' -> 'FH'; '99 yrs lease commencing from 1998' -> remaining years; else None.

    Terms far longer than 999 years are real, not parse failures: ROXY SQUARE is '9999 yrs lease
    commencing from 1995' and so returns 9968, and one D19 record yields 999963. Both are correct
    arithmetic on the source string. Do not clamp them here — template.html names the term from
    the remaining span (_leaseTxt) and scripts/test_lease_labels.js pins that mapping.
    """
    t = str(tenure or "")
    if "Freehold" in t:
        return "FH"
    m = re.search(r"(\d+)\s*yr?s?\s*lease\s*commencing\s*from\s*(\d{4})", t, re.I)
    if m:
        return max(0, int(m.group(1)) - (cur_year - int(m.group(2))))
    return None

def _range_mid(s):
    """'700 to 800' / '700-800' / '750' -> midpoint float, or None."""
    if not s:
        return None
    nums = [float(n) for n in re.findall(r"\d+", str(s))]
    return sum(nums) / len(nums) if nums else None

def _district_rent_psf(key):
    """Median monthly rent $psf by district over the last 4 quarters. Best-effort; {} on any trouble."""
    try:
        tok = _ura_token(key)
        hdr = {**UA, "AccessKey": key, "Token": tok}
        today = datetime.date.today()
        yy, qq, periods = today.year % 100, (today.month - 1) // 3 + 1, []
        for _ in range(4):
            periods.append(f"{yy:02d}q{qq}")
            qq -= 1
            if qq == 0:
                qq, yy = 4, yy - 1
        by = collections.defaultdict(list)
        for rp in periods:
            res = GET(f"https://eservice.ura.gov.sg/uraDataService/invokeUraDS/v1?service=PMI_Resi_Rental&refPeriod={rp}",
                      headers=hdr, timeout=60).json().get("Result", [])
            for proj in res:
                for c in proj.get("rental", []):
                    d = str(c.get("district") or proj.get("district") or "").zfill(2)
                    mid, rent = _range_mid(c.get("areaSqft")), c.get("rent")
                    if d in DISTRICT_NAME and mid and rent:
                        by[d].append(float(rent) / mid)
        return {d: statistics.median(v) for d, v in by.items() if len(v) >= 20}
    except Exception:
        return {}

def ura_transactions():
    """Official median condo/apartment $psf per market segment, last 12 months (current level)."""
    key = os.environ.get("URA_ACCESS_KEY")
    if not key:
        return None
    projs = _ura_projects(key)
    now_i = datetime.date.today().year * 12 + datetime.date.today().month
    seg_psf = {"CCR": [], "RCR": [], "OCR": []}
    for proj in projs:
        seg = proj.get("marketSegment")
        if seg not in seg_psf:
            continue
        for t in proj.get("transaction", []):
            if t.get("propertyType") not in ("Condominium", "Apartment"):
                continue
            if (_midx(t.get("contractDate", "")) or 0) <= now_i - 12:
                continue
            try:
                area = float(t["area"]) * 10.7639
                if area:
                    seg_psf[seg].append(float(t["price"]) / area)
            except (KeyError, ValueError, ZeroDivisionError):
                pass
    out = {s: {"median_psf": round(statistics.median(v)), "n": len(v)} for s, v in seg_psf.items() if v}
    out["_source"] = "URA PMI_Resi_Transaction (last 12 months, condo/apartment)"
    return out or None

def ura_districts():
    """Per-postal-district RESALE condo/apartment stats: median $psf (12m), volume, momentum, freehold share, gross yield.
    Resale-only (typeOfSale=3) so a district's median is not distorted by new-launch mix entering the sample."""
    key = os.environ.get("URA_ACCESS_KEY")
    if not key:
        return None
    projs = _ura_projects(key)
    now_i = datetime.date.today().year * 12 + datetime.date.today().month
    D = collections.defaultdict(lambda: {"psf": [], "psf_prev": [], "psf_fh": [], "psf_lh": [], "psf_sz": [[], [], [], []], "fh": 0, "tot": 0, "seg": collections.Counter()})
    cent = collections.defaultdict(lambda: [0.0, 0.0, 0])  # per-district SVY21 centroid (sum x, sum y, n) for the map
    for proj in projs:
        seg = proj.get("marketSegment")
        proj_d = None  # district lives on the transactions, not the project object
        for t in proj.get("transaction", []):
            if t.get("propertyType") not in ("Condominium", "Apartment"):
                continue
            if str(t.get("typeOfSale", "")).strip() != "3":   # resale only - strips new-launch mix distortion
                continue
            d = str(t.get("district") or "").zfill(2)
            if d not in DISTRICT_NAME:
                continue
            if proj_d is None:
                proj_d = d
            mi = _midx(t.get("contractDate", ""))
            if mi is None:
                continue
            try:
                area = float(t["area"]) * 10.7639
                psf = float(t["price"]) / area if area else None
            except (KeyError, ValueError, ZeroDivisionError):
                continue
            if not psf:
                continue
            r = D[d]
            r["tot"] += 1
            if seg:
                r["seg"][seg] += 1
            if "Freehold" in str(t.get("tenure", "")):
                r["fh"] += 1
            if mi > now_i - 12:
                r["psf"].append(psf)
                (r["psf_fh"] if "Freehold" in str(t.get("tenure", "")) else r["psf_lh"]).append(psf)
                r["psf_sz"][_sizeband(area)].append(psf)
            elif mi > now_i - 24:
                r["psf_prev"].append(psf)
        if proj_d:  # accumulate this project's location into its district centroid
            try:
                cent[proj_d][0] += float(proj["x"]); cent[proj_d][1] += float(proj["y"]); cent[proj_d][2] += 1
            except (KeyError, TypeError, ValueError):
                pass
    rent = _district_rent_psf(key)
    rows = []
    for d, r in D.items():
        if len(r["psf"]) < 25:  # need a liquid recent resale sample for a stable median
            continue
        med = round(statistics.median(r["psf"]))
        prev = round(statistics.median(r["psf_prev"])) if len(r["psf_prev"]) >= 15 else None
        rows.append({
            "district": "D" + d.lstrip("0"), "d": d, "name": DISTRICT_NAME[d],
            "region": (r["seg"].most_common(1)[0][0] if r["seg"] else None),
            "median_psf": med, "vol_12m": len(r["psf"]), "psf_p": _pctiles(r["psf"]),
            "psf_p_fh": (_pctiles(r["psf_fh"]) if len(r["psf_fh"]) >= 15 else None),
            "psf_p_lh": (_pctiles(r["psf_lh"]) if len(r["psf_lh"]) >= 15 else None),
            "psf_sz": [(_pctiles(b) if len(b) >= 15 else None) for b in r["psf_sz"]],
            "momentum": (round(med / prev - 1, 3) if prev else None),
            "fh_share": (round(r["fh"] / r["tot"], 2) if r["tot"] else None),
            "yield": (round(rent[d] * 12 / med, 4) if d in rent and med else None)})
    # per-district centroid (mean of project SVY21 coords) -> lon/lat, for the choropleth map
    cll = {}
    try:
        from pyproj import Transformer
        _tf = Transformer.from_crs("EPSG:3414", "EPSG:4326", always_xy=True)
        for d, (sx, sy, n) in cent.items():
            if n:
                lon, lat = _tf.transform(sx / n, sy / n)
                cll[d] = [round(lon, 5), round(lat, 5)]
    except Exception as e:
        print(f"  note: district centroids skipped ({e!r})")
    for row in rows:
        if row["d"] in cll:
            row["c"] = cll[row["d"]]
    rows.sort(key=lambda x: -x["vol_12m"])
    return {"asof": datetime.date.today().strftime("%Y-%m"), "n": len(rows), "rows": rows,
            "yield_ok": bool(rent), "basis": "resale condo, last 12 months",
            "source": "URA PMI_Resi_Transaction resale (12m median $psf / volume / momentum) + PMI_Resi_Rental (yield)"}

def _mrt_exits():
    """LTA MRT/LRT station exits (data.gov.sg, WGS84) -> [(lat, lon, station_name)]."""
    meta = GET("https://api-open.data.gov.sg/v1/public/api/datasets/d_b39d3a0871985372d7e1637193335da5/poll-download", timeout=30).json()
    url = meta.get("data", {}).get("url") or meta.get("url")
    gj = GET(url, timeout=60).json()
    out = []
    for f in gj.get("features", []):
        c = (f.get("geometry") or {}).get("coordinates")
        st = (f.get("properties", {}) or {}).get("STATION_NA", "") or ""
        if c and len(c) >= 2:
            out.append((c[1], c[0], st.title().replace(" Mrt Station", "").replace(" Lrt Station", "").strip()))
    return out

def _add_mrt(rows):
    """Annotate project rows (SVY21 x,y) with nearest MRT exit distance (m) + station. Best-effort; no-op on trouble."""
    try:
        import math
        from pyproj import Transformer
        exits = _mrt_exits()
        if not exits:
            return
        tf = Transformer.from_crs("EPSG:3414", "EPSG:4326", always_xy=True)
        def hav(a, b, c, d):
            p = math.pi / 180
            return 2 * 6371000.0 * math.asin(math.sqrt(
                math.sin((c - a) * p / 2) ** 2 + math.cos(a * p) * math.cos(c * p) * math.sin((d - b) * p / 2) ** 2))
        for r in rows:
            try:
                lon, lat = tf.transform(float(r["x"]), float(r["y"]))
            except (TypeError, ValueError):
                continue
            best = min(exits, key=lambda e: hav(lat, lon, e[0], e[1]))
            r["mrt_m"], r["mrt"] = round(hav(lat, lon, best[0], best[1])), best[2]
    except Exception as e:
        print(f"  note: MRT distances skipped ({e!r})")

def ura_project_scorecard():
    """Per-project resale stats: median $psf (12m), volume (turnover), momentum, representative remaining
    lease, and SVY21 x/y (for the OneMap distance step). Resale-only, projects with a usable recent sample."""
    key = os.environ.get("URA_ACCESS_KEY")
    if not key:
        return None
    projs = _ura_projects(key)
    cur = datetime.date.today()
    now_i = cur.year * 12 + cur.month
    out = []
    for proj in projs:
        psf, psf_prev, leases, dist, last_mi, last_ym, sizes, prices = [], [], collections.Counter(), None, 0, None, [], []
        for t in proj.get("transaction", []):
            if t.get("propertyType") not in ("Condominium", "Apartment"):
                continue
            if str(t.get("typeOfSale", "")).strip() != "3":  # resale
                continue
            d = str(t.get("district") or "").zfill(2)
            if d in DISTRICT_NAME:
                dist = d
            mi = _midx(t.get("contractDate", ""))
            if mi is None:
                continue
            try:
                area = float(t["area"]) * 10.7639
                p = float(t["price"]) / area if area else None
            except (KeyError, ValueError, ZeroDivisionError):
                continue
            if not p:
                continue
            # URA occasionally carries a land or strata area where a unit area belongs:
            # LOYANG VALLEY reports 626,545 sqft. One such record is enough to wreck any
            # size-weighted aggregate downstream (it moved a district's mean unit size by
            # 5x, and a correlation from -0.53 to -0.14). No condominium unit is this big,
            # so treat it as a bad record rather than an outlier and drop the transaction.
            if area > MAX_UNIT_SQFT:
                continue
            ll = _lease_left(t.get("tenure"), cur.year)
            if ll is not None:
                leases[ll] += 1
            if mi > now_i - 12:
                psf.append(p); sizes.append(area); prices.append(float(t["price"]))
                if mi > last_mi:
                    cd = t.get("contractDate", ""); last_mi, last_ym = mi, "20" + cd[2:] + "-" + cd[:2]
            elif mi > now_i - 24:
                psf_prev.append(p)
        if len(psf) < 2:  # >=2 for any kind of median (single-deal non-medians add noise + bulk); <6 flagged thin
            continue
        med = round(statistics.median(psf))
        prev = round(statistics.median(psf_prev)) if len(psf_prev) >= 4 else None
        out.append({"project": proj.get("project"), "d": dist,
                    "district": ("D" + dist.lstrip("0")) if dist else None, "region": proj.get("marketSegment"),
                    "median_psf": med, "vol_12m": len(psf), "psf_p": (_pctiles(psf) if len(psf) >= 6 else None),
                    "size": _pctiles(sizes)[2], "size_r": [_pctiles(sizes)[0], _pctiles(sizes)[4]], "price": _pctiles(prices)[2],
                    "momentum": (round(med / prev - 1, 3) if prev else None),
                    "lease": (leases.most_common(1)[0][0] if leases else None), "last": last_ym,
                    "x": proj.get("x"), "y": proj.get("y")})
    out.sort(key=lambda r: -r["vol_12m"])
    _add_mrt(out)
    for r in out:  # x,y were only needed for the MRT calc; drop to trim the payload
        r.pop("x", None); r.pop("y", None)
    return {"asof": cur.strftime("%Y-%m"), "n": len(out), "rows": out,
            "mrt_ok": any("mrt_m" in r for r in out),
            "source": "URA PMI_Resi_Transaction resale, per project; nearest MRT from LTA exits (data.gov.sg)"}

EC_TARGET = "HUNDRED PALMS RESIDENCES"      # subject property for the estate/sequencing model
TARGET_DISTRICTS = ("15",)                  # replacement-home search area (D15 East Coast / Marine Parade)
MIN_SQFT_LARGE = 1200                       # floor-area proxy for a 4-bedroom unit: URA has no bedroom field
# Match landed by keyword, case-insensitively. An exact-string tuple returned ZERO D15 landed
# transactions over 24 months, which is not plausible — URA's capitalisation of these labels
# ("Semi-detached House" vs "Semi-Detached House") is not what was guessed. Keyword matching
# survives that; the propertyType census in the output makes any future miss self-evident.
LANDED_WORDS = ("detached", "terrace", "semi-d")

def ec_resale():
    """EC resale pricing, per project, plus the full caveat history for EC_TARGET.

    ura_project_scorecard() filters propertyType to Condominium/Apartment, so every Executive
    Condominium is excluded from the main dataset. This is the only place EC pricing enters it.
    The target project's caveats are returned unwindowed and unfiltered by typeOfSale so the
    2017 launch prices (cost basis) and the post-MOP resale run (time-to-sale) are both visible.
    """
    key = os.environ.get("URA_ACCESS_KEY")
    if not key:
        return None
    projs = _ura_projects(key)
    cur = datetime.date.today()
    now_i = cur.year * 12 + cur.month
    per, target, target_d = [], [], None
    for proj in projs:
        is_target = (proj.get("project") or "").strip().upper() == EC_TARGET
        psf, sizes, prices, dist = [], [], [], None
        for t in proj.get("transaction", []):
            if t.get("propertyType") != "Executive Condominium":
                continue
            mi = _midx(t.get("contractDate", ""))
            if mi is None:
                continue
            try:
                area = float(t["area"]) * 10.7639
                p = float(t["price"]) / area if area else None
            except (KeyError, ValueError, ZeroDivisionError):
                continue
            if not p or area > MAX_UNIT_SQFT:
                continue
            d = str(t.get("district") or "").zfill(2)
            if d in DISTRICT_NAME:
                dist = d
            cd = t.get("contractDate", "")
            if is_target:
                target_d = dist or target_d
                target.append({"month": "20" + cd[2:] + "-" + cd[:2], "psf": round(p),
                               "sqft": round(area), "price": round(float(t["price"])),
                               "sale_type": str(t.get("typeOfSale", "")).strip(),
                               "floor": t.get("floorRange"), "tenure": t.get("tenure")})
            if str(t.get("typeOfSale", "")).strip() == "3" and mi > now_i - 12:   # resale, last 12m
                psf.append(p); sizes.append(area); prices.append(float(t["price"]))
        if len(psf) >= 2:
            per.append({"project": proj.get("project"), "d": dist,
                        "district": ("D" + dist.lstrip("0")) if dist else None,
                        "region": proj.get("marketSegment"),
                        "median_psf": round(statistics.median(psf)), "vol_12m": len(psf),
                        "psf_p": (_pctiles(psf) if len(psf) >= 6 else None),
                        "size": _pctiles(sizes)[2], "price": _pctiles(prices)[2]})
    per.sort(key=lambda r: -r["vol_12m"])
    target.sort(key=lambda r: r["month"])
    # monthly resale caveat counts for the target — the empirical time-to-sale input
    tr = [c for c in target if c["sale_type"] == "3"]
    by_month = collections.Counter(c["month"] for c in tr)
    return {"asof": cur.strftime("%Y-%m"), "n": len(per), "rows": per,
            "target": {"project": EC_TARGET, "district": ("D" + target_d.lstrip("0")) if target_d else None,
                       "n_all": len(target), "n_resale": len(tr),
                       "resale_psf_p": (_pctiles([c["psf"] for c in tr]) if len(tr) >= 6 else None),
                       "resale_by_month": dict(sorted(by_month.items())),
                       "caveats": target},
            "source": "URA PMI_Resi_Transaction, propertyType=Executive Condominium "
                      "(sale_type: 1=new sale, 2=subsale, 3=resale)"}

def target_homes():
    """Unit-level resale transactions in TARGET_DISTRICTS for the replacement-home screen.

    Split non-landed (>=MIN_SQFT_LARGE only) from landed (all sizes). Keeps tenure and
    typeOfArea per record: for landed, URA's `area` may be LAND area rather than strata, and a
    $psf computed across the two bases is meaningless. Window is 24 months, not 12, because
    large-unit and landed samples are thin. URA publishes no bedroom count, so floor area is
    the only available adequacy proxy and callers must treat it as a proxy.
    """
    key = os.environ.get("URA_ACCESS_KEY")
    if not key:
        return None
    projs = _ura_projects(key)
    cur = datetime.date.today()
    now_i = cur.year * 12 + cur.month
    nonlanded, landed, census = [], [], {}
    for proj in projs:
        for t in proj.get("transaction", []):
            d = str(t.get("district") or "").zfill(2)
            if d not in TARGET_DISTRICTS:
                continue
            if str(t.get("typeOfSale", "")).strip() != "3":     # resale only
                continue
            mi = _midx(t.get("contractDate", ""))
            if mi is None or mi <= now_i - 24:
                continue
            pt = t.get("propertyType")
            census[pt] = census.get(pt, 0) + 1
            ptl = (pt or "").lower()
            is_landed = any(w in ptl for w in LANDED_WORDS)
            if not is_landed and pt not in ("Condominium", "Apartment"):
                continue
            try:
                area = float(t["area"]) * 10.7639
                price = float(t["price"])
                p = price / area if area else None
            except (KeyError, ValueError, ZeroDivisionError):
                continue
            if not p or area > MAX_UNIT_SQFT:
                continue
            if not is_landed and area < MIN_SQFT_LARGE:
                continue
            cd = t.get("contractDate", "")
            lease = _lease_left(t.get("tenure"), cur.year)
            rec = {"project": proj.get("project"), "month": "20" + cd[2:] + "-" + cd[:2],
                   "type": pt, "sqft": round(area), "price": round(price), "psf": round(p),
                   "area_basis": t.get("typeOfArea"), "lease": lease, "floor": t.get("floorRange")}
            (landed if is_landed else nonlanded).append(rec)
    for lst in (nonlanded, landed):
        lst.sort(key=lambda r: r["month"])
    fh = [r["psf"] for r in nonlanded if r["lease"] == "FH"]
    return {"asof": cur.strftime("%Y-%m"), "districts": list(TARGET_DISTRICTS),
            "window_months": 24, "min_sqft_nonlanded": MIN_SQFT_LARGE,
            "nonlanded": {"n": len(nonlanded), "n_freehold": len(fh),
                          "fh_psf_p": (_pctiles(fh) if len(fh) >= 6 else None), "rows": nonlanded},
            "landed": {"n": len(landed), "rows": landed},
            "property_type_census": dict(sorted(census.items(), key=lambda kv: -kv[1])),
            "bedroom_note": "URA publishes no bedroom count; floor area is a proxy only",
            "source": "URA PMI_Resi_Transaction resale, unit level, 24 months"}

def ura_new_launches():
    """URA developer sales (current new launches). Structure probe first — emits keys + a sample so the
    real parse can be written; integrated into the projects table as new-launch pricing after inspection."""
    key = os.environ.get("URA_ACCESS_KEY")
    if not key:
        return None
    try:
        tok = _ura_token(key)
        hdr = {**UA, "AccessKey": key, "Token": tok}
        t = datetime.date.today(); yy, mm = t.year % 100, t.month
        res, working = [], None
        for _ in range(7):  # mmyy, walking back to clear the ~2-month developer-sales publication lag
            rp = f"{mm:02d}{yy:02d}"
            r = GET(f"https://eservice.ura.gov.sg/uraDataService/invokeUraDS/v1?service=PMI_Resi_Developer_Sales&refPeriod={rp}",
                    headers=hdr, timeout=60).json().get("Result", [])
            if r:
                res, working = r, rp
                break
            mm -= 1
            if mm == 0:
                mm, yy = 12, yy - 1
        if not res:
            return None
        rows = []
        for p in res:
            ds = p.get("developerSales") or []
            rec = max(ds, key=lambda x: x.get("refPeriod", "")) if ds else None
            if not rec or not rec.get("medianPrice"):
                continue
            units, sold = rec.get("unitsAvail") or rec.get("launchedToDate"), rec.get("soldToDate")
            rows.append({"project": p.get("project"), "developer": p.get("developer"),
                         "region": p.get("marketSegment"), "district": "D" + str(p.get("district") or "").lstrip("0"),
                         "psf": rec.get("medianPrice"), "units": units, "sold": sold,
                         "takeup": (round(sold / units, 3) if units and sold else None)})
        rows.sort(key=lambda r: -(r.get("sold") or 0))
        return {"asof": working, "n": len(rows), "rows": rows,
                "source": "URA PMI_Resi_Developer_Sales (new-sale median $psf, units, take-up, developer)"}
    except Exception as e:
        return {"error": repr(e)}

# ---- land bid -> launch price multiple ------------------------------------------------
# Corporate-form tokens carry no identity, so they are stripped before entity names are compared.
_ENTITY_NOISE = {"PTE", "LTD", "LIMITED", "PRIVATE", "AND", "GROUP", "HOLDINGS", "NO"}
LTL_WINDOW_YEARS = 6      # a site awarded longer ago than this is not the plot today's launch sits on
LTL_MIN_PAIRS = 5         # below this the median is one project's idiosyncrasy, not a market rate
LTL_SANE_BAND = (1.5, 3.5)  # a median outside this says the match broke, not that the market moved

def _entities(name):
    """Entity token-tuples in a tenderer/developer field, which may name a JV of several companies."""
    out = []
    for part in re.split(r"\band\b|/|&", html.unescape(str(name or "")), flags=re.I):
        toks = tuple(t for t in re.sub(r"[^A-Za-z0-9 ]", " ", part).upper().split()
                     if t and t not in _ENTITY_NOISE)
        if toks:
            out.append(toks)
    return out

def land_to_launch(launches):
    """Multiple of the winning land bid at which the resulting project actually sells.

    Pairs each currently-selling project (URA developer sales) with the GLS site its developer
    won, matching on the registered entity name. Singapore developers tender through a
    single-purpose vehicle named for the plot, so an exact entity match is strong evidence the
    project sits on that site - but URA does not publish the link, so this stays a derived
    heuristic and every pair is emitted for audit.

    Guards, because this runs unattended and publishes a number:
      - only awards inside LTL_WINDOW_YEARS. Without the window a perennial corporate entity
        (Tripartite Developers, not an SPV) matched a 2010 award at $321 psf ppr and produced a
        spurious 6.4x pair.
      - any entity that won more than one site in the window is dropped: it cannot tell us which
        plot the project sits on.
      - the result is withheld unless there are LTL_MIN_PAIRS pairs and the median lands inside
        LTL_SANE_BAND, so a broken join degrades to the curated baseline rather than to a
        confident wrong number on the page.
    """
    rows = (launches or {}).get("rows") or []
    if not rows:
        return None
    df = _gls_frame()
    cutoff = datetime.datetime.now() - datetime.timedelta(days=365 * LTL_WINDOW_YEARS)
    win = df[df["award"] >= cutoff]

    site_by_ent = collections.defaultdict(list)
    for _, r in win.iterrows():
        for e in _entities(r["tenderer"]):
            site_by_ent[e].append(r)
    # an entity holding several sites cannot identify a plot -> unusable, not a judgement call
    ambiguous = {e for e, v in site_by_ent.items() if len({str(x["Location"]) for x in v}) > 1}

    pairs = {}
    for p in rows:
        if not p.get("psf"):
            continue
        hits = {}
        for e in _entities(p.get("developer")):
            if e in ambiguous:
                continue
            for r in site_by_ent.get(e, []):
                hits[str(r["Location"])] = r
        if len(hits) != 1:      # no match, or a project we cannot pin to one plot
            continue
        site, r = next(iter(hits.items()))
        pairs[p["project"]] = {
            "project": p["project"], "site": site, "region": p.get("region"),
            "award": r["award"].strftime("%Y-%m-%d"), "land_psf_ppr": int(r["psf_ppr"]),
            "launch_psf": p["psf"], "takeup": p.get("takeup"),
            "multiple": round(p["psf"] / float(r["psf_ppr"]), 2)}
    allp = sorted(pairs.values(), key=lambda x: x["multiple"])
    # A pair outside the sane band is a broken join, not a market observation, and it would widen
    # the published range far more than it moves the median - so drop it, but say so rather than
    # truncating silently. (A 40-year window readmits the 6.4x Tripartite/KASSIA pair this way.)
    pairs = [x for x in allp if LTL_SANE_BAND[0] <= x["multiple"] <= LTL_SANE_BAND[1]]
    dropped = [x for x in allp if x not in pairs]
    mult = [x["multiple"] for x in pairs]
    if len(mult) < LTL_MIN_PAIRS:
        return {"ok": False, "reason": f"only {len(mult)} land/launch pairs matched (need {LTL_MIN_PAIRS})"}
    med = round(statistics.median(mult), 2)
    if not LTL_SANE_BAND[0] <= med <= LTL_SANE_BAND[1]:
        return {"ok": False, "reason": f"median multiple {med} outside the sane band {LTL_SANE_BAND}"}

    # Restate each launch price in the PPI level of its own award quarter. This strips out however
    # much the whole market moved while the site was being built, which the raw multiple embeds.
    defl = None
    try:
        ppi = {r["quarter"]: float(r["index"]) for r in dg_all(PPI_RID)
               if r["property_type"] == "All Residential"}
        cur_q = max(ppi, key=qkey)
        d = []
        for x in pairs:
            y, mo = int(x["award"][:4]), int(x["award"][5:7])   # ISO date string: months are 1-indexed
            base = ppi.get(f"{y}-Q{(mo - 1) // 3 + 1}")
            if base:
                d.append(round(x["multiple"] * base / ppi[cur_q], 2))
        if len(d) == len(pairs):
            d.sort()
            defl = {"range": [d[0], d[-1]], "median": round(statistics.median(d), 2),
                    "vs_q": cur_q, "index": "URA PPI (All Residential)"}
    except Exception as e:      # the caveat is nice to have; it must not take the headline down
        defl = {"error": repr(e)}

    # How long the sites have had to accumulate market drift. Via relativedelta (ships with pandas)
    # rather than day arithmetic, and note datetime months are 1-indexed.
    from dateutil.relativedelta import relativedelta
    today = datetime.date.today()
    ages = sorted((lambda r: r.years * 12 + r.months)(
        relativedelta(today, datetime.date.fromisoformat(x["award"]))) for x in pairs)

    return {"ok": True, "factor_range": [mult[0], mult[-1]], "factor_median": med,
            "n": len(pairs), "award_span": [min(x["award"] for x in pairs),
                                            max(x["award"] for x in pairs)],
            "award_age_months": [ages[0], ages[-1]],
            "launch_asof": launches.get("asof"), "deflated": defl, "pairs": pairs,
            "dropped_outliers": [{k: x[k] for k in ("project", "site", "award", "multiple")}
                                 for x in dropped],
            "source": "URA Past-Sale-Sites .xlsx x URA PMI_Resi_Developer_Sales, matched on tenderer entity",
            "note": ("Current median asking $psf of a selling project over the $psf ppr its developer paid "
                     "for the site. State land only. Not a developer margin - it also carries whatever the "
                     "market did between award and today.")}

def _has_data(v):
    """True only if a feed actually carries content.

    A key-gated feed whose upstream returned nothing does not raise — it produces a well-formed
    but empty shell such as {"n": 0, "rows": []} or {"_source": ...}. Those must be treated as
    failures, not as data, or they overwrite good history. This happened on 7 Aug 2026: every
    URA feed came back empty, the no-auth feeds succeeded so the all-failed guard never fired,
    and the empty result was committed and published.
    """
    if v is None:
        return False
    if isinstance(v, dict):
        if not v or set(v) <= {"_source", "asof", "source"}:
            return False
        if v.get("n") == 0:
            return False
        if isinstance(v.get("rows"), list) and not v["rows"]:
            return False
        return True
    if isinstance(v, (list, tuple)):
        return bool(v)
    return True

def main():
    now = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)
    live = {"_meta": {"fetched": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "errors": {}}}
    prev = {}
    if OUT.exists():
        try:
            prev = json.loads(OUT.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            print(f"  note: could not read existing {OUT.name} ({e!r}) - no carry-forward available")
    feeds = {"ura_ppi": ura_ppi, "hdb_rpi": hdb_rpi, "locality": ura_locality,
             "hdb_resale": hdb_resale, "hdb_town": hdb_town, "gls": gls,
             "segments_official": ura_transactions, "districts": ura_districts,
             "projects": ura_project_scorecard, "new_launches": ura_new_launches,
             "ec_resale": ec_resale, "target_homes": target_homes}
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
    # Derived feed: needs both the GLS workbook and developer sales, so it runs after the loop.
    # It is deliberately not in `feeds` - it fetches nothing of its own, and an all-feeds-failed
    # run must not be rescued by a value computed from the two failures.
    nl = live.get("new_launches") if _has_data(live.get("new_launches")) else prev.get("new_launches")
    try:
        v = land_to_launch(nl)
        if v is None:
            print("  skip land_to_launch (no developer-sales data)")
        elif v.get("ok"):
            live["land_to_launch"] = v
            print(f"  ok   land_to_launch (n={v['n']}, median {v['factor_median']}x)")
        else:
            # withheld by a guard: leave the key unset so carry-forward keeps the last good value
            live["_meta"]["errors"]["land_to_launch"] = v["reason"]
            print(f"::warning::land_to_launch withheld: {v['reason']}")
    except Exception as e:
        live["_meta"]["errors"]["land_to_launch"] = repr(e)
        print(f"  FAIL land_to_launch: {e!r}")

    fetched_any = any(_has_data(live.get(name)) for name in feeds)
    if not fetched_any:
        # Every feed failed: keep the previous live.json rather than overwriting it
        # with an empty shell, and fail the run so CI surfaces it.
        print("::error::all live feeds failed - keeping the previous data/live.json")
        sys.exit(1)

    # Carry forward any feed that held data before but is empty or absent now. Without this a
    # single upstream outage (or an expired URA_ACCESS_KEY) silently destroys months of history,
    # because an empty-but-well-formed response is not an exception.
    carried = []
    for name in list(feeds) + ["land_to_launch"]:
        if _has_data(live.get(name)):
            continue
        if _has_data(prev.get(name)):
            live[name] = prev[name]
            carried.append(name)
    if carried:
        live["_meta"]["carried_forward"] = {
            "from": prev.get("_meta", {}).get("fetched"), "feeds": sorted(carried),
            "note": "these feeds returned no data this run; the previous values were preserved"}
        for name in carried:
            print(f"::error::live feed returned NO DATA: {name} - carried forward from "
                  f"{prev.get('_meta', {}).get('fetched')} (data preserved, but it is now stale)")

    for name in live["_meta"]["errors"]:
        print(f"::warning::live feed failed: {name} - curated baseline values will stand for it")
    OUT.write_text(json.dumps(live, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size/1024:.1f} KB); errors: {list(live['_meta']['errors'])}")

if __name__ == "__main__":
    main()
