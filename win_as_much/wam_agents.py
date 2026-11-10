"""
WIN AS MUCH AS YOU CAN – the participants.

Each group is either three language-model agents who confer before handing in a choice,
or a simple rule-based "bot" group used as a benchmark. Each agent is a stateless call to a
language model: everything it knows is rebuilt from what the engine has let it see.
"""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import llm  # noqa: E402  (the shared provider layer from the HIERARCHY kit)

from wam_engine import GROUPS, SCHEDULE_31  # noqa: E402

from wam_texts import T, choice_name, group_name  # noqa: E402


def _tool(name, description, props, required):
    return {"name": name, "description": description,
            "input_schema": {"type": "object", "properties": props, "required": required}}


def _notes(cfg):
    return {"type": "string", "description": T(cfg, "notes_desc")}


def _choice(cfg, description=None):
    spec = {"type": "string", "enum": [choice_name(cfg, "X"), choice_name(cfg, "Y")]}
    if description:
        spec["description"] = description
    return spec


def tool_write_down(cfg):
    return _tool("write_down", T(cfg, "write_down_desc"), {"notes": _notes(cfg), "vote": _choice(cfg)}, ["notes", "vote"])


def tool_prepare(cfg, members):
    return _tool("prepare", T(cfg, "prepare_desc"),
                 {"notes": _notes(cfg), "message": {"type": "string", "description": T(cfg, "message_desc")},
                  "nominee": {"type": "string", "enum": members, "description": T(cfg, "nominee_desc")}},
                 ["notes", "message", "nominee"])


def tool_meeting(cfg, last):
    props = {"notes": _notes(cfg), "statement": {"type": "string", "description": T(cfg, "statement_desc")}}
    req = ["notes", "statement"]
    if last:
        props["commitment"] = {"type": "string", "enum": [choice_name(cfg, "X"), choice_name(cfg, "Y"), T(cfg, "none")],
                               "description": T(cfg, "commitment_desc")}
        req.append("commitment")
    return _tool("speak_in_meeting", T(cfg, "meeting_desc"), props, req)


def tool_report(cfg):
    return _tool("report_to_group", T(cfg, "report_desc"),
                 {"notes": _notes(cfg), "report": {"type": "string", "description": T(cfg, "report_field_desc")}},
                 ["notes", "report"])


def tool_discuss(cfg):
    return _tool("discuss", T(cfg, "discuss_desc"),
                 {"notes": _notes(cfg), "message": {"type": "string", "description": T(cfg, "message_desc")},
                  "proposal": _choice(cfg, T(cfg, "proposal_desc"))},
                 ["notes", "message", "proposal"])


# ---------------------------------------------------------------------------- prompts

def schedule_text(cfg, stop_shown=31):
    lines = []
    for n, mult, meeting in SCHEDULE_31[:stop_shown]:
        what = T(cfg, "sched_meeting") if meeting else T(cfg, "sched_plain")
        lines.append(T(cfg, "sched_line", n=n, what=what, mult=T(cfg, "sched_mult", m=mult) if mult > 1 else ""))
    return "\n".join(lines)


def system_prompt(game, agent):
    cfg = game.cfg
    g = agent[:-1]
    others = [a for a in game.agents[g] if a != agent]
    parts = [T(cfg, "you_are", agent=agent, group=group_name(cfg, g), o1=others[0], o2=others[1])]
    sheet = cfg["rules_text"].strip()
    if cfg.get("show_schedule", True):
        sheet += "\n\n" + T(cfg, "sched_head") + "\n" + schedule_text(cfg)
    parts.append(T(cfg, "sheet_head") + "\n" + sheet)
    extra = ((cfg.get("group_settings") or {}).get(g) or {}).get("extra") or cfg.get("extra_for_all")
    if extra:
        parts.append(T(cfg, "extra_head") + "\n" + extra.strip())
    how = [T(cfg, "how_1"), T(cfg, "how_2"),
           T(cfg, "how_3", reveal=T(cfg, "how_reveal") if cfg.get("reveal_choices", True) else ""),
           T(cfg, "how_4"), T(cfg, "how_5")]
    if cfg.get("tell_end"):
        how.append(T(cfg, "how_end", n=game.stop_after()))
    parts.append(T(cfg, "how_head") + "\n" + "\n".join("- " + h for h in how))
    return "\n\n".join(parts)


