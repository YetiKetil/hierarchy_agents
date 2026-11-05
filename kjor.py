"""
Kjør HIERARKI-øvelsen med KI-agenter.

Eksempler:
  python kjor.py betingelser/grunnbetingelse.yaml --test          # uten API, for å teste oppsettet
  python kjor.py betingelser/grunnbetingelse.yaml --antall 5
  python kjor.py betingelser/*.yaml --antall 10                   # alle betingelser, samme 10 utdelinger
  python kjor.py betingelser/alle_kjenner_maalet.yaml --fasit      # fasit: algoritme med full oversikt
"""
import argparse
import csv
import json
import os
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import llm
import tekster
from agenter import (SprakmodellAgent, TilfeldigAgent, debrief_prompt, rundeprompt, systemprompt, til_intern, verktoy,
                     verktoynavn)
from byraakrat import Byraakrat, ByraakratAgent
from konfig import last_betingelse
from motor import Spill, kort_str, og

CSV_FELT = ["tidspunkt", "betingelse", "seed", "utfall", "runder", "meldinger", "tegn_per_melding",
            "foresporsler", "bytter", "avslag", "kort_flyttet", "avvist", "kortomtale_oppover",
            "tapte_meldinger", "uorden_start", "uorden_slutt", "komplette_hender", "toppleder_andel",
            "api_kall", "api_feil", "avkuttede_svar", "tokens_inn", "tokens_ut", "sekunder"]


UT = {
    "no": {"status": "{e} runde {n:>2} | aktive {a:<7} | meldinger {m} | bytter {b} | avvist {v} | uorden {u:>2} | komplette {k}",
           "ferdig": "{e} FERDIG: {utfall} etter {r} runder, {m} meldinger, {b} bytter. Sluttkort: {kort}",
           "lagret": "Lagret {fil}  ({utfall}, {r} runder, {b} bytter, {k} API-kall{x})", "avkuttet": ", {n} avkuttede svar",
           "forhistorie": "{navn}: bruker forhistorie fra {fil} ({innhold})",
           "utfall": {"løst": "løst", "stillstand": "stillstand", "tidsgrense": "tidsgrense"}},
    "en": {"status": "{e} round {n:>2} | active {a:<7} | messages {m} | swaps {b} | rejected {v} | shortfall {u:>2} | complete {k}",
           "ferdig": "{e} FINISHED: {utfall} after {r} rounds, {m} messages, {b} swaps. Final cards: {kort}",
           "lagret": "Saved {fil}  ({utfall}, {r} rounds, {b} swaps, {k} API calls{x})", "avkuttet": ", {n} truncated answers",
           "forhistorie": "{navn}: using history from {fil} ({innhold})",
           "utfall": {"løst": "solved", "stillstand": "standstill", "tidsgrense": "time limit reached"}},
}


def ut(cfg, nokkel):
    return UT.get(cfg.get("sprak", "no"), UT["no"])[nokkel]


def rolle_modell(cfg, r):
    """Leverandør og modell for en rolle: rolleinnstillingen vinner, ellers standard for betingelsen."""
    rolle_cfg = (cfg.get("roller") or {}).get(r) or {}
    modell = rolle_cfg.get("modell", cfg["modell"])
    leverandor = rolle_cfg.get("leverandor") or (cfg.get("leverandor") if "modell" not in rolle_cfg else None)
    return leverandor or llm.guess_provider(modell), modell


def lag_agenter(cfg, spill, klient, modus):
    agenter = {}
    planlegger = Byraakrat(spill, spill.seed) if modus == "fasit" else None
    for r in spill.roller:
        if modus == "test":
            agenter[r] = TilfeldigAgent(r, spill, spill.seed)
        elif modus == "fasit":
            agenter[r] = ByraakratAgent(r, planlegger)
        else:
            leverandor, modell = rolle_modell(cfg, r)
            if klient is not None:   # brukes i tester: en falsk Anthropic-klient
                lev = llm.AnthropicProvider.__new__(llm.AnthropicProvider)
                lev.client, lev.model, lev.temperature = klient, modell, cfg.get("temperatur")
                lev.max_tokens, lev.force_tool = cfg.get("maks_tokens", 6000), cfg.get("tving_verktoybruk", False)
                lev.debrief_max_tokens = (cfg.get("debrief") or {}).get("maks_tokens", 4000)
            else:
                lev = llm.make_provider(leverandor, modell, max_tokens=cfg.get("maks_tokens", 6000),
                                        temperature=cfg.get("temperatur"),
                                        force_tool=cfg.get("tving_verktoybruk", False),
                                        debrief_max_tokens=(cfg.get("debrief") or {}).get("maks_tokens", 4000))
            agenter[r] = SprakmodellAgent(r, lev, tekster.tekst(spill.sprak, "viktig", v=verktoynavn(spill)))
    return agenter, planlegger


