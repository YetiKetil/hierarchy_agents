"""
Spillmotoren for HIERARKI-øvelsen.

Motoren er vanlig kode uten KI. Den eier sannheten om hvem som har hvilke kort,
hvem som kan skrive til hvem, og om et kortbytte er lovlig. Agentene påvirker
spillet bare gjennom handlingene som motoren tar imot i behandle_runde().

Rundene er synkrone: alle agenter som er på tur, handler på grunnlag av det de
visste ved starten av runden. Meldinger og forespørsler kommer frem i neste runde.
"""
import random
import re
from collections import Counter

import tekster

KORT_PER_PERSON = 4
KORTVERDIER = ["ess", "konge", "dame", "knekt", "tier", "nier", "åtter"]

# Brukes til å oppdage (og eventuelt blokkere) at noen forteller lederen sin hvilke kort de har.
_BOYNINGER = {
    "ess": ["ess", "esset", "essene"],
    "konge": ["konge", "kongen", "konger", "kongene"],
    "dame": ["dame", "damen", "damer", "damene"],
    "knekt": ["knekt", "knekten", "knekter", "knektene"],
    "tier": ["tier", "tieren", "tiere", "tierne"],
    "nier": ["nier", "nieren", "niere", "nierne"],
    "åtter": ["åtter", "åtteren", "åttere", "åtterne"],
}
_ORD = sorted({o for liste in _BOYNINGER.values() for o in liste}, key=len, reverse=True)
KORTORD = re.compile(r"\b(" + "|".join(_ORD) + r")\b", re.IGNORECASE)


# ---------------------------------------------------------------- hjelpere

def sorter(kort):
    return sorted(kort, key=lambda k: KORTVERDIER.index(k) if k in KORTVERDIER else 99)


def som_liste(hand):
    return sorter(hand.elements())


def kort_str(kort):
    if isinstance(kort, Counter):
        kort = list(kort.elements())
    return ", ".join(sorter(kort)) if kort else "(ingen)"


def uorden(hand):
    """Hvor mange kort personen mangler for å ha fire like (0 = ferdig)."""
    return KORT_PER_PERSON - max(hand.values()) if sum(hand.values()) else KORT_PER_PERSON


def og(navn):
    navn = list(navn)
    if len(navn) <= 1:
        return "".join(navn)
    return ", ".join(navn[:-1]) + " og " + navn[-1]


def _liste(x):
    return x if isinstance(x, list) else []


def _inneholder(beholdning, kort):
    behov = Counter(kort)
    return all(beholdning[k] >= n for k, n in behov.items())


def del_ut(roller, oppsett, rng):
    metode = oppsett.get("metode", "tilfeldig")
    verdier = KORTVERDIER[: len(roller)]
    if metode == "tilfeldig":
        stokk = [v for v in verdier for _ in range(KORT_PER_PERSON)]
        rng.shuffle(stokk)
        return {r: Counter(stokk[i * 4:(i + 1) * 4]) for i, r in enumerate(roller)}
    if metode == "maks_spredning":
        # Alle får fire ulike verdier, og hver verdi finnes hos fire personer.
        v, rr = verdier[:], roller[:]
        rng.shuffle(v)
        rng.shuffle(rr)
        n = len(rr)
        return {rr[i]: Counter(v[(i + k) % n] for k in range(KORT_PER_PERSON)) for i in range(n)}
    if metode == "manuell":
        hender = {r: Counter(oppsett["hender"][r]) for r in roller}
        totalt = sum(hender.values(), Counter())
        if any(totalt[v] != KORT_PER_PERSON for v in verdier) or set(totalt) - set(verdier):
            raise ValueError(f"Manuell utdeling må inneholde nøyaktig fire av hver verdi: {verdier}")
        return hender
    raise ValueError(f"Ukjent utdelingsmetode: {metode}")


# ---------------------------------------------------------------- spillet

