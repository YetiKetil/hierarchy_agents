"""
Vis et lagret spill som lesbar tekst / Show a saved game as readable text.
Språket følger loggen / The language follows the log.

  python vis_spill.py <logg.json>                  # oversikt ovenfra / overview from above
  python vis_spill.py <logg.json> --notater        # med agentenes tanker / with the agents' thoughts  (--thoughts)
  python vis_spill.py <logg.json> --perspektiv D   # det D så og gjorde / what D saw and did  (--perspective)
  python vis_spill.py <logg.json> --debrief        # bare debriefen / only the debrief
"""
import argparse
import json

from motor import sorter
from tekster import KORTNAVN

L = {
    "no": {"head": "Betingelse: {b}   seed: {s}   utfall: {u} etter {r} runder", "start": "Starthender: ",
           "round": "=== Runde {n} ===   uorden {a} → {b}   komplette hender: {k}", "hands": "Hender ved start: ",
           "thinks": "tenker", "lost": " [TAPT]", "cut": " [avkortet]", "req": "{f} ber {t} om {n} kort, tilbyr {k}",
           "swap": "BYTTE {f}⇄{t}: {f} ga {a}, {t} ga {b}", "decl": "{t} avslo forespørselen fra {f}",
           "wd": "{f} trakk tilbake forespørselen til {t}", "rej": "AVVIST {r} ({h}): {g}", "end": "Sluttkort: ",
           "chan": "Meldinger per kanal: ", "sys": "SYSTEMPROMPT FOR {r}", "turn": "{r} er på tur (runde {n})",
           "writes": "skriver", "acts": "handler", "err": "FEIL", "q": "«{x}»",
           "utfall": {"løst": "løst", "stillstand": "stillstand", "tidsgrense": "tidsgrense", "api_feil": "API-feil"}},
    "en": {"head": "Condition: {b}   seed: {s}   outcome: {u} after {r} rounds", "start": "Starting hands: ",
           "round": "=== Round {n} ===   shortfall {a} → {b}   complete hands: {k}", "hands": "Hands at start: ",
           "thinks": "thinks", "lost": " [LOST]", "cut": " [truncated]", "req": "{f} asks {t} for {n} card(s), offering {k}",
           "swap": "SWAP {f}⇄{t}: {f} gave {a}, {t} gave {b}", "decl": "{t} declined the request from {f}",
           "wd": "{f} withdrew the request to {t}", "rej": "REJECTED {r} ({h}): {g}", "end": "Final cards: ",
           "chan": "Messages per channel: ", "sys": "SYSTEM PROMPT FOR {r}", "turn": "{r}'s turn (round {n})",
           "writes": "writes", "acts": "acts", "err": "ERROR", "q": "“{x}”",
           "utfall": {"løst": "solved", "stillstand": "standstill", "tidsgrense": "time limit", "api_feil": "API error"}},
}


def oversikt(logg, notater, t, ks):
    m = logg["maalinger"]
    print(t["head"].format(b=logg["betingelse"], s=logg["seed"], u=t["utfall"].get(m["utfall"], m["utfall"]), r=m["runder"]))
    print(t["start"] + " | ".join(f"{r}: {ks(h)}" for r, h in logg["start_hender"].items()))
    for rd in logg["runder"]:
        print("\n" + t["round"].format(n=rd["runde"], a=rd["uorden_for"], b=rd["uorden_etter"], k=rd["komplette_hender"]))
        print(t["hands"] + " | ".join(f"{r}: {ks(h)}" for r, h in rd["hender_start"].items()))
        if notater:
            for r, h in rd["handlinger"].items():
                if h.get("notater"):
                    print(f"  [{r} {t['thinks']}] {h['notater']}")
        for e in rd["hendelser"]:
            typ = e["type"]
            if typ == "melding":
                ekstra = (t["lost"] if e["tapt"] else "") + (t["cut"] if e["avkortet"] else "")
                print(f"  {e['fra']} → {e['til']}: " + t["q"].format(x=e["tekst"]) + ekstra)
            elif typ == "foresporsel":
                print("  " + t["req"].format(f=e["fra"], t=e["til"], n=len(e["gir"]), k=ks(e["gir"])))
            elif typ == "bytte":
                print("  " + t["swap"].format(f=e["fra"], t=e["til"], a=ks(e["fra_ga"]), b=ks(e["til_ga"])))
            elif typ == "avslag":
                print("  " + t["decl"].format(f=e["fra"], t=e["til"]))
            elif typ == "trukket":
                print("  " + t["wd"].format(f=e["fra"], t=e["til"]))
            elif typ == "avvist":
                print("  " + t["rej"].format(r=e["rolle"], h=e["handling"], g=e["grunn"]))
    print("\n" + t["end"] + " | ".join(f"{r}: {ks(h)}" for r, h in logg["slutt_hender"].items()))
    print(t["chan"] + ", ".join(f"{k}: {v}" for k, v in sorted(m["meldinger_per_kanal"].items())))


def perspektiv(logg, rolle, t):
    if "systemprompter" not in logg or "perspektiv" not in logg:
        raise SystemExit("Denne loggen har ikke agentenes prompter / This log does not contain the agents' prompts.")
    print("=== " + t["sys"].format(r=rolle) + " ===\n" + logg["systemprompter"][rolle] + "\n")
    for steg in logg["perspektiv"][rolle]:
        print(f"\n{'=' * 20} " + t["turn"].format(r=rolle, n=steg["runde"]) + f" {'=' * 20}")
        print(steg["prompt"])
        if steg["tekst"]:
            print(f"\n[{rolle} {t['writes']}] {steg['tekst']}")
        print(f"\n[{rolle} {t['acts']}] " + json.dumps(steg["handling"], ensure_ascii=False, indent=1))
        if steg["feil"]:
            print(f"[{t['err']}] {steg['feil']}")
    if logg["debrief"].get(rolle):
        print(f"\n=== DEBRIEF {rolle} ===\n{logg['debrief'][rolle]}")


def main():
    ap = argparse.ArgumentParser(description="Vis et lagret spill / Show a saved game")
    ap.add_argument("fil")
    ap.add_argument("--perspective", "--perspektiv", dest="perspektiv", metavar="ROLE")
    ap.add_argument("--thoughts", "--notater", dest="notater", action="store_true")
    ap.add_argument("--debrief", action="store_true")
    ap.add_argument("--language", "--sprak", dest="sprak", choices=["no", "en"], help="override language / overstyr språk")
    a = ap.parse_args()
    with open(a.fil, encoding="utf-8") as f:
        logg = json.load(f)
    sprak = a.sprak or ("en" if logg.get("oversatt") else (logg.get("konfig") or {}).get("sprak", "no"))
    t = L.get(sprak, L["no"])
    navn = KORTNAVN.get(sprak, KORTNAVN["no"])
    ks = lambda kort: ", ".join(navn.get(k, k) for k in sorter(kort)) or "-"
    if a.debrief:
        for r, tekst in logg["debrief"].items():
            print(f"\n=== {r} ===\n{tekst}")
    elif a.perspektiv:
        perspektiv(logg, a.perspektiv, t)
    else:
        oversikt(logg, a.notater, t, ks)


if __name__ == "__main__":
    main()