def history_text(game, agent):
    cfg = game.cfg
    memory = cfg.get("memory_rounds")
    now = game.current["round"] if game.current else (game.rounds[-1]["round"] + 1 if game.rounds else 1)
    lines, last = [], None
    for n, text in game.history[agent]:
        if memory is not None and n < now - memory:
            continue
        if n != last:
            lines.append(T(cfg, "round_label", n=n))
            last = n
        lines.append("  " + text)
    return "\n".join(lines) if lines else T(cfg, "nothing_yet")


def round_prompt(game, agent, step):
    cfg = game.cfg
    parts = [T(cfg, "h_scoreboard") + "\n" + game.scoreboard(),
             T(cfg, "h_seen") + "\n" + history_text(game, agent)]
    if game.notes[agent]:
        parts.append(T(cfg, "h_notes") + "\n" + game.notes[agent])
    parts.append(step)
    return "\n\n".join(parts)


def debrief_prompt(game, agent):
    cfg = game.cfg
    qs = cfg["debrief"]["questions"]
    return (T(cfg, "h_scoreboard") + "\n" + game.scoreboard() + "\n\n" + T(cfg, "h_everything") + "\n" +
            history_text(game, agent) + "\n\n" + T(cfg, "debrief_intro") + "\n" +
            "\n".join(f"{i}. {q}" for i, q in enumerate(qs, 1)))


# ---------------------------------------------------------------------------- participants

class Member:
    """One language-model participant."""

    def __init__(self, agent, provider, reminder="IMPORTANT: Answer by calling the tool “{tool}”."):
        self.agent, self.provider, self.reminder = agent, provider, reminder

    def act(self, system, prompt, tool):
        return self.provider.act(system, prompt, tool, reminder=self.reminder.format(tool=tool["name"]))

    def reply(self, system, prompt):
        return self.provider.reply(system, prompt)


class TestProvider:
    """Fills in the tools at random. Used to test the set-up without an API key."""
    model = "test"

    def __init__(self, seed):
        self.rng = random.Random(seed)

    def act(self, system, prompt, tool, reminder=""):
        out = {}
        for k, spec in tool["input_schema"]["properties"].items():
            out[k] = self.rng.choice(spec["enum"]) if "enum" in spec else f"(test {k})"
        return out, {"modell": "test", "inn": 0, "ut": 0, "kall": 0, "avkuttet": 0, "feil": None, "tekst": ""}

    def reply(self, system, prompt):
        return "(test debrief)", {"modell": "test", "inn": 0, "ut": 0, "kall": 0, "avkuttet": 0, "feil": None}


def bot_choice(strategy, game, g):
    """Rule-based groups, as benchmarks."""
    prev = game.rounds[-1]["result"]["choices"] if game.rounds else None
    others_prev = [prev[h] for h in GROUPS if h != g] if prev else []
    if strategy == "always_Y":
        return "Y"
    if strategy == "always_X":
        return "X"
    if strategy == "tit_for_tat":        # Y first; then Y if most other groups chose Y last round
        return "Y" if not prev or sum(c == "Y" for c in others_prev) >= 3 else "X"
    if strategy == "grim":               # Y until any other group has chosen X, then X for ever
        return "X" if any(r["result"]["choices"][h] == "X" for r in game.rounds for h in GROUPS if h != g) else "Y"
    if strategy == "random":
        return game.rng.choice(["X", "Y"])
    raise ValueError(f"Unknown bot strategy: {strategy}")


def make_members(game, test):
    """Agent id -> Member for every language-model group (bot groups get no members)."""
    cfg = game.cfg
    members = {}
    for g in GROUPS:
        gs = (cfg.get("group_settings") or {}).get(g) or {}
        if gs.get("type") == "bot":
            continue
        model = gs.get("model", cfg["model"])
        provider_name = gs.get("provider") or (cfg.get("provider") if "model" not in gs else None) or llm.guess_provider(model)
        for a in game.agents[g]:
            if test:
                prov = TestProvider(f"{game.seed}-{a}")
            else:
                prov = llm.make_provider(provider_name, model, max_tokens=cfg.get("max_tokens", 4000),
                                         temperature=cfg.get("temperature"), force_tool=False,
                                         debrief_max_tokens=cfg.get("debrief_max_tokens", 3000))
            members[a] = Member(a, prov, T(cfg, "reminder", tool="{tool}"))
    return members


def group_kind(cfg, g):
    gs = (cfg.get("group_settings") or {}).get(g) or {}
    return ("bot", gs.get("strategy", "tit_for_tat")) if gs.get("type") == "bot" else ("llm", None)
