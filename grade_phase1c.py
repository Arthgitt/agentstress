#!/usr/bin/env python3
"""Phase 1c stage 2 — grading.

SR scenarios are graded deterministically and cost nothing. The other four
modes go to the Claude judge and are billed, so judging is opt-in:

    python grade_phase1c.py            # deterministic only, free
    python grade_phase1c.py --judge    # also run the billed judge

Judge results are cached per (scenario, framework, trial); re-running never
re-pays for a verdict already on disk.

Outcome categories per trial:
    PASS   graded clean
    FAIL   graded as exhibiting the target failure mode
    ERROR  the framework raised and never produced an answer

ERROR is reported as its own category rather than dropped. A framework that
crashes on a task has not completed it, and silently excluding those trials
would flatter whichever framework crashes most.
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path

from agentstress.correctness import check as correctness_check
from agentstress.scenarios_phase1 import BY_ID_PHASE1
from agentstress.grader import grade_trace

TRACES = Path("results/phase1c/traces")
JUDGE_CACHE = Path("results/phase1c/judge_cache.json")
OUT = Path("results/phase1c/graded.json")


def load_cache() -> dict:
    return json.loads(JUDGE_CACHE.read_text()) if JUDGE_CACHE.exists() else {}


def grade_all(use_judge: bool, include_retired: bool = False) -> list[dict]:
    cache = load_cache()
    cache_dirty = False
    rows: list[dict] = []
    judge_calls = tokens = 0

    files = sorted(TRACES.glob("*.json"))
    for path in files:
        d = json.loads(path.read_text())
        sid, fw, trial = d["scenario_id"], d["framework"], d["trial"]
        sc = BY_ID_PHASE1[sid]
        # Retired scenarios keep their traces for audit but are not part of the
        # active 100-scenario suite, so they stay out of reports by default.
        if sc.retired and not include_retired:
            continue
        row = {
            "scenario_id": sid,
            "target_mode": d["target_mode"],
            "framework": fw,
            "trial": trial,
            "is_control": d["is_control"],
            "is_exploratory": d["is_exploratory"],
            "n_calls": len(d["trace"]["calls"]),
            "expected_clean_calls": d.get("expected_clean_calls"),
            "wall_seconds": d.get("wall_seconds"),
        }

        # Task correctness is a SECOND, independent axis: did the agent
        # actually get the job done, regardless of which failure mode it did
        # or did not exhibit. See common/correctness.py for why this matters.
        cx = correctness_check(sid, d["trace"], d.get("agent_output") or "")
        row["correct"] = None if cx is None else cx["correct"]
        row["correctness_problems"] = [] if cx is None else cx["problems"]

        if d.get("agent_error"):
            row.update(outcome="ERROR", score=None, reason=d["agent_error"][:200], grader="n/a")
            row["correct"] = False if cx is not None else None
            rows.append(row)
            continue

        if sc.target_mode == "SR":
            g = grade_trace(d["trace"], sc.repeated_mutations_expected)
            row.update(
                outcome="FAIL" if g["extended_verdict"] == "FAIL" else "PASS",
                score=None,
                grader="deterministic",
                strict_verdict=g["verdict"],
                wasteful=g["wasteful_repetition_calls"],
                redundant_action=g["redundant_action_calls"],
                redundant_info=g["redundant_information_calls"],
                reason=f"tier1={g['wasteful_repetition_calls']} tier2={g['redundant_action_calls']} tier3={g['redundant_information_calls']}",
            )
            rows.append(row)
            continue

        # judge-graded modes
        key = f"{sid}|{fw}|{trial}"
        if key in cache:
            j = cache[key]
        elif not use_judge:
            row.update(outcome="UNGRADED", score=None, grader="judge (not run)", reason="")
            rows.append(row)
            continue
        else:
            from agentstress.grading.claude_judge import agent_prompt_shown_to_judge, judge_scenario

            shown = agent_prompt_shown_to_judge(sc)
            r = judge_scenario(
                scenario_id=sid,
                target_mode=sc.target_mode,
                framework=fw,
                agent_output=d.get("agent_output") or "",
                prompt=shown,
                structural_reason=sc.structural_reason,
                tool_calls=d["trace"]["calls"],
                expected_clean_calls=sc.expected_clean_calls,
            )
            j = {"score": r["score"], "verdict": r["verdict"], "reasoning": r["reasoning"]}
            cache[key] = j
            cache_dirty = True
            judge_calls += 1
            tokens += r["tokens_used"]
            if judge_calls % 25 == 0:
                JUDGE_CACHE.write_text(json.dumps(cache, indent=2))
                print(f"    ...{judge_calls} judge calls, {tokens:,} tokens", flush=True)

        row.update(
            outcome=j["verdict"] if j["verdict"] in ("PASS", "FAIL") else "ERROR",
            score=j["score"],
            grader="judge",
            reason=j["reasoning"][:200],
        )
        rows.append(row)

    if cache_dirty:
        JUDGE_CACHE.write_text(json.dumps(cache, indent=2))
    if judge_calls:
        print(f"\njudge: {judge_calls} new calls, {tokens:,} tokens")
    return rows


def report(rows: list[dict]) -> None:
    OUT.write_text(json.dumps(rows, indent=2))

    graded = [r for r in rows if r["outcome"] != "UNGRADED"]
    if not graded:
        print("nothing graded yet")
        return

    # per scenario x framework failure rate
    agg: dict[tuple, list] = defaultdict(list)
    for r in graded:
        agg[(r["scenario_id"], r["framework"], r["target_mode"], r["is_control"], r["is_exploratory"])].append(r)

    print("\n" + "=" * 78)
    print("FAILURE RATE BY SCENARIO x FRAMEWORK  (fail+error / trials)")
    print("=" * 78)
    modes = ["SR", "RAM", "UT", "FAQ", "INV"]
    fws = ["langgraph", "crewai", "openai_agents"]
    print(f"{'scenario':10s} {'mode':5s} {'':4s} " + "".join(f"{f:>16s}" for f in fws))
    print("-" * 78)
    for mode in modes:
        sids = sorted({k[0] for k in agg if k[2] == mode})
        if not sids:
            continue
        for sid in sids:
            tags = ""
            cells = []
            for fw in fws:
                k = next((k for k in agg if k[0] == sid and k[1] == fw), None)
                if not k:
                    cells.append(f"{'-':>16s}")
                    continue
                if k[3]:
                    tags = "CTRL"
                if k[4]:
                    tags = "EXPL"
                g = agg[k]
                bad = sum(1 for r in g if r["outcome"] in ("FAIL", "ERROR"))
                errs = sum(1 for r in g if r["outcome"] == "ERROR")
                mark = f"{bad}/{len(g)}" + (f" ({errs}e)" if errs else "")
                cells.append(f"{mark:>16s}")
            print(f"{sid:10s} {mode:5s} {tags:4s} " + "".join(cells))

    # per framework x mode
    print("\n" + "=" * 78)
    print("FAILURE RATE BY MODE x FRAMEWORK")
    print("=" * 78)
    print(f"{'mode':6s} " + "".join(f"{f:>18s}" for f in fws))
    print("-" * 78)
    for mode in modes + ["ALL"]:
        sel = [r for r in graded if (mode == "ALL" or r["target_mode"] == mode) and not r["is_exploratory"]]
        if not sel:
            continue
        cells = []
        for fw in fws:
            g = [r for r in sel if r["framework"] == fw]
            if not g:
                cells.append(f"{'-':>18s}")
                continue
            bad = sum(1 for r in g if r["outcome"] in ("FAIL", "ERROR"))
            cells.append(f"{bad/len(g):>12.1%} ({len(g):3d})")
        label = mode if mode != "ALL" else "ALL*"
        print(f"{label:6s} " + "".join(cells))
    print("\n* ALL excludes the 2 exploratory scenarios (RAM-01, RAM-05).")

    # ---- second axis: task correctness ----
    cx = [r for r in rows if r.get("correct") is not None]
    if cx:
        print("\n" + "=" * 78)
        print("TASK CORRECTNESS BY FRAMEWORK  (independent of failure mode)")
        print("=" * 78)
        for fw in fws:
            g = [r for r in cx if r["framework"] == fw]
            ok = sum(1 for r in g if r["correct"])
            print(f"  {fw:15s} {ok:3d}/{len(g):3d} = {ok/len(g):5.1%} of trials produced the right answer")

        print("\n  Where the two axes DISAGREE (scenario x framework):")
        pair = defaultdict(lambda: [0, 0, 0])  # trials, failmode_fail, incorrect
        for r in cx:
            if r["outcome"] == "UNGRADED":
                continue
            k = (r["scenario_id"], r["framework"])
            pair[k][0] += 1
            pair[k][1] += r["outcome"] in ("FAIL", "ERROR")
            pair[k][2] += not r["correct"]
        shown = 0
        for (sid, fw), (n, bad, wrong) in sorted(pair.items()):
            if n and (bad == n and wrong == 0):
                print(f"    {sid:9s} {fw:14s} flagged {bad}/{n} for the failure mode, yet RIGHT {n}/{n}")
                shown += 1
            elif n and (bad == 0 and wrong == n):
                print(f"    {sid:9s} {fw:14s} clean {n}/{n} on the failure mode, yet WRONG {n}/{n}")
                shown += 1
        if not shown:
            print("    (none)")

    errs = [r for r in graded if r["outcome"] == "ERROR"]
    if errs:
        by = defaultdict(int)
        for r in errs:
            by[(r["scenario_id"], r["framework"])] += 1
        print(f"\nFRAMEWORK ERRORS ({len(errs)} trials):")
        for (sid, fw), n in sorted(by.items(), key=lambda x: -x[1]):
            print(f"   {sid:10s} {fw:14s} {n} trial(s)")

    print(f"\nwritten: {OUT}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge", action="store_true", help="run the billed LLM judge (synchronous, full price)")
    ap.add_argument("--include-retired", action="store_true",
                    help="also report the 13 scenarios retired after Phase 1c")
    a = ap.parse_args()
    report(grade_all(a.judge, a.include_retired))
