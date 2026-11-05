"""
Agentene og det de får se.

Hver agent er et eget, tilstandsløst kall til Claude. Agenten ser bare sitt eget
perspektiv: instruksen for sin rolle, sine egne kort, sin egen historikk og sine
egne notater. Hele «hukommelsen» bygges av motoren for hver runde, slik at den
kan begrenses eller manipuleres som en eksperimentvariabel.
"""
import random

from motor import KORTVERDIER, kort_str, og

import tekster


def _felt(spill):
    """Feltnavnene agenten ser, på spillets språk: internt navn -> navn agenten ser."""
    return {intern: synlig for synlig, intern in tekster.FELT[spill.sprak if spill.sprak in tekster.FELT else "no"].items()}


def verktoynavn(spill):
    return _felt(spill)["handling"]


def til_intern(spill, handling):
    """Gjør om verktøysvaret fra agentens feltnavn til de interne (norske) feltnavnene."""
    kart = tekster.FELT.get(spill.sprak, tekster.FELT["no"])

    def om(x):
        if isinstance(x, dict):
            return {kart.get(k, k): om(v) for k, v in x.items()}
        if isinstance(x, list):
            return [om(v) for v in x]
        return x
    return om(handling) if isinstance(handling, dict) else {}


# ---------------------------------------------------------------- prompter

def systemprompt(spill, r):
    cfg, regler, t = spill.cfg, spill.regler, spill.t
    v = verktoynavn(spill)
    deler = [t("intro", n=len(spill.roller), r=r)]

    instruks = t("h_instruks") + "\n" + cfg["instruks"].strip()
    if r in (cfg.get("maal_kjent_for") or []):
        instruks += "\n" + cfg["maal_tekst"].strip()
    deler.append(instruks)

    leder = spill.leder_av.get(r)
    under = spill.underordnede[r]
    pos = [t("du_er", r=r),
           t("leder", x=leder) if leder else t("ingen_leder"),
           t("under", x=spill.og(under)) if under else t("ingen_under"),
           t("skrive_til", x=spill.og(spill.kan_skrive_til(r)))]
    if spill.kan_be_om_kort_fra(r):
        pos.append(t("be_fra", x=spill.og(spill.kan_be_om_kort_fra(r))))
    if spill.kan_motta_foresporsel_fra(r):
        pos.append(t("fa_fra", x=spill.og(spill.kan_motta_foresporsel_fra(r))))
    deler.append(t("h_posisjon") + "\n" + " ".join(pos))

    forhistorie = ((cfg.get("_forhistorie") or {}).get("tekster") or {}).get(r)
    if forhistorie:
        deler.append(t("h_forrige") + "\n" + forhistorie)

    felles = cfg.get("tilleggsinstruks") or {}
    if felles.get("tekst"):
        deler.append(felles.get("overskrift", "Tillegg").upper() + "\n" + felles["tekst"].strip())

    rolle_cfg = (cfg.get("roller") or {}).get(r) or {}
    if rolle_cfg.get("tillegg"):
        deler.append(rolle_cfg.get("tillegg_overskrift", t("h_om_deg")).upper() + "\n" + rolle_cfg["tillegg"].strip())

    tek = [t("tek_runder"), t("tek_verktoy", v=v), t("tek_neste")]
    if spill.kan_be_om_kort_fra(r) or spill.kan_motta_foresporsel_fra(r):
        tek.append(t("tek_foresp", maks=regler.get("maks_kort_per_bytte", 2)))
    if regler.get("maks_tegn_per_melding"):
        tek.append(t("tek_tegn", n=regler["maks_tegn_per_melding"]))
    if regler.get("maks_meldinger_per_runde"):
        tek.append(t("tek_meld", n=regler["maks_meldinger_per_runde"]))
    if cfg.get("agentene_kan_vente", True):
        tek.append(t("tek_vent", v=_felt(spill)["vent"]))
    if cfg.get("vis_tidsgrense"):
        tek.append(t("tek_tid", n=cfg.get("maks_runder", 40)))
    tek.append(t("tek_ser"))
    deler.append(t("h_slik") + "\n" + "\n".join("- " + x for x in tek))
    return "\n\n".join(deler)


def historikk_tekst(spill, r, minne=None):
    linjer, forrige = [], None
    nytt_fra = spill.sist_handlet[r]
    vist_nytt = False
    for runde, tekst in spill.historikk[r]:
        if minne is not None and runde < spill.runde - minne:
            continue
        if runde != forrige:
            if runde >= nytt_fra >= 0 and not vist_nytt:
                linjer.append(spill.t("nytt_siden"))
                vist_nytt = True
            linjer.append(spill.t("runde_hist", n=runde))
            forrige = runde
        linjer.append(f"  - {tekst}")
    return "\n".join(linjer) if linjer else spill.t("ingenting")


def rundeprompt(spill, r):
    cfg, t = spill.cfg, spill.t
    maks = cfg.get("maks_runder", 40)
    linjer = [t("runde_av", n=spill.runde, m=maks) if cfg.get("vis_tidsgrense") else t("runde", n=spill.runde)]
    if spill.runde == 0:
        linjer.append(t("start"))
    elif spill.er_paminnelsesrunde():
        linjer.append(t("paminnelse", n=spill.runde, m=maks))
    linjer.append("\n" + t("dine_kort", kort=spill.ks(spill.hender[r])))
    res = spill.reservert(r)
    if res:
        linjer.append(t("reservert", kort=spill.ks(res)))

    egne = [f for f in spill.apne.values() if f["fra"] == r]
    if egne:
        linjer.append("\n" + t("egne_apne"))
        linjer += [t("egen_apen", x=f["til"], kort=spill.ks(f["gir"]), n=f["runde"]) for f in egne]
    inn = [f for f in spill.apne.values() if f["til"] == r]
    if inn:
        linjer.append("\n" + t("inn_apne"))
        linjer += [t("inn_apen", x=f["fra"], k=len(f["gir"]), kort=spill.ks(f["gir"]), n=f["runde"]) for f in inn]

    if spill.notater[r]:
        linjer.append("\n" + t("notater_sist") + "\n" + spill.notater[r])
    minne = cfg.get("hukommelse_runder")
    overskrift = t("skjedd") if minne is None else t("skjedd_minne", n=minne)
    linjer.append(f"\n{overskrift}:\n" + historikk_tekst(spill, r, minne))
    linjer.append("\n" + t("bestem", v=verktoynavn(spill)))
    return "\n".join(linjer)


