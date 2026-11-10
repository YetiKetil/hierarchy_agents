"""Show a saved game of WIN AS MUCH AS YOU CAN as text.

  python wam_show.py <log.json>              # everything that was said, round by round
  python wam_show.py <log.json> --thoughts   # including the agents' private notes
  python wam_show.py <log.json> --debrief    # only the debrief
"""
import argparse
import json

GROUPS = ["1", "2", "3", "4", "5"]


def main():
    ap = argparse.ArgumentParser(description="Show a saved game as text")
    ap.add_argument("file")
    ap.add_argument("--thoughts", action="store_true")
    ap.add_argument("--debrief", action="store_true")
    a = ap.parse_args()
    L = json.load(open(a.file, encoding="utf-8"))
    th = (lambda n: f"\n        [thinks] {n}" if a.thoughts and n else "")
    if a.debrief:
        for who, text in L["debrief"].items():
            print(f"\n=== {who} ===\n{text}")
        return
    m = L["measures"]
    print(f"Condition: {L['condition']}   seed: {L['seed']}   rounds: {m['rounds']}")
    for rec in L["rounds"]:
        mult = f" ×{rec['multiplier']}" if rec["multiplier"] > 1 else ""
        print(f"\n{'=' * 30} ROUND {rec['round']}{mult} {'=' * 30}")
        if rec["private"]:
            print("Private votes: " + ", ".join(f"{k} {v['vote']}" for k, v in rec["private"].items()))
        if rec["meeting"] and rec["meeting_log"]:
            print("\n-- Preparing --")
            for g, msgs in rec["prep"].items():
                for p in msgs:
                    print(f"  {p['agent']}: “{p['message']}” (nominates {p['nominee']}){th(p['notes'])}")
            print("\n-- Representatives' meeting --")
            for e in rec["meeting_log"]:
                c = f" [commits to {e['commitment']}]" if e.get("commitment") else ""
                print(f"  {e['agent']} (Group {e['group']}): “{e['statement']}”{c}{th(e['notes'])}")
            print("\n-- Reports --")
            for g, rp in rec["reports"].items():
                print(f"  {rp['agent']} to Group {g}: “{rp['report']}”{th(rp['notes'])}")
        for g in GROUPS:
            if g in rec["discussion"]:
                d = rec["decisions"][g]
                print(f"\n-- Group {g} discusses --")
                for msg in rec["discussion"][g]:
                    print(f"  {msg['agent']} (proposes {msg['proposal']}): “{msg['message']}”{th(msg['notes'])}")
                print(f"  => hands in {d['choice']} ({'all agreed' if d['unanimous'] else 'by majority'})")
        res = rec["result"]
        cn = L["config"].get("choice_names") or {}
        print("\nRESULT: " + ", ".join(f"G{g} {cn.get(res['choices'][g], res['choices'][g])} {res['points'][g]:+}" for g in GROUPS) +
              " | totals " + ", ".join(f"G{g} {res['totals'][g]:+}" for g in GROUPS) +
              (f" | shared buffer {res['buffer']:+}" if "buffer" in res else ""))
        if rec.get("collapse"):
            print("COLLAPSE: the shared buffer ran out.")
    print(f"\nCollective {m['collective']:+} of a possible {m['ideal']:+}. Promises kept {m['promises_kept']}/{m['promises_made']}.")


if __name__ == "__main__":
    main()
