# HIERARCHY with AI agents – for advanced users

This guide explains how the program works, so you can change it, extend it and design your own experiments.

## How it works

| File | What it does |
|---|---|
| `motor.py` | The game engine. It owns the cards, enforces the channels and exchange rules, rejects illegal actions, and measures progress. No AI here. |
| `agenter.py` | What each agent sees: the system prompt, the round prompt and the tool it answers with. Also the random test agent. |
| `tekster.py` | Every text the agents see, in Norwegian and English. |
| `llm.py` | **Everything that talks to a language model.** Claude and Gemini are implemented here. This is where you add providers. |
| `kjor.py` / `run.py` | Runs games, calls the agents in parallel each round and saves the logs. |
| `byraakrat.py` | The answer key: an algorithm with full overview that plays by the same rules. |
| `konfig.py` | Reads condition files, with inheritance. |
| `oppsummer.py` / `summarize.py`, `vis_spill.py` / `show_game.py` | Analysis and reading of logs. |
| `replay.html` | The replay page. It only reads log files; it has no connection to the program. |

### One round, step by step

1. The engine works out which agents are to act. An agent that has chosen to wait is skipped until something happens to it, but everyone is woken every fifth round.
2. For each of those agents, the program builds a text containing:
   - the role instructions,
   - the agent’s position in the hierarchy,
   - its cards,
   - everything it has sent and received so far,
   - the private notes it wrote to itself last time.
3. The text is sent to the language model together with one tool, `action`. The model answers by filling in the tool with:
   - notes to itself,
   - messages,
   - card requests,
   - replies to requests,
   - optionally a wish to wait.
4. The engine checks every action against the rules, executes exchanges, and delivers messages for the next round.

The model remembers nothing between calls. What makes agent D “D” is only the text it is sent. Its notes are its only way of carrying a plan from one round to the next.

## Writing your own condition

A condition file can inherit from another and only list what is different:

```yaml
# betingelser/en/my_condition.yaml
arver: alle_kjenner_maalet.yaml          # inherit everything from this file
navn: my_condition                       # name used for the log folder
modell: gemini-3.8-flash                 # default model for all roles
roller:
  A:
    modell: claude-sonnet-5-5            # a different model for the top manager
    tillegg: >
      You prefer to give clear instructions and check that they are followed.
tilleggsinstruks:                        # extra text for all seven agents
  overskrift: Our working agreement
  tekst: |
    Anything you want every agent to be told.
```

Every setting is explained (in Norwegian) in `betingelser/grunnbetingelse.yaml`. The glossary below translates the names.

Command-line flags override the file:
- `--model` sets the model for all roles, and removes any per-role models.
- `--max-rounds` overrides the maximum number of rounds.
- `--concurrent` limits simultaneous API calls.

## Adding a model provider

All model calls go through `llm.py`. A provider is a class with two methods:

```python
class MyProvider:
    key_names = ("MY_API_KEY",)              # environment variable(s) holding the key

    def __init__(self, model, max_tokens=6000, temperature=None, force_tool=False, debrief_max_tokens=4000):
        ...                                  # create the client

    def act(self, system, prompt, tool, reminder=""):
        # Send system + prompt with `tool` (a JSON-schema tool definition) and force the model to call it.
        # Return (the tool arguments as a dict, info) – see _info() for the info keys.
        ...

    def reply(self, system, prompt):
        # Free-text answer for the debrief. Return (text, info).
        ...
```

Register it in `PROVIDERS` at the bottom of `llm.py`. You can then choose it in a condition file with `leverandor: myprovider`, or on the command line with `--provider myprovider`. If its model names are recognisable, add them to `guess_provider()` too.

The two existing classes show how to handle retries, token counting and answers without a tool call. Most chat APIs with function calling can be adapted in 30–60 lines.

## Ideas for experiments

- **Models.** Run the same condition and seeds with Gemini and Claude, or with a small and a large model. Do they fail in the same places?
- **Mixed organisations.** Give the top manager a stronger model than the rest, or the other way round.
- **Instructions.** Write your own version of the intention or procedure instruction. Which single sentence makes the biggest difference?
- **Structure.** Add a side channel between B and C (`struktur: sidekanaler: [[B, C]]`), or let subordinates start exchanges (`regler: underordnet_kan_be_om_bytte: true`).
- **Communication.** Limit message length, limit messages per round, or make some messages disappear (`regler: maks_tegn_per_melding`, `maks_meldinger_per_runde`, `tap_sannsynlighet`).
- **Memory.** Let agents only remember the last few rounds (`hukommelse_runder: 3`).
- **Learning.** Give the agents a previous game and its debrief before they play again (`forhistorie`, see `betingelser/andre_forsok.yaml`).
- **Analysis.** The logs are plain JSON. Measure something new: who becomes a bottleneck, how information travels, how often agents repeat themselves.

Run each condition several times, with `--games 5` for example. Language models give different courses from one run to the next, so one game is an anecdote, not a finding.

## The log format

Each game is one JSON file. The most useful keys:

| Key | Content |
|---|---|
| `konfig` | the full condition used |
| `start_hender`, `slutt_hender` | hands at the start and end |
| `runder` | one entry per round, with `hender_start` (hands), `handlinger` (each agent’s action, including `notater`), `hendelser` (what happened) and `uorden_etter` (shortfall) |
| `perspektiv` | exactly what each agent was sent and answered, round by round |
| `debrief` | each agent’s answers after the game |
| `maalinger` | summary measures |
| `tokens` | token use per role |

Each entry in `hendelser` has a `type`:
- `melding` (message)
- `foresporsel` (request)
- `bytte` (swap)
- `avslag` (declined)
- `trukket` (withdrawn)
- `avvist` (rejected by the engine)

Cards are always stored under their Norwegian names, whatever language the game was played in.

## Glossary (Norwegian → English)

| Norwegian | English |
|---|---|
| betingelse, betingelser | condition, conditions |
| runde, runder | round, rounds |
| kort, hender | cards, hands |
| ess, konge, dame, knekt, tier, nier, åtter | ace, king, queen, jack, ten, nine, eight |
| melding, bytte, forespørsel | message, swap, request |
| avvist, avslag, trukket | rejected, declined, withdrawn |
| uorden | shortfall (cards missing before everyone has four of a kind) |
| utfall: løst, stillstand, tidsgrense | outcome: solved, standstill, time limit |
| fasit | answer key |
| leder, underordnet, toppsjef | leader, subordinate, top manager |
| notater, vent | notes, wait |
| maal, maal_kjent_for | goal, who knows the goal |
| struktur, leder_av, sidekanaler | structure, reports to, side channels |
| regler | rules |
| tilleggsinstruks, tillegg | additional instruction, extra text for a role |
| forhistorie | history from an earlier game |
| sprak, leverandor, modell | language, provider, model |
| samtidige_kall, maks_runder, maks_tokens | concurrent calls, max rounds, max tokens per answer |
| hukommelse_runder | how many rounds of history an agent sees |
| kortomtale_oppover | messages upwards that mention card values |
| utdeling: tilfeldig, maks_spredning, manuell | deal: random, maximum spread, manual |
| arver | inherits from |