def verktoy(spill, r):
    t, F = spill.t, _felt(spill)
    maks = spill.regler.get("maks_kort_per_bytte", 2)
    kort = {"type": "string", "enum": [spill.navn(k) for k in spill.verdier]}
    props = {F["notater"]: {"type": "string", "description": t("v_notater")}}
    mottakere = spill.kan_skrive_til(r)
    if mottakere:
        props[F["meldinger"]] = {
            "type": "array", "description": t("v_meldinger"),
            "items": {"type": "object", "required": [F["til"], F["tekst"]],
                      "properties": {F["til"]: {"type": "string", "enum": mottakere}, F["tekst"]: {"type": "string"}}}}
    kan_be = spill.kan_be_om_kort_fra(r)
    if kan_be:
        props[F["kortforesporsler"]] = {
            "type": "array", "description": t("v_foresp"),
            "items": {"type": "object", "required": [F["til"], F["gir"]],
                      "properties": {F["til"]: {"type": "string", "enum": kan_be},
                                     F["gir"]: {"type": "array", "items": kort, "minItems": 1, "maxItems": maks,
                                                "description": t("v_gir")}}}}
        props[F["trekk_tilbake"]] = {"type": "array", "items": {"type": "string", "enum": kan_be}, "description": t("v_trekk")}
    fra = spill.kan_motta_foresporsel_fra(r)
    if fra:
        props[F["svar_pa_foresporsler"]] = {
            "type": "array", "description": t("v_svar"),
            "items": {"type": "object", "required": [F["fra"], F["aksepter"]],
                      "properties": {F["fra"]: {"type": "string", "enum": fra},
                                     F["aksepter"]: {"type": "boolean"},
                                     F["sender"]: {"type": "array", "items": kort, "description": t("v_sender")}}}}
    if spill.cfg.get("agentene_kan_vente", True):
        props[F["vent"]] = {"type": "boolean", "description": t("v_vent")}
    return {"name": F["handling"], "description": t("v_beskr"),
            "input_schema": {"type": "object", "properties": props, "required": [F["notater"]]}}


def debrief_prompt(spill, r):
    sporsmal = spill.cfg["debrief"]["sporsmal"]
    t = spill.t
    return (t("debrief_innledning") + "\n\n" + historikk_tekst(spill, r) +
            "\n\n" + t("debrief_kort", kort=spill.ks(spill.hender[r])) + "\n\n" +
            t("debrief_sporsmal") + "\n" +
            "\n".join(f"{i}. {s}" for i, s in enumerate(sporsmal, 1)))


# ---------------------------------------------------------------- agenter

class SprakmodellAgent:
    """En agent som spør en språkmodell. Selve kallet gjøres av en leverandør i llm.py."""

    def __init__(self, rolle, leverandor, paminnelse=""):
        self.rolle, self.lev, self.paminnelse = rolle, leverandor, paminnelse

    def handle(self, system, prompt, verktoy_def):
        return self.lev.act(system, prompt, verktoy_def, reminder=self.paminnelse)

    def debrief(self, system, tekst):
        return self.lev.reply(system, tekst)


class TilfeldigAgent:
    """Gjør tilfeldige (og av og til ulovlige) ting. Brukes for å teste oppsettet uten API-kostnad."""

    def __init__(self, rolle, spill, seed):
        self.rolle, self.spill = rolle, spill
        self.rng = random.Random(f"{seed}-{rolle}")

    def handle(self, system, prompt, verktoy_def):
        s, r, rng = self.spill, self.rolle, self.rng
        ledig = list((s.hender[r] - s.reservert(r)).elements())
        h = {"notater": f"Tilfeldig agent {r}, runde {s.runde}."}
        if s.kan_skrive_til(r) and rng.random() < 0.6:
            h["meldinger"] = [{"til": rng.choice(s.kan_skrive_til(r)),
                               "tekst": f"{r}: {s.navn(rng.choice(ledig or s.verdier))}"}]
        svar = []
        for f in s.apne.values():
            if f["til"] == r:
                ok = rng.random() < 0.8 and len(ledig) >= len(f["gir"])
                svar.append({"fra": f["fra"], "aksepter": ok,
                             "sender": [s.navn(k) for k in rng.sample(ledig, len(f["gir"]))] if ok else []})
        if svar:
            h["svar_pa_foresporsler"] = svar
        if s.kan_be_om_kort_fra(r) and ledig and rng.random() < 0.5:
            mal = rng.choice(s.kan_be_om_kort_fra(r))
            h["kortforesporsler"] = [{"til": mal, "gir": [s.navn(k) for k in rng.sample(ledig, rng.randint(1, min(2, len(ledig))))]}]
        h["vent"] = rng.random() < 0.2
        return h, {"modell": "tilfeldig", "inn": 0, "ut": 0, "kall": 0, "tekst": "", "feil": None}

    def debrief(self, system, tekst):
        return "(tilfeldig agent – ingen debrief)", {"feil": None, "inn": 0, "ut": 0, "kall": 0}
