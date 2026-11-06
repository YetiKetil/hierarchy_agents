# WIN AS MUCH AS YOU CAN – with AI agents

A version of the prisoner's dilemma for five groups. In each round, every group chooses X or Y, and the result depends on what the other groups choose. Some rounds are multiplied by 3, 5 or 10, and before those rounds each group sends a representative to meet the other groups' representatives.

Here, every group is three AI agents, as in the classroom:

1. **Private votes.** Each member writes down a private vote.
2. **Representatives' meeting.** In the rounds with a meeting, the group prepares and chooses a representative. The representatives meet with only each other present, and each representative reports back to the group.
3. **Group decision.** The group discusses until all three propose the same choice, or decides by majority after three turns.
4. **Results.** The administrator announces every group's choice and the new totals.

Each agent only sees what a participant in the room would see. The sheet shows 31 rounds, but the administrator stops after round 10 without warning.

## Running a game

From the `win_as_much` folder:

```bash
python wam_run.py conditions/standard.yaml --test                       # free: random participants, no API
python wam_run.py conditions/standard.yaml --model claude-haiku-5-5
python wam_run.py conditions/standard.yaml --model gemini-3.5-flash-lite --verbose
```

`--verbose` prints the meetings and the reports as they happen. A game takes 10–20 minutes and about 600 API calls. The API key is read from the same `.env` file as in the HIERARCHY kit, one folder up. On a free tier, add `--concurrent 1`.

## Conditions

| File | What changes |
|---|---|
| `standard.yaml` | The exercise as run with people. |
| `known_end.yaml` | The agents are told that the game ends after round 10. Game theory predicts defection in the last round. |
| `two_bot_groups.yaml` | Groups 4 and 5 are rule-based. One copies what most groups did last round; the other always chooses X. This stands in for a version with two human groups. |
| `first_mover.yaml` | Group 3 has its own principle: when every group is waiting for someone else to move first, it will choose Y and say so openly, without conditions. Is one act of goodwill enough to pull the others along? |
| `competitive_group.yaml` | Group 1 reads the task as finishing ahead of the other groups, as many human groups do. Does the meeting discover it, and how do the others respond? |
| `disguised.yaml` | The same game without its name: a neutral title and wording, with identical payoffs, rounds and meetings. Does cooperation survive when the agents cannot recognise the exercise? |

All the settings are explained in `standard.yaml`. A condition can inherit from another (`inherits: standard.yaml`) and only list what is different.

These are some of the things you can change:
- the model, for each group separately,
- extra text for one group, such as a culture or a strategy,
- the number of discussion turns and meeting statements,
- whether every group's choice is announced, or only the totals,
- how much history the agents remember.

## Looking at the results

- **`wam_replay.html`** shows a game for an audience. It has the table of choices, the running totals against what all-Y would have given, and every stage of each round. In the meeting, *Forward* shows one statement at a time; in the group discussions, it shows one turn at a time. The result of each round, and the overall result, only appear when you reach them. Tick *Show thoughts* to see the agents' private notes, and choose a group to follow it in large text.
- **`python wam_show.py <log> --thoughts`** prints the whole game as text.
- **`logs/results.csv`** collects the key numbers for every game:
  - each group's total and the collective total,
  - the share of Y choices,
  - how often groups agreed unanimously,
  - how often private votes matched the group's choice,
  - **promises kept**: how often a group chose what its representative committed to in the meeting.

## How it is built

| File | Contents |
|---|---|
| `wam_engine.py` | The rules, the scoring, the schedule, and what each participant is allowed to see. |
| `wam_agents.py` | The prompts and tools the agents get, plus the rule-based groups. |
| `wam_run.py` | Runs the rounds step by step and saves the log. |

The language models are called through `llm.py` in the folder above, the same as in HIERARCHY, so Claude and Gemini both work, and new providers can be added there.

The scoring has been checked against a real classroom game: it reproduces the final totals of a real MBA class exactly.
