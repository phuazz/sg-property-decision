#!/usr/bin/env python3
"""One-off: derive approximate 28-postal-district zones for the filled choropleth map.

No official open GeoJSON of Singapore's legacy postal districts (D1-D28) exists, and the one community
file found was unlicenced, so we approximate each district as the Voronoi region around its transaction
centroid (mean of URA resale-project SVY21 coordinates, emitted by fetch_data.py into
data/live.json as districts.rows[].c = [lon, lat]), clipped to the official Singapore coastline
(URA Master Plan 2019 Region Boundary "No Sea", data.gov.sg, Singapore Open Data Licence).

Output data/sg_districts.geojson is STATIC (committed once); the page joins live attractiveness to it by
district code at render time. The boundaries are approximate and are flagged as such on the page.

Run:  python scripts/build_districts_geo.py        (needs shapely; run after a CI refresh has written centroids)
"""
import json, pathlib, sys, urllib.request
from shapely.geometry import shape, mapping, MultiPoint, Point
from shapely.ops import unary_union, voronoi_diagram   # shapely >= 2.0

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
OUT = DATA / "sg_districts.geojson"
REGION_DATASET = "d_bf4d24df9129d5a8ff8cf82e20959ee0"  # URA Master Plan 2019 Region Boundary (No Sea)

def get(url, timeout=90):
    req = urllib.request.Request(url, headers={"User-Agent": "sg-property-decision/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)

def coastline():
    """Union the official region polygons -> single Singapore landmass outline (WGS84)."""
    meta = get(f"https://api-open.data.gov.sg/v1/public/api/datasets/{REGION_DATASET}/poll-download")
    url = meta.get("data", {}).get("url") or meta.get("url")
    gj = get(url)
    polys = [shape(f["geometry"]) for f in gj.get("features", []) if f.get("geometry")]
    if not polys:
        sys.exit("ERROR: no region polygons returned from data.gov.sg")
    land = unary_union(polys).buffer(0)
    geoms = list(land.geoms) if land.geom_type == "MultiPolygon" else [land]
    # Keep only the main island. Sentosa and Jurong Island are already fused to it (reclamation/causeways
    # in the Master Plan boundary); every remaining separate polygon is an outlying islet with no postal-
    # district condos (Pulau Tekong/Ubin in the north-east, southern reefs) that would only stretch the map.
    return max(geoms, key=lambda g: g.area).buffer(0)

def rnd(o, dp=5):
    if isinstance(o, float): return round(o, dp)
    if isinstance(o, list): return [rnd(x, dp) for x in o]
    if isinstance(o, dict): return {k: rnd(v, dp) for k, v in o.items()}
    return o

def main():
    live = json.load(open(DATA / "live.json", encoding="utf-8"))
    rows = (live.get("districts") or {}).get("rows") or []
    pts = [(r["c"][0], r["c"][1], r["d"], r["district"], r.get("name")) for r in rows if r.get("c")]
    if len(pts) < 10:
        sys.exit(f"ERROR: only {len(pts)} district centroids in live.json - run the CI refresh first")
    # simplify the coastline ONCE (~100 m); Voronoi internal edges stay exact straight lines shared by
    # neighbours, so clipping to this leaves no inter-district slivers while trimming the payload.
    land = coastline().simplify(0.0009, preserve_topology=True)
    mp = MultiPoint([Point(p[0], p[1]) for p in pts])
    vor = voronoi_diagram(mp, envelope=land.buffer(0.05))
    cells = list(vor.geoms)
    feats = []
    for lon, lat, d, dcode, name in pts:
        pt = Point(lon, lat)
        cell = next((c for c in cells if c.contains(pt)), None)
        if cell is None:
            print(f"  warn: no Voronoi cell for {dcode}")
            continue
        clipped = cell.intersection(land)
        if clipped.is_empty:
            continue
        feats.append({"type": "Feature",
                      "properties": {"d": d, "district": dcode, "name": name},
                      "geometry": rnd(mapping(clipped))})
    fc = {"type": "FeatureCollection", "n": len(feats),
          "note": ("Approximate postal-district zones: Voronoi of URA resale-transaction centroids clipped "
                   "to the official Singapore coastline (URA Master Plan 2019 Region Boundary, No Sea, "
                   "data.gov.sg, Singapore Open Data Licence). NOT official district boundaries."),
          "features": feats}
    OUT.write_text(json.dumps(fc, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size/1024:.1f} KB), {len(feats)} districts")

if __name__ == "__main__":
    main()
