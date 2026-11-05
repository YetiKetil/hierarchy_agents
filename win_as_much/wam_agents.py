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

NOTES = {"type": "string",
         "description": "Your private thoughts and plans. Nobody else sees them. You will see them again next "
                        "time it is your turn (they replace your earlier notes)."}
CHOICE = {"type": "string", "enum": ["X", "Y"]}


def _tool(name, description, props, required):
    return {"name": name, "description": description,
            "input_schema": {"type": "object", "properties": props, "required": required}}


def tool_write_down():
    return _tool("write_down", "Write down your own vote for this round. Nobody else sees it.",
                 {"notes": NOTES, "vote": CHOICE}, ["notes", "vote"])


def tool_prepare(members):
    return _tool("prepare", "Speak to your group before the representatives' meeting, and nominate a representative.",
                 {"notes": NOTES, "message": {"type": "string", "description": "What you say to your group."},
                  "nominee": {"type": "string", "enum": members, "description": "Who should represent the group."}},
                 ["notes", "message", "nominee"])


def tool_meeting(last):
    props = {"notes": NOTES, "statement": {"type": "string", "description": "What you say in the meeting."}}
    req = ["notes", "statement"]
    if last:
        props["commitment"] = {"type": "string", "enum": ["X", "Y", "none"],
                               "description": "What, if anything, you have committed your group to choosing in this round."}
        req.append("commitment")
    return _tool("speak_in_meeting", "Make your statement in the representatives' meeting.", props, req)


def tool_report():
    return _tool("report_to_group", "Report back to your group after the meeting.",
                 {"notes": NOTES, "report": {"type": "string", "description": "What you tell your group."}},
                 ["notes", "report"])


def tool_discuss():
    return _tool("discuss", "Speak in your group's discussion and say which choice you now propose.",
                 {"notes": NOTES, "message": {"type": "string", "description": "What you say to your group."},
                  "proposal": {**CHOICE, "description": "The choice you now propose the group hands in."}},
                 ["notes", "message", "proposal"])


# ---------------------------------------------------------------------------- prompts

def schedule_text(stop_shown=31):
    lines = []
    for n, mult, meeting in SCHEDULE_31[:stop_shown]:
        what = "representatives' meeting, then group decision" if meeting else "group decision"
        lines.append(f"Round {n}: {what}" + (f" (result ×{mult})" if mult > 1 else ""))
    return "\n".join(lines)


def system_prompt(game, agent):
    cfg = game.cfg
    g = agent[:-1]
    others = [a for a in game.agents[g] if a != agent]
    parts = [f"You are participant {agent}, a member of Group {g}. Five groups of three people take part in this "
             f"exercise. The other members of your group are {others[0]} and {others[1]}."]
    sheet = cfg["rules_text"].strip()
    if cfg.get("show_schedule", True):
        sheet += "\n\nScore scheme – the consecutive rounds:\n" + schedule_text()
    parts.append("THE SHEET EVERY PARTICIPANT HAS RECEIVED\n" + sheet)
    extra = ((cfg.get("group_settings") or {}).get(g) or {}).get("extra") or cfg.get("extra_for_all")
    if extra:
        parts.append("ADDITIONAL INFORMATION\n" + extra.strip())
    how = [
        "Each round, you first write down your own vote privately. Then your group confers until it agrees, "
        "and the group's choice is handed in to the administrator.",
        "In rounds with a representatives' meeting, your group first chooses one representative, who meets the "
        "representatives of the other groups. Only the representatives are present at the meeting. Afterwards the "
        "representative reports back, and then the group decides.",
        "After each round, the administrator announces " + ("every group's choice and " if cfg.get("reveal_choices", True) else "")
        + "the scores.",
        "You can only talk to your own group, and to the other representatives if you are your group's representative.",
        "You act by calling the tool you are given. Your notes are private.",
    ]
    if cfg.get("tell_end"):
        how.append(f"The administrator has told everyone that the exercise ends after round {game.stop_after()}.")
    parts.append("HOW IT WORKS HERE\n" + "\n".join("- " + h for h in how))
    return "\n\n".join(parts)


def history_text(game, agent):
    memory = game.cfg.get("memory_rounds")
    now = game.current["round"] if game.current else (game.rounds[-1]["round"] + 1 if game.rounds else 1)
    lines, last = [], None
    for n, text in game.history[agent]:
        if memory is not None and n < now - memory:
            continue
        if n != last:
            lines.append(f"Round {n}:")
            last = n
        lines.append("  " + text)
    return "\n".join(lines) if lines else "(nothing yet)"


def round_prompt(game, agent, step):
    parts = ["SCOREBOARD\n" + game.scoreboard(),
             "WHAT YOU HAVE SEEN AND HEARD SO FAR (oldest first)\n" + history_text(game, agent)]
    if game.notes[agent]:
        parts.append("YOUR PRIVATE NOTES FROM LAST TIME\n" + game.notes[agent])
    parts.append(step)
    return "\n\n".join(parts)


def debrief_prompt(game, agent):
    qs = game.cfg["debrief"]["questions"]
    return ("SCOREBOARD\n" + game.scoreboard() + "\n\nEVERYTHING YOU SAW AND HEARD\n" + history_text(game, agent) +
            "\n\nThe exercise is over. Answer these questions briefly and honestly, in the first person:\n" +
            "\n".join(f"{i}. {q}" for i, q in enumerate(qs, 1)))


# ---------------------------------------------------------------------------- participants

class Member:
    """One language-model participant."""

    def __init__(self, agent, provider):
        self.agent, self.provider = agent, provider

    def act(self, system, prompt, tool):
        return self.provider.act(system, prompt, tool, reminder=f"IMPORTANT: Answer by calling the tool “{tool['name']}”.")

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
            members[a] = Member(a, prov)
    return members


def group_kind(cfg, g):
    gs = (cfg.get("group_settings") or {}).get(g) or {}
    return ("bot", gs.get("strategy", "tit_for_tat")) if gs.get("type") == "bot" else ("llm", None)
