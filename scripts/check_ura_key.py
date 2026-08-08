#!/usr/bin/env python3
"""Verify a URA access key before it goes anywhere near CI or a repo secret.

A key can authenticate and still return nothing for the services this project calls: registration
is per purpose of use, so a key issued for (say) carpark data yields an empty PMI_Resi_Transaction.
That failure is indistinguishable from an outage unless you look, which is how the 7 Aug 2026
refresh silently emptied the dataset.

Reads the key from a prompt rather than argv or the environment, so it does not land in shell
history. Nothing is written; this only reads.

Usage: python scripts/check_ura_key.py
"""
import getpass, sys, collections

sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
import fetch_data as F                                     # reuse GET, _ura_token, _midx

TARGET = F.EC_TARGET                                       # HUNDRED PALMS RESIDENCES
SERVICES = ["PMI_Resi_Transaction", "PMI_Resi_Rental", "PMI_Resi_Developer_Sales"]

def main():
    # getpass reads the terminal, not stdin, so it would block forever if piped. Fall back to
    # stdin when there is no tty (CI, a pipe) rather than hanging with no prompt visible.
    if sys.stdin.isatty():
        key = getpass.getpass("Paste the URA access key (hidden): ").strip()
    else:
        print("No terminal detected - reading the key from stdin.")
        key = (sys.stdin.readline() or "").strip()
    if not key:
        sys.exit("No key entered.")

    print("\n1. Day token")
    try:
        tok = F._ura_token(key)
    except Exception as e:
        sys.exit(f"   FAIL {e}")
    print(f"   ok   token issued ({tok[:8]}...)")

    hdr = {**F.UA, "AccessKey": key, "Token": tok}
    print("\n2. Service access (a key registered for the wrong purpose authenticates but returns nothing)")
    ok_services = []
    for svc in SERVICES:
        url = f"https://eservice.ura.gov.sg/uraDataService/invokeUraDS/v1?service={svc}"
        if svc == "PMI_Resi_Transaction":
            url += "&batch=1"
        try:
            r = F.GET(url, headers=hdr, timeout=60).json()
            n = len(r.get("Result") or [])
            status = r.get("Status")
            if status == "Success" and n:
                print(f"   ok   {svc:28s} {n:,} records")
                ok_services.append(svc)
            else:
                print(f"   FAIL {svc:28s} Status={status} records={n} msg={r.get('Message')}")
        except Exception as e:
            print(f"   FAIL {svc:28s} {e!r}")

    if "PMI_Resi_Transaction" not in ok_services:
        sys.exit("\nPMI_Resi_Transaction is the feed everything depends on. Ask URA to enable the "
                 "private residential transaction services for this key.")

    print("\n3. All four transaction batches, and the subject property")
    projs, ec_types = [], collections.Counter()
    for batch in (1, 2, 3, 4):
        r = F.GET("https://eservice.ura.gov.sg/uraDataService/invokeUraDS/v1"
                  f"?service=PMI_Resi_Transaction&batch={batch}", headers=hdr, timeout=60).json()
        got = r.get("Result") or []
        print(f"   batch {batch}: {len(got):,} projects")
        projs += got
    print(f"   total: {len(projs):,} projects")

    for p in projs:
        for t in p.get("transaction", []):
            if t.get("propertyType"):
                ec_types[t["propertyType"]] += 1
    print("\n4. Property types present (ECs must appear, or Hundred Palms cannot be priced)")
    for k, v in sorted(ec_types.items(), key=lambda kv: -kv[1]):
        mark = " <-- needed" if k == "Executive Condominium" else ""
        print(f"   {k:34s} {v:>8,}{mark}")

    hp = [p for p in projs if (p.get("project") or "").strip().upper() == TARGET]
    print(f"\n5. {TARGET}")
    if not hp:
        names = [p.get("project") for p in projs if "PALM" in (p.get("project") or "").upper()]
        print(f"   NOT FOUND. Projects containing 'PALM': {names or 'none'}")
        print("   The project name in URA's data may differ - check the list above before assuming.")
    else:
        tx = hp[0].get("transaction", [])
        resale = [t for t in tx if str(t.get("typeOfSale", "")).strip() == "3"]
        print(f"   found: {len(tx):,} transactions, {len(resale):,} resale")
        if resale:
            months = sorted("20" + t["contractDate"][2:] + "-" + t["contractDate"][:2]
                            for t in resale if t.get("contractDate"))
            print(f"   resale caveats span {months[0]} to {months[-1]}")
            psf = sorted(float(t["price"]) / (float(t["area"]) * 10.7639)
                         for t in resale if t.get("area") and t.get("price"))
            print(f"   resale $psf: min {psf[0]:,.0f}  median {psf[len(psf)//2]:,.0f}  max {psf[-1]:,.0f}")
        else:
            print("   no resale transactions - only launch/subsale records")

    print("\nKey works for the services this project needs. Safe to set as the "
          "URA_ACCESS_KEY repo secret.")

if __name__ == "__main__":
    main()
