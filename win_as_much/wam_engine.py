"""
WIN AS MUCH AS YOU CAN – the game engine.

Five groups choose X or Y in consecutive rounds. The result of each round depends on how
many groups chose X (see PAYOFF). Some rounds are multiplied by 3, 5 or 10, and before those
rounds each group sends a representative to meet the other groups' representatives.

The engine keeps the scores, the schedule and – importantly – what each participant can
see. Every event is delivered only to those who would see it in the classroom:
a private vote only to the voter, a group discussion only to that group, the
representatives' meeting only to the representatives, and the results to everyone.
No AI here.
"""
import copy
import random
from pathlib import Path

import yaml

GROUPS = ["1", "2", "3", "4", "5"]

# number of groups choosing X -> (what each X group gets, what each Y group gets), before the multiplier
PAYOFF = {5: (-1000, None), 4: (2000, -8000), 3: (4000, -6000), 2: (6000, -4000), 1: (8000, -2000), 0: (None, 1000)}

# (round, multiplier, representatives' meeting) – the schedule on the participants' sheet
SCHEDULE_31 = [
    (1, 1, False), (2, 1, False), (3, 1, False), (4, 1, False), (5, 3, True), (6, 1, False), (7, 1, False),
    (8, 5, True), (9, 1, False), (10, 10, True), (11, 1, False), (12, 3, True), (13, 1, False), (14, 1, False),
    (15, 5, True), (16, 1, False), (17, 10, True), (18, 1, False), (19, 3, True), (20, 1, False), (21, 1, False),
    (22, 5, True), (23, 1, False), (24, 10, True), (25, 1, False), (26, 3, True), (27, 1, False), (28, 1, False),
    (29, 5, True), (30, 1, False), (31, 10, True),
]


def load_condition(path):
    """Reads a condition file. A file can inherit from another with `inherits: other.yaml`."""
    path = Path(path)
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if "inherits" in data:
        base = load_condition(path.parent / data.pop("inherits"))
        base.pop("name", None)
        data = _merge(base, data)
    data.setdefault("name", path.stem)
    return data


def _merge(base, over):
    out = copy.deepcopy(base)
    for k, v in over.items():
        out[k] = _merge(out[k], v) if isinstance(v, dict) and isinstance(out.get(k), dict) else copy.deepcopy(v)
    return out


def payoffs(choices, multiplier):
    """choices: group -> 'X' or 'Y'. Returns group -> points for this round."""
    n_x = sum(c == "X" for c in choices.values())
    x_gets, y_gets = PAYOFF[n_x]
    return {g: (x_gets if c == "X" else y_gets) * multiplier for g, c in choices.items()}


def fmt(n):
    return f"{n:+,}".replace(",", " ")