class Spill:
    def __init__(self, cfg, seed):
        self.cfg = cfg
        self.seed = seed
        self.regler = cfg["regler"]
        rng = random.Random(seed)
        self.stoy = random.Random(seed * 7919 + 1)  # egen strøm, så støy ikke påvirker utdelingen

        s = cfg["struktur"]
        self.leder_av = dict(s["leder_av"])
        self.roller = sorted(set(self.leder_av) | set(self.leder_av.values()))
        self.underordnede = {r: sorted(u for u, l in self.leder_av.items() if l == r) for r in self.roller}
        self.kanaler = {frozenset(p) for p in self.leder_av.items()}
        self.kanaler |= {frozenset(p) for p in s.get("sidekanaler") or []}
        self.verdier = KORTVERDIER[: len(self.roller)]
        self.sprak = cfg.get("sprak", "no")
        self.kortnavn = tekster.KORTNAVN.get(self.sprak, tekster.KORTNAVN["no"])
        self._fra_navn = {v.lower(): k for k, v in self.kortnavn.items()}
        ordliste = sorted(tekster.KORTORD.get(self.sprak, tekster.KORTORD["no"]), key=len, reverse=True)
        self.kortord = re.compile(r"\b(" + "|".join(ordliste) + r")\b", re.IGNORECASE)

        self.hender = del_ut(self.roller, cfg.get("utdeling", {}), rng)
        self.start_hender = {r: som_liste(h) for r, h in self.hender.items()}

        self.apne = {}  # frozenset({fra, til}) -> forespørsel
        self.neste_id = 1
        self.runde = 0
        self.historikk = {r: [] for r in self.roller}  # (runde, tekst)
        self.notater = {r: "" for r in self.roller}
        self.venter = {r: False for r in self.roller}
        self.vekket = {r: True for r in self.roller}
        self.sist_handlet = {r: -1 for r in self.roller}

        self.teller = Counter()
        self.tomme_runder = 0
        self.kanalteller = Counter()
        self.runder_logg = []
        self.ferdig = False
        self.utfall = None
        self._kontroller()

    # --- språk
    def t(self, nokkel, **kw):
        return tekster.tekst(self.sprak, nokkel, **kw)

    def navn(self, k):
        return self.kortnavn.get(k, k)

    def ks(self, kort):
        """Kortliste som tekst på spillets språk."""
        if isinstance(kort, Counter):
            kort = list(kort.elements())
        return ", ".join(self.navn(k) for k in sorter(kort)) if kort else self.t("ingen")

    def og(self, navn):
        navn = list(navn)
        if len(navn) <= 1:
            return "".join(navn)
        return ", ".join(navn[:-1]) + f" {self.t('og')} " + navn[-1]

    def intern(self, kort):
        """Gjør kortnavn på agentens språk om til interne verdier."""
        ut = []
        for k in _liste(kort):
            if not isinstance(k, str):
                continue
            k2 = k.strip()
            ut.append(k2 if k2 in KORTVERDIER else self._fra_navn.get(k2.lower(), k2))
        return ut

    # --- hvem kan hva

    def kan_skrive_til(self, r):
        return [x for x in self.roller if x != r and frozenset((r, x)) in self.kanaler]

    def kan_be_om_kort_fra(self, r):
        ut = list(self.underordnede[r])
        if self.regler.get("underordnet_kan_be_om_bytte") and self.leder_av.get(r):
            ut.append(self.leder_av[r])
        return ut

    def kan_motta_foresporsel_fra(self, r):
        ut = [self.leder_av[r]] if self.leder_av.get(r) else []
        if self.regler.get("underordnet_kan_be_om_bytte"):
            ut += self.underordnede[r]
        return ut

    def reservert(self, r):
        res = Counter()
        for f in self.apne.values():
            if f["fra"] == r:
                res.update(f["gir"])
        return res

    def er_paminnelsesrunde(self):
        hver = self.cfg.get("vekk_alle_hver")
        return bool(hver) and self.runde > 0 and self.runde % hver == 0

    def har_ubesvart_foresporsel(self, r):
        return any(f["til"] == r for f in self.apne.values())

    def hvem_skal_handle(self):
        if self.er_paminnelsesrunde():
            return list(self.roller)
        return [r for r in self.roller
                if self.vekket[r] or not self.venter[r] or self.har_ubesvart_foresporsel(r)]

    # --- selve runden

    def behandle_runde(self, handlinger):
        """handlinger: rolle -> dict med verktøyinput fra agentene som var på tur."""
        n = self.runde
        start = {r: Counter(h) for r, h in self.hender.items()}
        res_start = {r: self.reservert(r) for r in self.roller}
        brukt = {r: Counter() for r in self.roller}
        uorden_for = sum(uorden(h) for h in self.hender.values())
        hendelser = []
        nytt = {r: [] for r in self.roller}
        vekk = {r: False for r in self.roller}

        def til(r, tekst, vekker=True):
            nytt[r].append(tekst)
            if vekker:
                vekk[r] = True

        def ledig(r):
            return start[r] - res_start[r] - brukt[r]

        def avvis(r, hva, grunn):
            self.teller["avvist"] += 1
            hendelser.append({"type": "avvist", "rolle": r, "handling": hva, "grunn": grunn})
            til(r, self.t("avvist", hva=hva, grunn=grunn))

        for r, h in handlinger.items():
            if not isinstance(h, dict):
                handlinger[r] = {}
        for r, h in handlinger.items():
            self.notater[r] = str(h.get("notater", "") or "")
            self.venter[r] = bool(h.get("vent")) and self.cfg.get("agentene_kan_vente", True)
            self.sist_handlet[r] = n

        # 1. Svar på åpne forespørsler (fra forrige runde eller tidligere)
        for r, h in handlinger.items():
            for svar in _liste(h.get("svar_pa_foresporsler")):
                if not isinstance(svar, dict):
                    continue
                fra = svar.get("fra")
                f = self.apne.get(frozenset((r, fra)))
                if not f or f["til"] != r:
                    avvis(r, self.t("hva_svar", x=fra), self.t("g_ingen_apen", x=fra))
                    continue
                if not svar.get("aksepter"):
                    del self.apne[frozenset((r, fra))]
                    self.teller["avslag"] += 1
                    hendelser.append({"type": "avslag", "fra": fra, "til": r})
                    til(r, self.t("du_avslo", x=fra), vekker=False)
                    til(fra, self.t("avslo_din", x=r, kort=self.ks(f["gir"])))
                    continue
                sender = self.intern(svar.get("sender"))
                if len(sender) != len(f["gir"]):
                    avvis(r, self.t("hva_svar", x=fra), self.t("g_noyaktig", n=len(f["gir"]), m=len(sender)))
                    continue
                if not _inneholder(ledig(r), sender):
                    avvis(r, self.t("hva_svar", x=fra), self.t("g_ikke_ledige", kort=self.ks(sender)))
                    continue
                self.hender[r] -= Counter(sender)
                self.hender[r] += Counter(f["gir"])
                self.hender[fra] -= Counter(f["gir"])
                self.hender[fra] += Counter(sender)
                brukt[r] += Counter(sender)
                del self.apne[frozenset((r, fra))]
                self.teller["bytter"] += 1
                self.teller["kort_flyttet"] += 2 * len(sender)
                hendelser.append({"type": "bytte", "fra": fra, "til": r, "fra_ga": f["gir"], "til_ga": sender})
                til(r, self.t("bytte_du", x=fra, sendt=self.ks(sender), fikk=self.ks(f["gir"])), vekker=False)
                til(fra, self.t("godtok", x=r, ga=self.ks(f["gir"]), fikk=self.ks(sender)))

        # 2. Tilbaketrekking av egne forespørsler
        for r, h in handlinger.items():
            for t in _liste(h.get("trekk_tilbake")):
                f = self.apne.get(frozenset((r, t)))
                if f and f["fra"] == r:
                    del self.apne[frozenset((r, t))]
                    hendelser.append({"type": "trukket", "fra": r, "til": t})
                    til(r, self.t("du_trakk", x=t), vekker=False)
                    til(t, self.t("trakk_til_deg", x=r))
                else:
                    til(r, self.t("ingen_trekke", x=t))

        # 3. Nye kortforespørsler
        maks = self.regler.get("maks_kort_per_bytte", 2)
        for r, h in handlinger.items():
            for f in _liste(h.get("kortforesporsler")):
                if not isinstance(f, dict):
                    continue
                t = f.get("til")
                gir = self.intern(f.get("gir"))
                hva = self.t("hva_foresp", x=t)
                if t not in self.kan_be_om_kort_fra(r):
                    avvis(r, hva, self.t("g_kan_ikke_be", x=t))
                elif frozenset((r, t)) in self.apne:
                    avvis(r, hva, self.t("g_allerede_apen", x=t))
                elif not 1 <= len(gir) <= maks:
                    avvis(r, hva, self.t("g_antall", maks=maks))
                elif not _inneholder(ledig(r), gir):
                    avvis(r, hva, self.t("g_ikke_ledige", kort=self.ks(gir)))
                else:
                    brukt[r] += Counter(gir)
                    self.apne[frozenset((r, t))] = {"id": self.neste_id, "fra": r, "til": t, "gir": sorter(gir), "runde": n}
                    self.neste_id += 1
                    self.teller["foresporsler"] += 1
                    hendelser.append({"type": "foresporsel", "fra": r, "til": t, "gir": sorter(gir)})
                    til(r, self.t("du_ba", x=t, n=len(gir), kort=self.ks(gir)), vekker=False)
                    til(t, self.t("ber_deg", x=r, n=len(gir), kort=self.ks(gir)))

        # 4. Meldinger
        maks_m = self.regler.get("maks_meldinger_per_runde")
        maks_t = self.regler.get("maks_tegn_per_melding")
        p_tap = self.regler.get("tap_sannsynlighet", 0) or 0
        for r, h in handlinger.items():
            sendt = 0
            for m in _liste(h.get("meldinger")):
                if not isinstance(m, dict):
                    continue
                t, tekst = m.get("til"), str(m.get("tekst", "") or "").strip()
                if not tekst:
                    continue
                if t not in self.kan_skrive_til(r):
                    avvis(r, self.t("hva_melding", x=t), self.t("g_ikke_skrive", x=t))
                    continue
                if maks_m and sendt >= maks_m:
                    avvis(r, self.t("hva_melding", x=t), self.t("g_maks_meld", n=maks_m))
                    continue
                avkortet = bool(maks_t and len(tekst) > maks_t)
                if avkortet:
                    tekst = tekst[:maks_t]
                oppover = self.leder_av.get(r) == t
                nevner_kort = oppover and bool(self.kortord.search(tekst))
                if nevner_kort:
                    self.teller["kortomtale_oppover"] += 1
                    if self.regler.get("kortomtale_oppover") == "blokkert":
                        avvis(r, self.t("hva_melding", x=t), self.t("g_kortomtale"))
                        continue
                sendt += 1
                tapt = self.stoy.random() < p_tap
                self.teller["meldinger"] += 1
                self.teller["tegn"] += len(tekst)
                self.kanalteller[f"{r}→{t}"] += 1
                hendelser.append({"type": "melding", "fra": r, "til": t, "tekst": tekst,
                                  "avkortet": avkortet, "tapt": tapt, "nevner_kort_oppover": nevner_kort})
                til(r, self.t("du_sendte", x=t, tekst=tekst) + (self.t("avkortet") if avkortet else ""), vekker=False)
                if tapt:
                    self.teller["tapt"] += 1
                else:
                    til(t, self.t("fra_melding", x=r, tekst=tekst))

        # 5. Oppdater historikk, logg og sjekk slutt
        for r in self.roller:
            self.historikk[r].extend((n, t) for t in nytt[r])
            self.vekket[r] = vekk[r]
        self._kontroller()
        uorden_etter = sum(uorden(h) for h in self.hender.values())
        self.runder_logg.append({
            "runde": n,
            "hender_start": {r: som_liste(h) for r, h in start.items()},
            "handlinger": handlinger,
            "hendelser": hendelser,
            "uorden_for": uorden_for,
            "uorden_etter": uorden_etter,
            "komplette_hender": sum(uorden(h) == 0 for h in self.hender.values()),
        })
        self.runde += 1
        noe_skjedde = any(e["type"] != "avvist" for e in hendelser)
        self.tomme_runder = 0 if noe_skjedde else self.tomme_runder + 1
        grense = self.cfg.get("stillstand_etter_tomme_runder")
        if uorden_etter == 0:
            self.avslutt("løst")
        elif not self.hvem_skal_handle() and not self.cfg.get("vekk_alle_hver"):
            self.avslutt("stillstand")
        elif grense and self.tomme_runder >= grense:
            self.avslutt("stillstand")
        elif self.runde >= self.cfg.get("maks_runder", 40):
            self.avslutt("tidsgrense")

    def avslutt(self, utfall):
        self.ferdig = True
        self.utfall = utfall

    def _kontroller(self):
        totalt = sum(self.hender.values(), Counter())
        assert all(totalt[v] == KORT_PER_PERSON for v in self.verdier), f"Kort har forsvunnet: {totalt}"
        assert all(sum(h.values()) == KORT_PER_PERSON for h in self.hender.values()), "Feil antall kort på hånd"
        for r in self.roller:
            assert _inneholder(self.hender[r], list(self.reservert(r).elements())), f"Reserverte kort mangler hos {r}"

    # --- målinger

    def maalinger(self):
        topp = [r for r in self.roller if r not in self.leder_av]
        belastning = Counter()
        for kanal, antall in self.kanalteller.items():
            fra, t = kanal.split("→")
            belastning[fra] += antall
            belastning[t] += antall
        totalt = self.teller["meldinger"]
        return {
            "utfall": self.utfall,
            "runder": self.runde,
            "meldinger": totalt,
            "tegn_per_melding": round(self.teller["tegn"] / totalt, 1) if totalt else 0,
            "foresporsler": self.teller["foresporsler"],
            "bytter": self.teller["bytter"],
            "avslag": self.teller["avslag"],
            "kort_flyttet": self.teller["kort_flyttet"],
            "avvist": self.teller["avvist"],
            "kortomtale_oppover": self.teller["kortomtale_oppover"],
            "tapte_meldinger": self.teller["tapt"],
            "uorden_start": self.runder_logg[0]["uorden_for"] if self.runder_logg else None,
            "uorden_slutt": sum(uorden(h) for h in self.hender.values()),
            "komplette_hender": sum(uorden(h) == 0 for h in self.hender.values()),
            "toppleder_andel": round(sum(belastning[t] for t in topp) / totalt, 3) if totalt else 0,
            "meldinger_per_kanal": dict(self.kanalteller),
            "belastning_per_rolle": dict(belastning),
        }
