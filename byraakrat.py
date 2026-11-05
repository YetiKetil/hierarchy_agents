"""
Fasit: «den perfekte byråkraten».

En vanlig algoritme uten språkmodell, med full oversikt over alle kortene. Den spiller
gjennom den samme motoren og etter de samme reglene som agentene: bare ledere ber om
kort, maks 2 om gangen, like mange tilbake, og kortene flyttes ett ledd om gangen.

Den gjør tre ting:
1. Fordeler verdiene: hver person får én verdi, valgt slik at den samlede avstanden
   kortene må flyttes, blir minst mulig (alle 5040 fordelinger prøves).
2. Bytter der begge parter kommer nærmere målet, langs alle linjer samtidig.
3. Når ingen slike bytter finnes, gjør den et «transittbytte»: en leder tar midlertidig
   imot et kort den ikke trenger, for å sende det videre. Det er nettopp dette agentene
   ikke ville gjøre.

Resultatet er en referanse for hvor raskt oppgaven kan løses med disse kortene og
reglene. Det er ikke bevist optimalt, men viser at oppgaven er løsbar.
"""
import itertools
import random
from collections import Counter

from motor import kort_str


def _inneholder(beholdning, kort):
    return all(beholdning[k] >= n for k, n in Counter(kort).items())


class Byraakrat:
    def __init__(self, spill, seed=0):
        self.s = spill
        self.rng = random.Random(seed)
        self.maks = spill.regler.get("maks_kort_per_bytte", 2)
        self.foreldre = dict(spill.leder_av)
        self.dybde = {r: len(self._forfedre(r)) - 1 for r in spill.roller}
        self.undertre = {r: {x for x in spill.roller if r in self._forfedre(x)} for r in spill.roller}
        # kanter (leder, underordnet), nederste nivå først
        self.kanter = sorted(((l, u) for u, l in spill.leder_av.items()), key=lambda e: -self.dybde[e[1]])
        self.maal = self._fordel_verdier()
        self.eier = {v: r for r, v in self.maal.items()}
        self.planlagt_retur = {}
        self.plan_runde = None
        self.handlinger = {}
        self.transitter = 0
        self.siste_transitt = None

    # ---------------------------------------------------------- geometri
    def _forfedre(self, r):
        ut = [r]
        while ut[-1] in self.foreldre:
            ut.append(self.foreldre[ut[-1]])
        return ut

    def avstand(self, a, b):
        fa, fb = self._forfedre(a), self._forfedre(b)
        felles = next(x for x in fa if x in fb)
        return fa.index(felles) + fb.index(felles)

    def _fordel_verdier(self):
        roller, verdier = self.s.roller, self.s.verdier
        beste, beste_kost = None, None
        for perm in itertools.permutations(roller):
            eier = dict(zip(verdier, perm))
            kost = sum(self.avstand(r, eier[k]) for r, h in self.s.hender.items() for k in h.elements())
            if beste_kost is None or kost < beste_kost:
                beste, beste_kost = eier, kost
        self.startavstand = beste_kost
        return {r: v for v, r in beste.items()}

    # ---------------------------------------------------------- planlegging
    def handling(self, r):
        if self.plan_runde != self.s.runde:
            self._planlegg()
            self.plan_runde = self.s.runde
        return self.handlinger.get(r, {"notater": "", "vent": False})

    def _ned(self, kort, under):
        """Kort som skal ned i undertreet til «under», lengst reise først."""
        ut = [k for k in kort.elements() if self.eier[k] in self.undertre[under]]
        return sorted(ut, key=lambda k: -self.avstand(under, self.eier[k]))

    def _opp(self, kort, under):
        """Kort som skal ut av undertreet til «under», lengst reise først."""
        ut = [k for k in kort.elements() if self.eier[k] not in self.undertre[under]]
        return sorted(ut, key=lambda k: -self.avstand(under, self.eier[k]))

    def _planlegg(self):
        s = self.s
        R = s.roller
        start = {r: Counter(h) for r, h in s.hender.items()}
        res = {r: s.reservert(r) for r in R}
        brukt = {r: Counter() for r in R}
        proj = {r: Counter(h) for r, h in s.hender.items()}
        if s.sprak == "en":
            akt = {r: {"notater": f"Answer key: {r} collects {s.navn(self.maal[r])}s.", "vent": False} for r in R}
        else:
            akt = {r: {"notater": f"Fasit: {r} samler {self.maal[r]}.", "vent": False} for r in R}

        # 1. Svar på forespørslene fra forrige runde med de planlagte returkortene
        svar = 0
        for f in list(s.apne.values()):
            L, S = f["fra"], f["til"]
            ledig = start[S] - res[S] - brukt[S]
            retur = self.planlagt_retur.pop((L, S), None)
            if retur is None or not _inneholder(ledig, retur):
                kand = self._opp(ledig, S) + [k for k in ledig.elements() if self.eier[k] in self.undertre[S]]
                retur = kand[:len(f["gir"])] if len(kand) >= len(f["gir"]) else None
            if retur is None:
                akt[S].setdefault("svar_pa_foresporsler", []).append({"fra": L, "aksepter": False})
                continue
            akt[S].setdefault("svar_pa_foresporsler", []).append({"fra": L, "aksepter": True, "sender": retur})
            brukt[S] += Counter(retur)
            proj[S] = proj[S] - Counter(retur) + Counter(f["gir"])
            proj[L] = proj[L] - Counter(f["gir"]) + Counter(retur)
            svar += 1

        # 2. Nye bytter der begge parter kommer nærmere målet, nederste nivå først
        tilbudt = {r: Counter() for r in R}
        planer = []
        for L, S in self.kanter:
            ledig_L = start[L] - res[L] - brukt[L] - tilbudt[L]
            pool_S = proj[S] - tilbudt[S]
            ned, opp = self._ned(ledig_L, S), self._opp(pool_S, S)
            k = min(len(ned), len(opp), self.maks)
            if k:
                planer.append((L, S, ned[:k], opp[:k]))
                tilbudt[L] += Counter(ned[:k])
                tilbudt[S] += Counter(opp[:k])

        # 3. Ingenting i bevegelse: gjør et transittbytte
        if not planer and svar == 0:
            t = self._transitt(start, res, brukt, proj)
            if t:
                planer.append(t)
                self.transitter += 1
                akt[t[0]]["notater"] += (" Transit swap to get cards moving." if s.sprak == "en"
                                         else " Transittbytte for å få kort i bevegelse.")

        for L, S, gir, retur in planer:
            akt[L].setdefault("kortforesporsler", []).append({"til": S, "gir": gir})
            self.planlagt_retur[(L, S)] = retur
        self.handlinger = akt

    def _nyttige_kanter(self, hender):
        return sum(1 for L, S in self.kanter if self._ned(hender[L], S) and self._opp(hender[S], S))

    def _transitt(self, start, res, brukt, proj):
        kandidater = []
        for L, S in self.kanter:
            ledig_L = start[L] - res[L] - brukt[L]
            pool_S = proj[S]
            if not ledig_L or not pool_S:
                continue
            opp, ned = self._opp(pool_S, S), self._ned(ledig_L, S)
            if opp and not ned:      # dra et kort oppover; lederen sender et kort den ikke trenger nedover
                gir, retur = [next(ledig_L.elements())], [opp[0]]
            elif ned and not opp:    # skyv et kort nedover; den underordnede sender et kort opp midlertidig
                gir, retur = [ned[0]], [next(pool_S.elements())]
            else:
                continue
            if (L, S, retur[0], gir[0]) == self.siste_transitt:   # ikke reverser forrige transitt
                continue
            ny = {r: Counter(h) for r, h in proj.items()}
            ny[L] = ny[L] - Counter(gir) + Counter(retur)
            ny[S] = ny[S] - Counter(retur) + Counter(gir)
            kandidater.append((self._nyttige_kanter(ny), self.rng.random(), (L, S, gir, retur)))
        if not kandidater:
            return None
        valgt = max(kandidater)[2]
        self.siste_transitt = (valgt[0], valgt[1], valgt[2][0], valgt[3][0])
        return valgt


class ByraakratAgent:
    def __init__(self, rolle, planlegger):
        self.rolle, self.p = rolle, planlegger

    def handle(self, system, prompt, verktoy_def):
        return self.p.handling(self.rolle), {"modell": "fasit", "inn": 0, "ut": 0, "kall": 0, "tekst": "", "feil": None}

    def debrief(self, system, tekst):
        return "(fasit – ingen debrief)", {"feil": None, "inn": 0, "ut": 0, "kall": 0}
