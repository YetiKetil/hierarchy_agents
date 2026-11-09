# HIERARCHY with AI agents – student kit

In the leadership exercise HIERARCHY, seven people in a three-level hierarchy try to end up with four cards of equal value each. They may only write to their immediate leader or subordinates, and only the top manager is told what the task is.

This kit lets seven AI agents play the exercise. A game engine enforces the rules, each agent only sees its own perspective, and every game is saved as a complete log that you can replay, read and analyse. You decide which language model plays, what the agents are told, and how the organisation is set up.

The kit was made for teaching leadership. You are welcome to use it for learning and for your own experiments.

## What you need

- **Python 3.10 or newer** on your own computer. Alternatively, use Google Colab in your browser with nothing to install (see below).
- **An API key** for Gemini (Google AI Studio) or Claude (Anthropic Console).
  - A chat subscription, such as the Gemini app or Claude.ai, is not the same as API access. API use is set up and billed separately by each provider.
  - Some providers offer a free tier with strict rate limits.
- **Without a key** you can still run the answer key and the test agents. Both are free and show you how everything works.

## Quick start on your own computer

Get the kit: on [the GitHub page](https://github.com/YetiKetil/hierarchy_agents), click the green **Code** button and choose **Download ZIP**, then unpack it. Or, if you use git: `git clone https://github.com/YetiKetil/hierarchy_agents`.

```bash
pip install -r requirements.txt

# 1. Free: watch the answer key solve the task
python run.py betingelser/en/alle_kjenner_maalet.yaml --answer-key
```

Open `replay.html` in your browser by double-clicking it. Drag in the new file from the `logger` folder and press Play.

Next, add your key:

1. Copy `.env.example` to a new file called `.env`.
2. Fill in `GEMINI_API_KEY=...` or `ANTHROPIC_API_KEY=...`.
3. Never share your `.env` file.

Then run a short trial game:

```bash
# 2. A short trial game (10 rounds) with Gemini
python run.py betingelser/en/prosedyre_lappet.yaml --model gemini-3.5-flash-lite --max-rounds 10

# 3. A full game (up to 60 rounds) – with Claude this time
python run.py betingelser/en/prosedyre_lappet.yaml --model claude-haiku-5-5
```

The program prints one line per round. **Shortfall** is the number of cards the group is missing before everyone has four of a kind; 0 means the task is solved. A full game takes 5–15 minutes.

## Quick start in Google Colab

**[Open the notebook in Google Colab](https://colab.research.google.com/github/YetiKetil/hierarchy_agents/blob/main/notebooks/HIERARCHY_colab.ipynb)** and follow the cells. The notebook fetches the code from GitHub by itself. You store your key in Colab’s **Secrets** panel (the key icon on the left). At the end, you download your logs and open them in `replay.html` on your own computer.

## The conditions

The files in `betingelser/en/` describe what the agents are told. *Betingelser* is Norwegian for *conditions*.

| File | What the agents get |
|---|---|
| `grunnbetingelse.yaml` | The original exercise: only A knows the goal |
| `alle_kjenner_maalet.yaml` | Everyone knows the goal |
| `intensjon.yaml` | Everyone knows the goal, plus a shared purpose and a “we”, but no method |
| `prosedyre.yaml` | Everyone knows the goal, plus a fixed procedure: mapping, a plan, step-by-step moving |
| `prosedyre_lappet.yaml` | The procedure plus one sentence: leaders pass cards on even when it temporarily breaks their own set |
| `prosedyre_fasit.yaml` | The procedure spelled out the way the answer key solves the task: the employees finish first, the leaders last, and cards move on every line every round |
| `prosedyre_fasit_regler.yaml` | The same, with two principles rewritten as concrete rules: a leader must not complete their own set while a subordinate is still missing cards, and after two still rounds the leader must make a request |

Each game uses a numbered card deal, chosen with `--seed`. The same seed gives the same cards in every condition, so you can compare conditions, or models, fairly.

## Looking at the results

- **`replay.html`** shows a game round by round: the organisation chart with everyone’s cards, the messages, and (if you tick “Show thoughts”) each agent’s private notes. It also shows the debrief, in which each agent answers questions after the game. Switch the interface between English and Norwegian at the top.
- **`python show_game.py <log file> --thoughts`** prints a game as text. Use `--perspective D` to see exactly what agent D saw and did in every round.
- **`python summarize.py --en`** prints a table comparing all your games per condition.

Your logs are saved in `logger/`, with one folder per condition, and `logger/resultater.csv` collects the key numbers for every game.

## Examples

The `examples/` folder contains:

- **`demo_patched_procedure_seed1.json`**: a full game with the patched procedure, played by Claude Haiku. Look at round 2 (A’s plan), round 24 (a finished leader lends a card for the first time) and the debrief.
- **`answer_key_seed1.json`** and **`answer_key_seed2.json`**: the answer key solving card deals 1 and 2.

## Cost and rate limits

A full game takes roughly 100–250 API calls and 0.5–3 million input tokens. What that costs depends on the provider and model, so check their current prices before running series of games.

- **Start small.** Use `--answer-key`, then `--max-rounds 10`.
- **On a free tier,** add `--concurrent 1` so the agents do not all call the API at once. Games then take longer, but stay within the limits.
- **Model names change.** Check the providers’ model lists: [Gemini](https://ai.google.dev/gemini-api/docs/models) and [Claude](https://docs.claude.com).

## A second game: Win as much as you can

The folder `win_as_much` contains a version of the prisoner's dilemma for five groups, in which each group is three AI agents who confer before every choice, and representatives negotiate before the high-stake rounds. See `win_as_much/README.md`. To run it in Colab, use **[the second notebook](https://colab.research.google.com/github/YetiKetil/hierarchy_agents/blob/main/notebooks/WIN_AS_MUCH_colab.ipynb)**.

## Going further

`ADVANCED.md` explains how the program works, how to write your own conditions, how to add another model provider, and gives ideas for experiments.

Much of the code is written in Norwegian. `ADVANCED.md` has a glossary.
