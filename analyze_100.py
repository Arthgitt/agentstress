"""Scenario-level statistics for the 100-scenario suite.

Reads results/phase1c/graded.json (written by grade_phase1c.py) and reports:
  - pairwise framework comparisons, scenario as the unit (sign test on each
    scenario's 0-4 failure count), overall and per mode, with Bonferroni
  - scenario-clustered bootstrap 95% CIs for failure-rate differences
  - the same comparisons on task correctness
  - replication: the 29 Phase 1c scenarios vs the 71 new ones, separately
  - suite quality: non-discriminating scenarios, controls, trial agreement

Free (no API). Run:  python analyze_100.py > results/phase1c/stats_100.txt
"""
from __future__ import annotations

import json
import random
from collections import defaultdict
from itertools import combinations
from math import comb

from agentstress.scenarios_expansion import FAQ_NEW, INV_NEW, RAM_NEW, SR_NEW, UT_NEW

FWS = ["langgraph", "crewai", "openai_agents"]
SHORT = {"langgraph": "LG", "crewai": "CrewAI", "openai_agents": "OAI"}
MODES = ["SR", "RAM", "UT", "FAQ", "INV"]
NEW_IDS = {s.id for s in SR_NEW + RAM_NEW + UT_NEW + FAQ_NEW + INV_NEW}
PAIRS = list(combinations(FWS, 2))
BOOT = 10_000


def sign_p(better: int, worse: int) -> float:
    n = better + worse
    if n == 0:
        return 1.0
    k = min(better, worse)
    return min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2**n)


def load():
    rows = json.load(open("results/phase1c/graded.json"))
    fail = defaultdict(lambda: defaultdict(int))     # sid -> fw -> fails (FAIL+ERROR)
    right = defaultdict(lambda: defaultdict(int))    # sid -> fw -> correct trials
    has_check, meta, verdicts = set(), {}, defaultdict(list)
    for r in rows:
        sid, fw = r["scenario_id"], r["framework"]
        meta[sid] = r
        bad = r["outcome"] in ("FAIL", "ERROR")
        fail[sid][fw] += bad
        verdicts[(sid, fw)].append(bad)
        if r["correct"] is not None:
            has_check.add(sid)
            right[sid][fw] += bool(r["correct"])
    return rows, fail, right, has_check, meta, verdicts


def compare(ids, table, a, b, higher_is_better=False):
    better = worse = tie = 0
    for sid in ids:
        x, y = table[sid][a], table[sid][b]
        if x == y:
            tie += 1
        elif (x > y) == higher_is_better:
            better += 1   # a better than b
        else:
            worse += 1
    return better, worse, tie, sign_p(better, worse)


def boot_ci(ids, table, a, b, rng):
    ids = list(ids)
    diffs = []
    for _ in range(BOOT):
        s = [rng.choice(ids) for _ in ids]
        diffs.append(sum(table[i][a] - table[i][b] for i in s) / (4 * len(s)))
    diffs.sort()
    point = sum(table[i][a] - table[i][b] for i in ids) / (4 * len(ids))
    return point, diffs[int(0.025 * BOOT)], diffs[int(0.975 * BOOT)]


def rate(ids, table, fw):
    return 100 * sum(table[i][fw] for i in ids) / (4 * len(ids)) if ids else float("nan")


def pair_block(title, ids, table, rng, n_tests, higher_is_better=False):
    print(f"\n{title}  (n = {len(ids)} scenarios)")
    print(f"  {'pair':<16}{'A better/worse/tie':>20}{'p':>8}{'p_bonf':>8}   rate diff A-B, 95% CI")
    for a, b in PAIRS:
        bt, wr, ti, p = compare(ids, table, a, b, higher_is_better)
        pt, lo, hi = boot_ci(ids, table, a, b, rng)
        name = f"{SHORT[a]} vs {SHORT[b]}"
        print(f"  {name:<16}{f'{bt} / {wr} / {ti}':>20}{p:>8.3f}{min(1, p * n_tests):>8.3f}"
              f"   {100 * pt:+.1f} pts [{100 * lo:+.1f}, {100 * hi:+.1f}]")