def finn_logg(kilde):
    """kilde kan være én loggfil eller en mappe; for en mappe brukes det nyeste spillet."""
    sti = Path(kilde)
    if sti.is_dir():
        filer = sorted(sti.glob("*.json"), key=lambda f: f.stat().st_mtime)
        if not filer:
            sys.exit(f"Fant ingen spill i mappen {sti} / No games found in the folder {sti}.")
        return filer[-1]
    if not sti.exists():
        sys.exit(f"Fant ikke {sti}. Sjekk «forhistorie: kilde:» i betingelsesfilen. / "
                 f"Could not find {sti}. Check 'forhistorie: kilde:' in the condition file.")
    return sti


def lag_forhistorie(cfg):
    """Bygger teksten hver agent får om forrige gjennomføring (se «forhistorie» i grunnbetingelsen)."""
    fh = cfg.get("forhistorie") or {}
    if not fh.get("kilde"):
        return None
    fil = finn_logg(fh["kilde"])
    forrige = json.loads(fil.read_text(encoding="utf-8"))
    innhold = fh.get("innhold", "plenum")
    if innhold not in ("plenum", "egen"):
        sys.exit("forhistorie: innhold må være «plenum» eller «egen».")
    sprak = cfg.get("sprak", "no")
    T = lambda k, **kw: tekster.tekst(sprak, k, **kw)
    navn = tekster.KORTNAVN.get(sprak, tekster.KORTNAVN["no"])
    og_ = lambda xs: (", ".join(xs[:-1]) + f" {T('og')} " + xs[-1]) if len(xs) > 1 else "".join(xs)
    m = forrige["maalinger"]
    kjente = forrige["konfig"].get("maal_kjent_for") or []
    hender = forrige["slutt_hender"]
    ferdige = [r for r, h in hender.items() if len(set(h)) == 1]
    felles = [T("fh_for")]
    if len(kjente) == len(hender):
        felles.append(T("fh_alle"))
    elif kjente:
        felles.append(T("fh_noen", x=og_(list(kjente))))
    else:
        felles.append(T("fh_ingen"))
    felles.append(T("fh_lost", n=m["runder"]) if m["utfall"] == "løst" else T("fh_ikke_lost", n=m["runder"]))
    felles.append(T("fh_ferdige", x=og_(ferdige)) if ferdige else T("fh_ingen_ferdige"))
    felles.append(T("fh_sluttkort", x=" | ".join(f"{r}: " + ", ".join(navn.get(k, k) for k in h) for r, h in hender.items())))
    utdata = {}
    for r in hender:
        deler = [" ".join(felles)]
        if innhold == "plenum":
            deler.append(T("fh_plenum"))
            deler += [f"=== {x} ===\n{(t or T('fh_ingen_svar')).strip()}" for x, t in forrige["debrief"].items()]
        else:
            deler.append(T("fh_egen"))
            deler.append((forrige["debrief"].get(r) or T("fh_ingen_svar")).strip())
        deler.append(T("fh_nytt"))
        utdata[r] = "\n\n".join(deler)
    return {"fil": str(fil), "innhold": innhold, "tekster": utdata}


