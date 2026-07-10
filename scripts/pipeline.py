#!/usr/bin/env python3
"""Build docs/index.html from template.html by inlining data/*.json.

Vault dashboard convention: work on template.html (fetch-fallback for dev);
this injects the data so the built page is standalone. Usage: python scripts/pipeline.py
"""
import json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "template.html"
DATA = ROOT / "data"
OUT = ROOT / "docs" / "index.html"

def load(name):
    p = DATA / name
    with open(p, encoding="utf-8") as f:
        obj = json.load(f)          # parse => validates JSON
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"))

def main():
    html = TEMPLATE.read_text(encoding="utf-8")
    rules = load("rules.json")
    market = load("market.json")

    for token, payload, label in (
        ("/*__RULES__*/ null", rules, "rules.json"),
        ("/*__MARKET__*/ null", market, "market.json"),
    ):
        if token not in html:
            sys.exit(f"ERROR: placeholder for {label} not found in template.html")
        html = html.replace(token, payload)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding="utf-8")
    kb = OUT.stat().st_size / 1024
    print(f"Built {OUT.relative_to(ROOT)}  ({kb:.0f} KB)")
    print(f"  rules.json  {len(rules):>6} chars")
    print(f"  market.json {len(market):>6} chars")

if __name__ == "__main__":
    main()