class Game:
    def __init__(self, cfg, seed):
        self.cfg = cfg
        self.seed = seed
        self.rng = random.Random(seed)
        self.members = list(cfg.get("members", ["A", "B", "C"]))
        self.agents = {g: [f"{g}{m}" for m in self.members] for g in GROUPS}
        self.all_agents = [a for g in GROUPS for a in self.agents[g]]
        self.totals = {g: 0 for g in GROUPS}
        self.rounds = []                       # one record per finished round
        self.history = {a: [] for a in self.all_agents}   # (round, text) each agent has seen
        self.notes = {a: "" for a in self.all_agents}
        self.current = None                    # record of the round being played
        self.stopped = False
        self.rep_count = {g: 0 for g in GROUPS}

    # ------------------------------------------------------------------ schedule
    def schedule(self, n):
        return SCHEDULE_31[n - 1]

    def stop_after(self):
        return min(int(self.cfg.get("stop_after", 10)), len(SCHEDULE_31))

    # ------------------------------------------------------------------ visibility
    def tell(self, agents, text):
        n = self.current["round"] if self.current else 0
        for a in agents:
            self.history[a].append((n, text))

    def tell_group(self, g, text):
        self.tell(self.agents[g], text)

    # ------------------------------------------------------------------ round
    def start_round(self, n):
        _, mult, meeting = self.schedule(n)
        self.current = {"round": n, "multiplier": mult, "meeting": meeting, "private": {}, "prep": {},
                        "representatives": {}, "meeting_log": [], "reports": {}, "discussion": {},
                        "decisions": {}, "result": None}
        return self.current

    def choose_representative(self, g, nominations):
        """nominations: member id -> nominee id. Most nominations wins; a tie rotates through the members."""
        counts = {}
        for nominee in nominations.values():
            if nominee in self.agents[g]:
                counts[nominee] = counts.get(nominee, 0) + 1
        if counts:
            top = max(counts.values())
            tied = [a for a in self.agents[g] if counts.get(a) == top]
        else:
            tied = list(self.agents[g])
        rep = tied[self.rep_count[g] % len(tied)]
        self.rep_count[g] += 1
        return rep

    def finish_round(self):
        rec = self.current
        choices = {g: rec["decisions"][g]["choice"] for g in GROUPS}
        points = payoffs(choices, rec["multiplier"])
        for g in GROUPS:
            self.totals[g] += points[g]
        n_x = sum(c == "X" for c in choices.values())
        rec["result"] = {"choices": choices, "points": points, "totals": dict(self.totals), "n_x": n_x}
        self.rounds.append(rec)
        line = self.announcement(rec)
        self.tell(self.all_agents, line)
        if rec["round"] >= self.stop_after():
            self.stopped = True
            self.tell(self.all_agents, "The administrator has stopped the exercise. There will be no more rounds.")
        self.current = None
        return rec

    def announcement(self, rec):
        res, m = rec["result"], rec["multiplier"]
        n_x = res["n_x"]
        x_gets, y_gets = PAYOFF[n_x]
        parts = []
        if x_gets is not None:
            parts.append(f"each X group {'wins' if x_gets > 0 else 'loses'} {abs(x_gets) * m:,}".replace(",", " "))
        if y_gets is not None:
            parts.append(f"each Y group {'wins' if y_gets > 0 else 'loses'} {abs(y_gets) * m:,}".replace(",", " "))
        if self.cfg.get("reveal_choices", True):
            who = ", ".join(f"Group {g}: {res['choices'][g]}" for g in GROUPS)
        else:
            who = "individual choices are not revealed"
        mult = f" (×{m})" if m > 1 else ""
        totals = ", ".join(f"Group {g} {fmt(res['totals'][g])}" for g in GROUPS)
        return (f"RESULT OF ROUND {rec['round']}{mult}: {who}. That is {n_x} X and {5 - n_x} Y, so "
                f"{' and '.join(parts)}. Totals now: {totals}.")

    def scoreboard(self):
        """A compact table of all finished rounds, for the prompts."""
        if not self.rounds:
            return "(no rounds played yet)"
        lines = ["Round  Mult  " + "  ".join(f"G{g}" for g in GROUPS)]
        for rec in self.rounds:
            ch = rec["result"]["choices"] if self.cfg.get("reveal_choices", True) else {g: "?" for g in GROUPS}
            lines.append(f"{rec['round']:>5}  ×{rec['multiplier']:<3} " + "   ".join(ch[g] for g in GROUPS))
        lines.append("Totals: " + ", ".join(f"Group {g} {fmt(self.totals[g])}" for g in GROUPS))
        return "\n".join(lines)

    # ------------------------------------------------------------------ measures
    def measures(self):
        played = len(self.rounds)
        ideal = sum(5 * 1000 * rec["multiplier"] for rec in self.rounds)
        decisions = [rec["decisions"][g] for rec in self.rounds for g in GROUPS]
        y_share = sum(d["choice"] == "Y" for d in decisions) / len(decisions) if decisions else 0
        conform, private_total = 0, 0
        for rec in self.rounds:
            for a, pv in rec["private"].items():
                private_total += 1
                conform += pv["vote"] == rec["decisions"][a[0]]["choice"]
        promises = []
        for rec in self.rounds:
            if not rec["meeting"]:
                continue
            for g, rep in rec["representatives"].items():
                commit = rec.get("commitments", {}).get(g)
                if commit in ("X", "Y"):
                    promises.append({"round": rec["round"], "group": g, "promised": commit,
                                     "chose": rec["decisions"][g]["choice"],
                                     "kept": commit == rec["decisions"][g]["choice"]})
        return {
            "rounds": played,
            "totals": dict(self.totals),
            "collective": sum(self.totals.values()),
            "ideal": ideal,
            "y_share": round(y_share, 3),
            "y_per_round": [5 - rec["result"]["n_x"] for rec in self.rounds],
            "unanimous_share": round(sum(d.get("unanimous", False) for d in decisions) / len(decisions), 3) if decisions else 0,
            "private_matches_group": round(conform / private_total, 3) if private_total else None,
            "promises": promises,
            "promises_kept": sum(p["kept"] for p in promises),
            "promises_made": len(promises),
        }
