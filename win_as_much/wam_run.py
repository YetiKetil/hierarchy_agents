"""
WIN AS MUCH AS YOU CAN – run games.

  python wam_run.py conditions/standard.yaml --test              # free test, random participants
  python wam_run.py conditions/standard.yaml --model claude-haiku-5-5
  python wam_run.py conditions/standard.yaml --model gemini-3.5-flash-lite --verbose

Each round: every member writes down a private vote; in meeting rounds the group prepares and
chooses a representative, the representatives meet, and each representative reports back;
then each group discusses until it agrees (or decides by majority) and hands in X or Y.
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

HER = Path(__file__).resolve().parent
sys.path.insert(0, str(HER))
sys.path.insert(0, str(HER.parent))
import llm  # noqa: E402

from wam_agents import (bot_choice, debrief_prompt, group_kind, make_members, round_prompt,  # noqa: E402
                        system_prompt, tool_discuss, tool_meeting, tool_prepare, tool_report, tool_write_down)
from wam_engine import GROUPS, Game, load_condition  # noqa: E402

CSV_FIELDS = ["time", "condition", "seed", "rounds", "collective", "ideal", "y_share", "unanimous_share",
              "private_matches_group", "promises_made", "promises_kept"] + [f"total_{g}" for g in GROUPS] + \
             ["calls", "errors", "tokens_in", "tokens_out", "seconds"]


class Runner:
    def __init__(self, cfg, seed, test=False, verbose=False, quiet=False):
        self.cfg, self.verbose, self.quiet = cfg, verbose, quiet
        self.game = Game(cfg, seed)
        self.members = make_members(self.game, test)
        self.systems = {a: system_prompt(self.game, a) for a in self.members}
        self.tokens = {a: Counter() for a in self.members}
        self.calls = []                 # every call: who, round, step, output (and prompt if log_prompts)
        self.errors_seen = set()
        self.fail_streak = 0
        self.pool = ThreadPoolExecutor(max_workers=cfg.get("concurrent") or 5)

    # ------------------------------------------------------------------ one call
    def ask(self, agent, step_name, tool, step_text):
        g = self.game
        prompt = round_prompt(g, agent, step_text)
        out, info = self.members[agent].act(self.systems[agent], prompt, tool)
        self.tokens[agent].update({"in": info.get("inn", 0), "out": info.get("ut", 0), "calls": info.get("kall", 1),
                                   "errors": int(bool(info.get("feil"))), "truncated": info.get("avkuttet", 0)})
        if info.get("feil"):
            self.fail_streak += 1
            if info["feil"] not in self.errors_seen:
                self.errors_seen.add(info["feil"])
                print(f"API ERROR for {agent}: {str(info['feil'])[:400]}", flush=True)
            if self.fail_streak >= 15:
                raise RuntimeError("Fifteen API calls in a row failed. Check the model name and your API key.")
        else:
            self.fail_streak = 0
        if isinstance(out.get("notes"), str) and out["notes"].strip():
            g.notes[agent] = out["notes"]
        entry = {"agent": agent, "round": g.current["round"] if g.current else None, "step": step_name,
                 "output": out, "error": info.get("feil")}
        if self.cfg.get("log_prompts"):
            entry["prompt"] = prompt
        self.calls.append(entry)
        return out

    def in_groups(self, fn, groups):
        list(self.pool.map(fn, groups))

    # ------------------------------------------------------------------ the steps of a round
    def private_votes(self, rec, llm_groups):
        n, m = rec["round"], rec["multiplier"]
        meeting = " This round starts with a representatives' meeting." if rec["meeting"] else ""
        step = (f"ROUND {n}" + (f" (result ×{m})" if m > 1 else "") + f".{meeting}\nSTEP: Before your group confers, "
                "write down your own vote for this round. Nobody else sees it.")

        def one(a):   # private votes are independent, so all members vote at the same time
            out = self.ask(a, "private_vote", tool_write_down(), step)
            vote = out.get("vote") if out.get("vote") in ("X", "Y") else None
            rec["private"][a] = {"vote": vote, "notes": out.get("notes", "")}
            if vote:
                self.game.tell([a], f"You wrote down your own vote: {vote}.")
        self.in_groups(one, [a for g in llm_groups for a in self.game.agents[g]])

    def prepare(self, rec, llm_groups):
        n, m = rec["round"], rec["multiplier"]
        step = (f"ROUND {n} (result ×{m}).\nSTEP: Before this round, each group sends one representative to meet the "
                "representatives of the other groups. Tell your group what you think the representative should aim for, "
                "and nominate a representative (you may nominate yourself).")

        def one(g):
            msgs, noms = [], {}
            for a in self.game.agents[g]:
                out = self.ask(a, "prepare", tool_prepare(self.game.agents[g]), step)
                msg = (out.get("message") or "").strip()
                noms[a] = out.get("nominee")
                msgs.append({"agent": a, "message": msg, "nominee": out.get("nominee"), "notes": out.get("notes", "")})
                self.game.tell_group(g, f"{a}: “{msg}” (nominates {out.get('nominee')} as representative)")
            rep = self.game.choose_representative(g, noms)
            rec["prep"][g] = msgs
            rec["representatives"][g] = rep
            self.game.tell_group(g, f"Your group chose {rep} as its representative.")
        self.in_groups(one, llm_groups)

    def meeting(self, rec, llm_groups):
        g_ = self.game
        n, m = rec["round"], rec["multiplier"]
        turns = int(self.cfg.get("meeting_turns", 3))
        reps = {g: rec["representatives"][g] for g in llm_groups}
        rec["commitments"] = {}
        present = ", ".join(f"Group {g}: {reps[g]}" for g in llm_groups)
        silent = [g for g in GROUPS if g not in llm_groups]
        opening = f"The representatives' meeting begins. Present: {present}."
        if silent:
            opening += " " + " ".join(f"Group {g}'s representative is present but says nothing." for g in silent)
        g_.tell(list(reps.values()), opening)
        for t in range(1, turns + 1):
            order = list(llm_groups)
            g_.rng.shuffle(order)
            for g in order:
                last = t == turns
                step = (f"ROUND {n} (result ×{m}).\nSTEP: You are Group {g}'s representative in the meeting with the other "
                        f"groups' representatives. Only the representatives are present. Statement {t} of {turns}."
                        + (" This is your last statement in the meeting. Also state what, if anything, you have "
                           "committed your group to." if last else ""))
                out = self.ask(reps[g], "meeting", tool_meeting(last), step)
                text = (out.get("statement") or "").strip()
                rec["meeting_log"].append({"turn": t, "group": g, "agent": reps[g], "statement": text,
                                           "notes": out.get("notes", ""), "commitment": out.get("commitment") if last else None})
                if last:
                    rec["commitments"][g] = out.get("commitment")
                g_.tell(list(reps.values()), f"[Meeting] {reps[g]} (Group {g}): “{text}”")
                if self.verbose:
                    print(f"   [meeting t{t}] {reps[g]}: {text[:300]}", flush=True)

    def reports(self, rec, llm_groups):
        n, m = rec["round"], rec["multiplier"]
        step = (f"ROUND {n} (result ×{m}).\nSTEP: The meeting is over. Report back to your group. They only know what "
                "you tell them.")

        def one(g):
            rep = rec["representatives"][g]
            out = self.ask(rep, "report", tool_report(), step)
            text = (out.get("report") or "").strip()
            rec["reports"][g] = {"agent": rep, "report": text, "notes": out.get("notes", "")}
            self.game.tell_group(g, f"Report from your representative {rep}: “{text}”")
            if self.verbose:
                print(f"   [report G{g}] {rep}: {text[:300]}", flush=True)
        self.in_groups(one, llm_groups)

    def discussion(self, rec, llm_groups):
        n, m = rec["round"], rec["multiplier"]
        turns = int(self.cfg.get("discussion_turns", 3))

        def one(g):
            log, decision = [], None
            last_prop = {a: (rec["private"].get(a) or {}).get("vote") for a in self.game.agents[g]}
            for t in range(1, turns + 1):
                step = (f"ROUND {n}" + (f" (result ×{m})" if m > 1 else "") + ".\nSTEP: Discuss with your group which "
                        f"choice to hand in to the administrator. Turn {t} of {turns}. The choice is handed in as soon as "
                        f"all three of you propose the same, or by majority after turn {turns}.")
                for a in self.game.agents[g]:
                    out = self.ask(a, "discussion", tool_discuss(), step)
                    msg = (out.get("message") or "").strip()
                    if out.get("proposal") in ("X", "Y"):
                        last_prop[a] = out["proposal"]
                    log.append({"turn": t, "agent": a, "message": msg, "proposal": last_prop[a], "notes": out.get("notes", "")})
                    self.game.tell_group(g, f"{a}: “{msg}” (proposes {last_prop[a]})")
                props = [p for p in last_prop.values() if p]
                if len(props) == len(last_prop) and len(set(props)) == 1:
                    decision = {"choice": props[0], "unanimous": True, "turns": t}
                    break
            if decision is None:
                props = [p for p in last_prop.values() if p] or ["Y"]
                choice = Counter(props).most_common(1)[0][0]
                decision = {"choice": choice, "unanimous": len(set(props)) == 1 and len(props) == 3, "turns": turns}
            rec["discussion"][g] = log
            rec["decisions"][g] = decision
            self.game.tell_group(g, f"Your group hands in {decision['choice']} "
                                    f"({'all agreed' if decision['unanimous'] else 'by majority'}).")
        self.in_groups(one, llm_groups)

    # ------------------------------------------------------------------ the game
    def play(self):
        g_ = self.game
        t0 = time.time()
        label = f"[{self.cfg['name']} s{g_.seed:03d}]"
        llm_groups = [g for g in GROUPS if group_kind(self.cfg, g)[0] == "llm"]
        bot_groups = [g for g in GROUPS if group_kind(self.cfg, g)[0] == "bot"]
        stopped_by_error = None
        try:
            for n in range(1, g_.stop_after() + 1):
                rec = g_.start_round(n)
                if llm_groups:
                    self.private_votes(rec, llm_groups)
                    if rec["meeting"]:
                        self.prepare(rec, llm_groups)
                        self.meeting(rec, llm_groups)
                        self.reports(rec, llm_groups)
                    self.discussion(rec, llm_groups)
                for g in bot_groups:
                    rec["decisions"][g] = {"choice": bot_choice(group_kind(self.cfg, g)[1], g_, g), "unanimous": True,
                                           "turns": 0, "bot": True}
                rec = g_.finish_round()
                if not self.quiet:
                    res = rec["result"]
                    kind = " meeting" if rec["meeting"] else "        "
                    print(f"{label} round {n:>2} ×{rec['multiplier']:<2}{kind} | " +
                          " ".join(f"G{g}:{res['choices'][g]}" for g in GROUPS) + f" | {res['n_x']} X | totals " +
                          " ".join(f"{res['totals'][g]:+}" for g in GROUPS), flush=True)
        except RuntimeError as e:
            stopped_by_error = str(e)
            print(f"{label} STOPPED: {e}", flush=True)

        debrief = {}
        if self.cfg.get("debrief", {}).get("active", True) and not stopped_by_error and self.members:
            def one(a):
                text, info = self.members[a].reply(self.systems[a], debrief_prompt(g_, a))
                self.tokens[a].update({"in": info.get("inn", 0), "out": info.get("ut", 0), "calls": info.get("kall", 1)})
                return a, text
            debrief = dict(self.pool.map(one, list(self.members)))
        self.pool.shutdown()

        total = sum(self.tokens.values(), Counter())
        return {
            "game": "win_as_much_as_you_can",
            "condition": self.cfg["name"],
            "seed": g_.seed,
            "time": datetime.now().isoformat(timespec="seconds"),
            "config": self.cfg,
            "stopped_by_error": stopped_by_error,
            "rounds": g_.rounds,
            "measures": g_.measures(),
            "debrief": debrief,
            "calls": self.calls,
            "tokens": {a: dict(t) for a, t in self.tokens.items()},
            "tokens_total": dict(total),
            "seconds": round(time.time() - t0, 1),
        }


def save(log, folder):
    folder = Path(folder)
    sub = folder / log["condition"]
    sub.mkdir(parents=True, exist_ok=True)
    path = sub / f"game_s{log['seed']:03d}_{log['time'].replace(':', '')}.json"
    path.write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    csv_path = folder / "results.csv"
    new = not csv_path.exists()
    m, t = log["measures"], log["tokens_total"]
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if new:
            w.writeheader()
        row = {"time": log["time"], "condition": log["condition"], "seed": log["seed"], "rounds": m["rounds"],
               "collective": m["collective"], "ideal": m["ideal"], "y_share": m["y_share"],
               "unanimous_share": m["unanimous_share"], "private_matches_group": m["private_matches_group"],
               "promises_made": m["promises_made"], "promises_kept": m["promises_kept"],
               "calls": t.get("calls", 0), "errors": t.get("errors", 0), "tokens_in": t.get("in", 0),
               "tokens_out": t.get("out", 0), "seconds": log["seconds"]}
        row.update({f"total_{g}": m["totals"][g] for g in GROUPS})
        w.writerow(row)
    return path


def main():
    ap = argparse.ArgumentParser(description="Run WIN AS MUCH AS YOU CAN with AI agents.")
    ap.add_argument("conditions", nargs="+", metavar="CONDITION", help="condition files (YAML)")
    ap.add_argument("--games", type=int, default=1, metavar="N", help="games per condition")
    ap.add_argument("--seed", type=int, default=1, help="first seed; game i gets seed+i (speaking order, ties)")
    ap.add_argument("--model", metavar="NAME", help="model for all language-model groups")
    ap.add_argument("--provider", choices=sorted(llm.PROVIDERS), help="override provider")
    ap.add_argument("--stop-after", type=int, metavar="N", help="round after which the administrator stops the game")
    ap.add_argument("--concurrent", type=int, metavar="N", help="max simultaneous API calls (1-5)")
    ap.add_argument("--test", action="store_true", help="random participants, no API")
    ap.add_argument("--verbose", action="store_true", help="print the meetings and reports as they happen")
    ap.add_argument("--quiet", action="store_true", help="do not print each round")
    ap.add_argument("--logs", default="logs", metavar="FOLDER", help="log folder")
    a = ap.parse_args()

    llm.load_env(Path.cwd(), HER, HER.parent)
    jobs = []
    for path in a.conditions:
        cfg = load_condition(path)
        if a.model:
            cfg["model"] = a.model
            cfg["provider"] = a.provider or llm.guess_provider(a.model)
            for gs in (cfg.get("group_settings") or {}).values():
                if isinstance(gs, dict):
                    gs.pop("model", None)
                    gs.pop("provider", None)
        elif a.provider:
            cfg["provider"] = a.provider
        if a.stop_after:
            cfg["stop_after"] = a.stop_after
        if a.concurrent:
            cfg["concurrent"] = a.concurrent
        if a.test:
            cfg["name"] = "TEST-" + cfg["name"]
        jobs += [(cfg, a.seed + i) for i in range(a.games)]

    if not a.test:
        missing = set()
        for cfg, _ in jobs:
            for g in GROUPS:
                gs = (cfg.get("group_settings") or {}).get(g) or {}
                if gs.get("type") == "bot":
                    continue
                model = gs.get("model", cfg["model"])
                prov = gs.get("provider") or (cfg.get("provider") if "model" not in gs else None) or llm.guess_provider(model)
                if prov not in llm.PROVIDERS:
                    sys.exit(f"Unknown provider for model '{model}'. Use --provider {' | '.join(llm.PROVIDERS)}")
                key = llm.missing_key(prov)
                if key:
                    missing.add(key)
        if missing:
            sys.exit("Missing API key: " + ", ".join(sorted(missing)) + ". Put it in a .env file or an environment "
                     "variable, or run with --test.")

    for cfg, seed in jobs:
        log = Runner(cfg, seed, test=a.test, verbose=a.verbose, quiet=a.quiet).play()
        path = save(log, a.logs)
        m = log["measures"]
        print(f"Saved {path}  (collective {m['collective']:+} of a possible {m['ideal']:+}, "
              f"promises kept {m['promises_kept']}/{m['promises_made']}, {log['tokens_total'].get('calls', 0)} API calls)")


if __name__ == "__main__":
    main()