def kjor_spill(cfg, seed, klient=None, modus="llm", stille=False):
    t0 = time.time()
    spill = Spill(cfg, seed)
    agenter, planlegger = lag_agenter(cfg, spill, klient, modus)
    system = {r: systemprompt(spill, r) for r in spill.roller}
    tokens = {r: Counter() for r in spill.roller}
    perspektiv = {r: [] for r in spill.roller}
    etikett = f"[{cfg['navn']} s{seed:03d}]"

    with ThreadPoolExecutor(max_workers=cfg.get("samtidige_kall") or len(spill.roller)) as pool:
        while not spill.ferdig:
            aktive = spill.hvem_skal_handle()
            prompts = {r: rundeprompt(spill, r) for r in aktive}
            framtid = {r: pool.submit(agenter[r].handle, system[r], prompts[r], verktoy(spill, r)) for r in aktive}
            handlinger = {}
            for r in aktive:
                h, info = framtid[r].result()
                h = til_intern(spill, h)
                handlinger[r] = h
                tokens[r].update({"inn": info["inn"], "ut": info["ut"], "kall": info.get("kall", 1),
                                  "feil": int(bool(info["feil"])), "avkuttet": info.get("avkuttet", 0)})
                perspektiv[r].append({"runde": spill.runde, "prompt": prompts[r], "handling": h,
                                      "tekst": info["tekst"], "feil": info["feil"], "stopp": info.get("stopp")})
            spill.behandle_runde(handlinger)
            if not stille:
                siste = spill.runder_logg[-1]
                typer = Counter(e["type"] for e in siste["hendelser"])
                print(ut(cfg, "status").format(e=etikett, n=siste["runde"], a="".join(aktive), m=typer["melding"],
                                               b=typer["bytte"], v=typer["avvist"], u=siste["uorden_etter"],
                                               k=siste["komplette_hender"]), flush=True)

        debrief = {}
        if cfg.get("debrief", {}).get("aktiv") and modus != "fasit":
            framtid = {r: pool.submit(agenter[r].debrief, system[r], debrief_prompt(spill, r)) for r in spill.roller}
            for r, f in framtid.items():
                tekst, info = f.result()
                debrief[r] = tekst
                tokens[r].update({"inn": info["inn"], "ut": info["ut"], "kall": info.get("kall", 1),
                                  "feil": int(bool(info["feil"])),
                                  "avkuttet": info.get("avkuttet", 0)})

    maal = spill.maalinger()
    sum_tokens = sum(tokens.values(), Counter())
    if not stille:
        print(ut(cfg, "ferdig").format(e=etikett, utfall=ut(cfg, "utfall").get(maal["utfall"], maal["utfall"]),
                                       r=maal["runder"], m=maal["meldinger"], b=maal["bytter"],
                                       kort=" | ".join(f"{r}: {spill.ks(h)}" for r, h in spill.hender.items())), flush=True)
    return {
        "betingelse": cfg["navn"],
        "seed": seed,
        "tidspunkt": datetime.now().isoformat(timespec="seconds"),
        "test": modus == "test",
        "modus": modus,
        "fasit": ({"fordeling": planlegger.maal, "startavstand": planlegger.startavstand,
                   "transittbytter": planlegger.transitter} if planlegger else None),
        "konfig": cfg,
        "systemprompter": system,
        "start_hender": spill.start_hender,
        "slutt_hender": {r: sorted(h.elements()) for r, h in spill.hender.items()},
        "maalinger": maal,
        "runder": spill.runder_logg,
        "perspektiv": perspektiv,
        "debrief": debrief,
        "tokens": {r: dict(t) for r, t in tokens.items()},
        "tokens_sum": dict(sum_tokens),
        "sekunder": round(time.time() - t0, 1),
    }


def csv_rad(logg):
    m, t = logg["maalinger"], logg["tokens_sum"]
    rad = {k: m.get(k) for k in CSV_FELT if k in m}
    rad.update({"tidspunkt": logg["tidspunkt"], "betingelse": logg["betingelse"], "seed": logg["seed"],
                "api_kall": t.get("kall", 0), "api_feil": t.get("feil", 0), "avkuttede_svar": t.get("avkuttet", 0),
                "tokens_inn": t.get("inn", 0),
                "tokens_ut": t.get("ut", 0), "sekunder": logg["sekunder"]})
    return rad


def apne_csv(loggmappe):
    """Åpner resultater.csv for tilføying. Har en eldre fil færre kolonner, skrives den om med de nye."""
    loggmappe.mkdir(parents=True, exist_ok=True)
    sti = loggmappe / "resultater.csv"
    if sti.exists():
        with open(sti, encoding="utf-8") as f:
            leser = csv.DictReader(f)
            gamle_felt, rader = leser.fieldnames, list(leser)
        if gamle_felt != CSV_FELT:
            with open(sti, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=CSV_FELT)
                w.writeheader()
                for rad in rader:
                    w.writerow({k: rad.get(k, "") for k in CSV_FELT})
    ny = not sti.exists()
    fil = open(sti, "a", newline="", encoding="utf-8")
    skriver = csv.DictWriter(fil, fieldnames=CSV_FELT)
    if ny:
        skriver.writeheader()
    return fil, skriver


def lagre(logg, loggmappe, csvfil, skriver):
    mappe = loggmappe / logg["betingelse"]
    mappe.mkdir(exist_ok=True)
    fil = mappe / f"spill_s{logg['seed']:03d}_{logg['tidspunkt'].replace(':', '')}.json"
    fil.write_text(json.dumps(logg, ensure_ascii=False, indent=1), encoding="utf-8")
    skriver.writerow(csv_rad(logg))
    csvfil.flush()
    return fil