def main():
    rng = random.Random(20260914)
    rows, fail, right, has_check, meta, verdicts = load()
    core = sorted(s for s in fail if not meta[s]["is_exploratory"])
    by_mode = {m: [s for s in core if meta[s]["target_mode"] == m] for m in MODES}

    print("=" * 78)
    print("100-SCENARIO SUITE — SCENARIO-LEVEL STATISTICS")
    print("=" * 78)
    print(f"runs {len(rows)} | core scenarios {len(core)} (exploratory RAM-01, RAM-05 excluded)")
    print("unit = scenario; each scenario x framework cell is its 0-4 failure count")
    print("sign test two-sided; Bonferroni x3 for the overall comparison, x15 per mode")
    print(f"bootstrap: {BOOT} resamples of scenarios (clustered), seed 20260914")

    print("\nFAILURE RATE (fail or crash / trials)")
    print(f"  {'':<10}" + "".join(f"{SHORT[f]:>10}" for f in FWS))
    for m in MODES + ["ALL"]:
        ids = core if m == "ALL" else by_mode[m]
        print(f"  {m:<10}" + "".join(f"{rate(ids, fail, f):>9.1f}%" for f in FWS))

    pair_block("OVERALL — failure-mode instances (lower is better)", core, fail, rng, 3)
    for m in MODES:
        pair_block(f"{m}", by_mode[m], fail, rng, 15)

    checked = [s for s in core if s in has_check]
    print("\n" + "=" * 78)
    print("TASK CORRECTNESS (higher is better)")
    print(f"  {'':<10}" + "".join(f"{SHORT[f]:>10}" for f in FWS))
    print(f"  {'correct':<10}" + "".join(f"{rate(checked, right, f):>9.1f}%" for f in FWS))
    pair_block("Correctness", checked, right, rng, 3, higher_is_better=True)

    print("\n" + "=" * 78)
    print("REPLICATION — kept Phase 1c scenarios vs new expansion scenarios, separately")
    old = [s for s in core if s not in NEW_IDS]
    new = [s for s in core if s in NEW_IDS]
    for label, ids in (("kept (Phase 1c)", old), ("new (expansion)", new)):
        print(f"\n  {label}: " + "  ".join(f"{SHORT[f]} {rate(ids, fail, f):.1f}%" for f in FWS))
        for a, b in PAIRS:
            bt, wr, ti, p = compare(ids, fail, a, b)
            print(f"    {SHORT[a]} vs {SHORT[b]:<8} {bt:>2} / {wr:>2} / {ti:>2}   p = {p:.3f}")
        for m in MODES:
            mi = [s for s in ids if meta[s]["target_mode"] == m]
            print(f"    {m:<4} n={len(mi):>2}  " + "  ".join(f"{SHORT[f]} {rate(mi, fail, f):5.1f}%" for f in FWS))

    print("\n" + "=" * 78)
    print("SUITE QUALITY")
    cells = [v for v in verdicts.values()]
    unanimous = sum(1 for v in cells if len(set(v)) == 1)
    print(f"  trial agreement: {unanimous}/{len(cells)} scenario x framework cells unanimous "
          f"({100 * unanimous / len(cells):.0f}%)")
    nondisc = [s for s in core if len({fail[s][f] for f in FWS}) == 1]
    ctrl = [s for s in core if meta[s]["is_control"]]
    print(f"  non-discriminating (identical count on all 3): {len(nondisc)}/{len(core)}")
    for kind, test in (("always fail", lambda s: fail[s][FWS[0]] == 4),
                       ("always pass", lambda s: fail[s][FWS[0]] == 0),
                       ("mixed", lambda s: 0 < fail[s][FWS[0]] < 4)):
        ids = [s for s in nondisc if test(s)]
        tag = lambda s: s + ("(ctrl)" if s in ctrl else "") + ("*" if s in NEW_IDS else "")
        print(f"    {kind:<12} {len(ids):>2}: " + ", ".join(tag(s) for s in ids))
    print("    (* = new expansion scenario)")
    print("  controls (failures /4 per framework):")
    for s in ctrl:
        print(f"    {s:<8} " + "  ".join(f"{SHORT[f]} {fail[s][f]}" for f in FWS))
    cache = json.load(open("results/phase1c/judge_cache.json"))
    salv = sorted(k for k, v in cache.items() if v.get("parse_salvaged"))
    print(f"  judge verdicts recovered by tolerant parsing: {len(salv)} ({', '.join(salv)})")


if __name__ == "__main__":
    main()
