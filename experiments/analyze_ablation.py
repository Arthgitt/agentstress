"""Prompt ablation results: does CrewAI's prompt reproduce CrewAI's failures?

Series compared (same scenarios, model, temperature, trials):
  baselines   langgraph / crewai / openai_agents      (results/phase1c/traces)
  conditions  lg_crewprompt / oai_crewprompt          CrewAI's exact prompt
              crew_neutral                            CrewAI loop, neutral wording

SR is graded deterministically here (free). UT and FAQ need judge verdicts in
results/ablation/judge_cache.json; they are reported once those exist.

Run:  python -m experiments.analyze_ablation
"""
from __future__ import annotations

import json
from collections import defaultdict
from math import comb
from pathlib import Path

from agentstress.scenarios_phase1 import BY_ID_PHASE1
from agentstress.grader import grade_trace

BASE = Path("results/phase1c/traces")
ABL = Path("results/ablation/traces")
ABL_CACHE = Path("results/ablation/judge_cache.json")
BASE_CACHE = Path("results/phase1c/judge_cache.json")

PAIRED = {"lg_crewprompt": "langgraph", "oai_crewprompt": "openai_agents", "crew_neutral": "crewai"}
SERIES = ["langgraph", "openai_agents", "crewai", "lg_crewprompt", "oai_crewprompt", "crew_neutral"]
LABEL = {
    "langgraph": "LangGraph (base)", "openai_agents": "OpenAI Agents (base)", "crewai": "CrewAI (base)",
    "lg_crewprompt": "LangGraph + CrewAI prompt", "oai_crewprompt": "OpenAI Agents + CrewAI prompt",
    "crew_neutral": "CrewAI + neutral wording",
}


def sign_p(better: int, worse: int) -> float:
    n = better + worse
    if n == 0:
        return 1.0
    k = min(better, worse)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2**n)


# --set phase1d: all six setups live in one directory, on gpt-5.4-mini, 2 trials.
SOURCES = [(BASE, BASE_CACHE), (ABL, ABL_CACHE)]
TRIALS = 4


def use_phase1d() -> None:
    global SOURCES, TRIALS, ABL_CACHE
    ABL_CACHE = Path("results/phase1d/judge_cache.json")
    SOURCES = [(Path("results/phase1d/traces"), ABL_CACHE)]
    TRIALS = 2


def load():
    """-> fails[mode][scenario][series] = 0-TRIALS, calls[series] = [n, ...]"""
    fails = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    calls = defaultdict(list)
    graded = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))  # counts of graded trials
    jcache = {}
    for p, cache_path in SOURCES:
        cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
        for f in sorted(p.glob("*.json")):
            d = json.loads(f.read_text())
            sid, fw, mode = d["scenario_id"], d["framework"], d["target_mode"]
            if fw not in SERIES or sid not in {s.id for s in ABL_SCENARIOS}:
                continue
            calls[fw].append(len(d["trace"]["calls"]))
            if mode == "SR":
                sc = BY_ID_PHASE1[sid]
                g = grade_trace(d["trace"], sc.repeated_mutations_expected)
                bad = bool(d.get("agent_error")) or g["extended_verdict"] == "FAIL"
            else:
                v = cache.get(f"{sid}|{fw}|{d['trial']}")
                if v is None:
                    continue
                bad = bool(d.get("agent_error")) or v["verdict"] == "FAIL"
            fails[mode][sid][fw] += bad
            graded[mode][sid][fw] += 1
            jcache[(sid, fw, d["trial"])] = True
    return fails, calls, graded


def rate(fails, ids, fw, graded, mode):
    n = sum(graded[mode][s][fw] for s in ids)
    return 100 * sum(fails[mode][s][fw] for s in ids) / n if n else float("nan")


ABL_SCENARIOS = [s for s in BY_ID_PHASE1.values()
                 if s.target_mode in {"SR", "UT", "FAQ"} and not s.retired and not s.is_exploratory]


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("--set", choices=["ablation", "phase1d"], default="ablation")
    if ap.parse_args().set == "phase1d":
        use_phase1d()
    fails, calls, graded = load()
    print("=" * 78)
    print("PROMPT ABLATION — does CrewAI's prompt reproduce CrewAI's failures?")
    print("=" * 78)
    print("tool calls per run (mean / max):")
    for s in SERIES:
        if calls[s]:
            print(f"  {LABEL[s]:32s} {sum(calls[s])/len(calls[s]):5.2f} / {max(calls[s])}")

    for mode in ("SR", "UT", "FAQ"):
        ids = sorted(fails[mode])
        complete = [s for s in ids if all(graded[mode][s][x] == TRIALS for x in SERIES)]
        if not complete:
            print(f"\n{mode}: not graded yet ({len(ids)} scenarios waiting on judge verdicts)")
            continue
        print(f"\n{mode} — {len(complete)} scenarios x {TRIALS} trials")
        for s in SERIES:
            print(f"  {LABEL[s]:32s} {rate(fails, complete, s, graded, mode):5.1f}%")
        print("  paired sign tests (scenario as unit):")
        for cond, base in PAIRED.items():
            others = [base] if base == "crewai" else [base, "crewai"]
            for other in others:
                w = sum(fails[mode][s][cond] > fails[mode][s][other] for s in complete)
                b = sum(fails[mode][s][cond] < fails[mode][s][other] for s in complete)
                tag = "own baseline" if other == base else "CrewAI baseline"
                print(f"    {LABEL[cond]:32s} vs {tag:16s} worse {w:2d} / better {b:2d} / "
                      f"tie {len(complete)-w-b:2d}   p = {sign_p(b, w):.3f}")

    pooled = [(m, s) for m in ("SR", "UT", "FAQ") for s in fails[m]
              if all(graded[m][s][x] == TRIALS for x in SERIES)]
    if pooled:
        print(f"\nALL THREE MODES POOLED — {len(pooled)} scenarios x {TRIALS} trials")
        for s in SERIES:
            n = sum(graded[m][x][s] for m, x in pooled)
            print(f"  {LABEL[s]:32s} {100 * sum(fails[m][x][s] for m, x in pooled) / n:5.1f}%")
        print("  paired sign tests (Bonferroni x6):")
        for cond, other in (("lg_crewprompt", "langgraph"), ("oai_crewprompt", "openai_agents"),
                            ("crew_neutral", "crewai"), ("lg_crewprompt", "crewai"),
                            ("oai_crewprompt", "crewai"), ("crew_neutral", "langgraph"),
                            ("crewai", "langgraph"), ("crewai", "openai_agents")):
            w = sum(fails[m][s][cond] > fails[m][s][other] for m, s in pooled)
            b = sum(fails[m][s][cond] < fails[m][s][other] for m, s in pooled)
            p = sign_p(b, w)
            print(f"    {LABEL[cond]:32s} vs {LABEL[other]:22s} worse {w:2d} / better {b:2d} / "
                  f"tie {len(pooled)-w-b:2d}   p = {p:.2g}   corrected {min(1, 6 * p):.2g}")

    missing = sum(1 for s in ABL_SCENARIOS if s.target_mode in ("UT", "FAQ")) * (3 if TRIALS == 4 else 6) * TRIALS
    if not ABL_CACHE.exists():
        print(f"\nUT/FAQ need {missing} judge calls (~${missing * 0.00565:.2f} at batch price).")


if __name__ == "__main__":
    main()