def main():
    ap = argparse.ArgumentParser(description="Kjør HIERARKI-øvelsen med KI-agenter / Run the HIERARCHY exercise with AI agents.")
    ap.add_argument("betingelser", metavar="CONDITION", nargs="+", help="betingelsesfiler / condition files (YAML)")
    ap.add_argument("--games", "--antall", dest="antall", metavar="N", type=int, default=1, help="spill per betingelse / games per condition")
    ap.add_argument("--seed", type=int, default=1,
                    help="første kortutdeling; spill nr. i får seed+i / first card deal; game i gets seed+i")
    ap.add_argument("--provider", "--leverandor", dest="leverandor", choices=sorted(llm.PROVIDERS),
                    help="overstyr leverandør / override provider")
    ap.add_argument("--model", "--modell", dest="modell", metavar="NAME", help="overstyr modell for alle roller / override the model for all roles")
    ap.add_argument("--max-rounds", "--maks-runder", dest="maks_runder", metavar="N", type=int, help="overstyr maks antall runder / override max rounds")
    ap.add_argument("--concurrent", "--samtidige", dest="samtidige", metavar="N", type=int,
                    help="maks samtidige API-kall per spill / max simultaneous API calls per game (1-7)")
    ap.add_argument("--parallel", "--parallelt", dest="parallelt", metavar="N", type=int, default=1, help="spill som kjøres samtidig / games at once")
    ap.add_argument("--test", action="store_true", help="tilfeldige agenter, uten API / random agents, no API")
    ap.add_argument("--answer-key", "--fasit", dest="fasit", action="store_true",
                    help="algoritme med full oversikt, uten API / algorithm with full overview, no API")
    ap.add_argument("--logs", "--logg", dest="logg", metavar="FOLDER", default="logger", help="mappe for logger / log folder")
    ap.add_argument("--quiet", "--stille", dest="stille", action="store_true", help="ikke skriv ut hver runde / do not print each round")
    a = ap.parse_args()

    llm.load_env(Path.cwd(), Path(__file__).resolve().parent)
    modus = "fasit" if a.fasit else "test" if a.test else "llm"

    jobber = []
    for sti in a.betingelser:
        cfg = last_betingelse(sti)
        if a.modell:
            cfg["modell"] = a.modell
            cfg["leverandor"] = a.leverandor or llm.guess_provider(a.modell)
            for rolle_cfg in (cfg.get("roller") or {}).values():
                if isinstance(rolle_cfg, dict):
                    rolle_cfg.pop("modell", None)
                    rolle_cfg.pop("leverandor", None)
        elif a.leverandor:
            cfg["leverandor"] = a.leverandor
        if a.maks_runder:
            cfg["maks_runder"] = a.maks_runder
        if a.samtidige:
            cfg["samtidige_kall"] = a.samtidige
        cfg["_forhistorie"] = lag_forhistorie(cfg)
        if cfg["_forhistorie"]:
            print(ut(cfg, "forhistorie").format(navn=cfg["navn"], fil=cfg["_forhistorie"]["fil"],
                                                innhold=cfg["_forhistorie"]["innhold"]))
        if modus != "llm":
            cfg["navn"] = modus.upper() + "-" + cfg["navn"]
        jobber += [(cfg, a.seed + i) for i in range(a.antall)]

    if modus == "llm":
        mangler = set()
        for cfg, _ in jobber:
            roller = sorted(set(cfg["struktur"]["leder_av"]) | set(cfg["struktur"]["leder_av"].values()))
            for r in roller:
                leverandor, modell = rolle_modell(cfg, r)
                if leverandor not in llm.PROVIDERS:
                    sys.exit(f"Ukjent leverandør for modellen «{modell}» / Unknown provider for model '{modell}'. "
                             f"Bruk / use --provider {' | '.join(llm.PROVIDERS)}")
                nokkel = llm.missing_key(leverandor)
                if nokkel:
                    mangler.add(nokkel)
        if mangler:
            sys.exit("Mangler API-nøkkel / Missing API key: " + ", ".join(sorted(mangler)) +
                     ".\nSett den i en .env-fil eller som miljøvariabel, eller kjør med --test / --answer-key."
                     "\nPut it in a .env file or an environment variable, or run with --test / --answer-key.")

    loggmappe = Path(a.logg)
    csvfil, skriver = apne_csv(loggmappe)
    with ThreadPoolExecutor(max_workers=a.parallelt) as pool:
        for logg in pool.map(lambda j: kjor_spill(j[0], j[1], None, modus, a.stille or a.parallelt > 1), jobber):
            fil = lagre(logg, loggmappe, csvfil, skriver)
            m, t = logg["maalinger"], logg["tokens_sum"]
            c = logg["konfig"]
            ekstra = ut(c, "avkuttet").format(n=t.get("avkuttet")) if t.get("avkuttet") else ""
            print(ut(c, "lagret").format(fil=fil, utfall=ut(c, "utfall").get(m["utfall"], m["utfall"]), r=m["runder"],
                                         b=m["bytter"], k=t.get("kall", 0), x=ekstra))
    csvfil.close()


if __name__ == "__main__":
    main()
