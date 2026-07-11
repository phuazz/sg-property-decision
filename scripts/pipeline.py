#!/usr/bin/env python3
"""Build docs/index.html from template.html by inlining rules.json + a merged market snapshot.

market.json is the curated baseline (canonical shape); data/live.json (written by
fetch_data.py from data.gov.sg + the URA GLS workbook) is overlaid where present.
Without live.json the baseline stands, so `npx serve .` works for standalone dev.

Usage:  python scripts/fetch_data.py   # refresh live.json (optional)
        python scripts/pipeline.py      # build docs/index.html
"""
import json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "template.html"
DATA = ROOT / "data"
OUT = ROOT / "docs" / "index.html"

def read(name, required=True):
    p = DATA / name
    if not p.exists():
        if required:
            sys.exit(f"ERROR: {name} missing")
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)

def merge_live(market, live):
    """Overlay live feeds onto the curated market baseline (canonical fields)."""
    if not live:
        return market
    feeds = ("ura_ppi", "hdb_rpi", "locality", "hdb_resale", "gls", "segments_official", "districts", "projects", "new_launches")
    ok = [f for f in feeds if live.get(f)]
    market["live"] = {"present": bool(ok), "fetched": live.get("_meta", {}).get("fetched"),
                      "ok": ok, "failed": sorted(live.get("_meta", {}).get("errors", {})),
                      "errors": live.get("_meta", {}).get("errors", {})}
    if not ok:
        return market
    # price indices
    for key in ("ura_ppi", "hdb_rpi"):
        lv = live.get(key)
        if lv:
            m = market["indices"][key]
            m.update({"level": lv["level"], "asof": lv["level_asof"],
                      "yoy": lv["yoy"], "qoq": lv["qoq"], "source": lv["source"] + " (live)"})
    # segment momentum (official quarterly q/q)
    loc = live.get("locality", {})
    for seg in ("CCR", "RCR", "OCR"):
        if seg in loc and loc[seg].get("qoq") is not None:
            market["segments"][seg]["momentum_qoq"] = loc[seg]["qoq"]
            market["segments"][seg]["momentum_asof"] = loc[seg]["asof"] + " official"
    # segment median $psf (official, only if URA token supplied)
    off = live.get("segments_official", {})
    for seg in ("CCR", "RCR", "OCR"):
        if seg in off:
            market["segments"][seg]["median_psf"] = off[seg]["median_psf"]
            market["segments"][seg]["median_psf_flag"] = "URA transactions (official)"
    # GLS land bids
    g = live.get("gls")
    if g and g.get("tenders_recent"):
        yrs = sorted(g["avg_psf_ppr_year"], reverse=True)
        market["gls"]["tenders"] = [{"site": t["site"], "region": t["region"], "close": t["close"],
                                     "psf_ppr": t["psf_ppr"], "bids": t["bids"],
                                     "note": t.get("tenderer")} for t in g["tenders_recent"]]
        market["gls"]["avg_now"] = g["avg_psf_ppr_year"][yrs[0]]
        market["gls"]["avg_prev"] = g["avg_psf_ppr_year"][yrs[1]] if len(yrs) > 1 else market["gls"]["avg_prev"]
        market["gls"]["yoy"] = g["yoy"]
        market["gls"]["asof"] = g["asof"] + " (live)"
        market["gls"]["source"] = g["source"]
    # HDB resale live medians
    if live.get("hdb_resale"):
        market["hdb_resale"] = live["hdb_resale"]
    # district-level attractiveness (URA transactions + rental; only present with the key)
    if live.get("districts"):
        market["districts"] = live["districts"]
    if live.get("projects"):
        market["projects"] = live["projects"]
    if live.get("new_launches"):
        market["new_launches"] = live["new_launches"]
    return market

def main():
    rules = read("rules.json")
    market = read("market.json")
    live = read("live.json", required=False)
    market = merge_live(market, live)

    rules_s = json.dumps(rules, ensure_ascii=False, separators=(",", ":"))
    market_s = json.dumps(market, ensure_ascii=False, separators=(",", ":"))
    html = TEMPLATE.read_text(encoding="utf-8")
    for token, payload, label in (("/*__RULES__*/ null", rules_s, "rules"),
                                  ("/*__MARKET__*/ null", market_s, "market")):
        if token not in html:
            sys.exit(f"ERROR: placeholder for {label} not found in template.html")
        html = html.replace(token, payload)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    live_state = "LIVE " + market["live"]["fetched"] if market.get("live", {}).get("present") else "baseline only (no live.json)"
    print(f"Built {OUT.relative_to(ROOT)} ({OUT.stat().st_size/1024:.0f} KB) — {live_state}")

if __name__ == "__main__":
    main()
