"""
Oppsummerer logger/resultater.csv per betingelse.

  python oppsummer.py                 # alle betingelser
  python oppsummer.py --uten-test     # hopp over testkjøringer
"""
import argparse
import csv
import statistics as st
from collections import defaultdict


def tall(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def snitt(v):
    v = [x for x in v if x is not None]
    return f"{st.mean(v):.1f}" if v else "–"


def median(v):
    v = [x for x in v if x is not None]
    return f"{st.median(v):.0f}" if v else "–"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fil", default="logger/resultater.csv")
    ap.add_argument("--no-test", "--uten-test", dest="uten_test", action="store_true")
    ap.add_argument("--en", action="store_true", help="English column headings")
    a = ap.parse_args()

    grupper = defaultdict(list)
    with open(a.fil, encoding="utf-8") as f:
        for rad in csv.DictReader(f):
            if a.uten_test and rad["betingelse"].startswith("TEST-"):
                continue
            grupper[rad["betingelse"]].append(rad)

    kolonner = [("betingelse", 32), ("n", 4), ("løst", 7), ("runder*", 8), ("meldinger", 10), ("bytter", 7),
                ("avvist", 7), ("A-andel", 8), ("kortomtale", 11), ("uorden slutt", 13), ("avkuttet", 9), ("tokens inn", 11)]
    if a.en:
        kolonner = [(n, b) for n, (_, b) in zip(["condition", "n", "solved", "rounds*", "messages", "swaps", "rejected",
                                                 "A share", "card talk", "shortfall end", "truncated", "tokens in"], kolonner)]
    kolonner = [(n, max(b, len(n) + 2)) for n, b in kolonner]
    print("".join(n.ljust(b) for n, b in kolonner))
    print("-" * sum(b for _, b in kolonner))
    for navn, rader in sorted(grupper.items()):
        losta = [r for r in rader if r["utfall"] == "løst"]
        verdier = [navn, str(len(rader)), f"{100 * len(losta) / len(rader):.0f} %",
                   median([tall(r["runder"]) for r in losta]),
                   snitt([tall(r["meldinger"]) for r in rader]),
                   snitt([tall(r["bytter"]) for r in rader]),
                   snitt([tall(r["avvist"]) for r in rader]),
                   snitt([tall(r["toppleder_andel"]) for r in rader]),
                   snitt([tall(r["kortomtale_oppover"]) for r in rader]),
                   snitt([tall(r["uorden_slutt"]) for r in rader]),
                   f"{sum(tall(r.get('avkuttede_svar')) or 0 for r in rader):.0f}",
                   f"{sum(tall(r['tokens_inn']) or 0 for r in rader):,.0f}".replace(",", " ")]
        print("".join(v.ljust(b) for v, (_, b) in zip(verdier, kolonner)))
    if a.en:
        print("\n* median number of rounds among solved games. Other columns are averages per game.")
        print("  A share = share of all messages to or from the top manager.")
        print("  Card talk = messages upwards that mention card values.")
        print("  Shortfall = cards missing before everyone has four of a kind (0 = solved).")
        print("  Truncated = answers cut off by the token limit (should be 0).")
    else:
        print("\n* median antall runder blant spill som ble løst. Øvrige kolonner er gjennomsnitt per spill.")
        print("  A-andel = andel av alle meldinger som gikk til eller fra toppsjefen.")
        print("  Uorden = antall kort som mangler før alle har fire like (0 = løst).")
        print("  Avkuttet = svar som ble kuttet av tokengrensen (bør være 0).")


if __name__ == "__main__":
    main()
