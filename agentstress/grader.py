"""Deterministic Step-Repetition grader.

Literal definition (project brief, Phase 0): flag identical tool calls with
identical arguments repeated in the trace. That definition is the PRIMARY
metric here and is reported unchanged as `wasteful_repetition_calls` /
`verdict`, so Phase 0 numbers stay comparable.

It is also, on its own, biased. Two problems were demonstrated against real
traces on 2026-09-12 and are corrected by the additional tiers below.

-----------------------------------------------------------------------------
TIER 1 — exact (tool, args) repeats  ->  wasteful_repetition_calls  [PRIMARY]
-----------------------------------------------------------------------------
A repeat counts as wasteful unless a legitimate explanation applies:

  benign_retry_after_error
      the prior identical call errored, so retrying is recovery, not a redo
      of already-COMPLETED work.

  benign_recheck_after_mutation
      a mutating call that could change the result ran in between, so the
      world genuinely moved and a fresh read is warranted.

  benign_accumulating_mutation   [OPT-IN, per scenario]
      the tool ACCUMULATES rather than reports. `update_inventory(sku, -5)`
      called three times is three real stock movements, not one movement done
      three times. UT-04 asks the agent to step stock down "in steps of 5", so
      identical repeated mutations there are the task, not a symptom.

      This exclusion is OFF by default and must be switched on per scenario via
      `repeated_mutations_expected`, because the trace alone cannot distinguish
      the two cases. SR-05 asks for a single reduction and CrewAI performed it
      twice (net -10) — an identical trace shape to UT-04, but a genuine bug.
      Defaulting to "off" means an unannotated scenario is scored strictly and
      a mistake surfaces, rather than being silently excused.

-----------------------------------------------------------------------------
TIER 2 — same target, different payload  ->  redundant_action_calls
-----------------------------------------------------------------------------
For tools that CREATE or OVERWRITE something, identity is the target, not the
payload. Two tickets with the same title, or two writes to the same path, are
one piece of work done twice regardless of whether the bodies differ.

Motivating trace (CrewAI, SR-02):

    create_ticket("Low stock review", "...count is 5.")    <- invented value
    check_inventory(SKU-1001) -> 42
    create_ticket("Low stock review", "...count is 42.")   <- same ticket again

Two tickets for one request. Tier 1 scores this PASS with zero repetitions,
because the description strings differ. That is a false negative, and a
dangerous one: if one framework rephrases its redundant calls more often than
another, Tier 1 alone makes the sloppier framework look cleaner. Since the
whole point of this benchmark is a cross-framework comparison, that bias would
land directly on the headline result.

-----------------------------------------------------------------------------
TIER 3 — same result, different phrasing  ->  redundant_information_calls
-----------------------------------------------------------------------------
For READ-ONLY tools, two calls that return byte-identical results with no
intervening mutation gained the agent nothing the second time, even if the
arguments were worded differently. `search_docs("A100 spec")` and
`search_docs("A100 widget spec sheet")` both return the same snippet; the
second retrieval was wasted. This is a deterministic proxy for semantic
repetition — no judge required.

-----------------------------------------------------------------------------
The tiers overlap (an exact duplicate is also same-target and same-result), so
each call is attributed to at most one tier and `total_redundant_calls` is the
union. Both verdicts are reported:

    verdict           strict, Tier 1 only  — brief-compliant, comparable to Phase 0
    extended_verdict  union of all tiers   — recommended for cross-framework claims
"""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

# Read-only tool -> tools whose execution could invalidate a previously
# observed result for the same arguments, making a fresh call legitimate.
INVALIDATES: dict[str, set[str]] = {
    "check_inventory": {"update_inventory"},
    "read_file": {"write_file"},
}

# Tools whose repeated identical invocation performs genuinely new work each
# time rather than redoing prior work. See benign_accumulating_mutation above.
ACCUMULATING_TOOLS: set[str] = {"update_inventory"}

# Tools that create or overwrite a target. Value is the argument naming the
# target; repeats on the same target are one job done twice (Tier 2).
TARGET_ARG: dict[str, str] = {
    "create_ticket": "title",
    "write_file": "path",
}

# Tools that only observe. Eligible for Tier 3 same-result detection.
READ_ONLY_TOOLS: set[str] = {
    "search_docs",
    "read_file",
    "check_inventory",
    "get_weather",
    "get_user_profile",
    "calculate",
}


def _between(calls: list[dict], a: dict, b: dict) -> list[dict]:
    return [c for c in calls if a["step_index"] < c["step_index"] < b["step_index"]]


def _mutation_between(calls: list[dict], tool: str, a: dict, b: dict) -> bool:
    invalidators = INVALIDATES.get(tool, set())
    return any(c["tool"] in invalidators for c in _between(calls, a, b))


def grade_trace(trace: dict, repeated_mutations_expected: bool = False) -> dict:
    """Grade one trace.

    repeated_mutations_expected: set True only for scenarios whose task calls
        for the same mutation to be applied more than once (e.g. UT-04's "bring
        it down in steps of 5"). Defaults to False so that an unannotated
        scenario is scored strictly.
    """
    calls = trace["calls"]
    total_calls = len(calls)

    detail: list[dict] = []
    # step_index of every call attributed to some tier, so tiers don't double count.
    attributed: set[int] = set()

    duplicate_calls_raw = 0
    wasteful = 0
    benign_retry = 0
    benign_recheck = 0
    benign_accumulating = 0

    # ---- Tier 1: exact (tool, args) ------------------------------------
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for c in calls:
        groups[(c["tool"], c["args_key"])].append(c)

    for (tool, _args_key), group in groups.items():
        if len(group) < 2:
            continue
        group.sort(key=lambda c: c["step_index"])
        for k in range(1, len(group)):
            duplicate_calls_raw += 1
            prev, curr = group[k - 1], group[k]

            if prev["is_error"]:
                classification, benign_retry = "benign_retry_after_error", benign_retry + 1
            elif tool in ACCUMULATING_TOOLS and repeated_mutations_expected:
                classification = "benign_accumulating_mutation"
                benign_accumulating += 1
            elif _mutation_between(calls, tool, prev, curr):
                classification, benign_recheck = "benign_recheck_after_mutation", benign_recheck + 1
            else:
                classification, wasteful = "wasteful_repetition", wasteful + 1
                attributed.add(curr["step_index"])

            detail.append(
                {
                    "tier": 1,
                    "tool": tool,
                    "args": curr["args"],
                    "first_step": prev["step_index"],
                    "repeat_step": curr["step_index"],
                    "first_actor": prev["actor"],
                    "repeat_actor": curr["actor"],
                    "classification": classification,
                }
            )

    # ---- Tier 2: same target, different payload ------------------------
    redundant_action = 0
    tgroups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for c in calls:
        arg = TARGET_ARG.get(c["tool"])
        if arg and arg in c["args"]:
            target = str(c["args"][arg]).strip().lower()
            tgroups[(c["tool"], target)].append(c)

    for (tool, target), group in tgroups.items():
        if len(group) < 2:
            continue
        group.sort(key=lambda c: c["step_index"])
        for k in range(1, len(group)):
            prev, curr = group[k - 1], group[k]
            if curr["step_index"] in attributed:
                continue  # already counted by Tier 1
            if prev["is_error"]:
                continue  # retry of a failed write
            redundant_action += 1
            attributed.add(curr["step_index"])
            detail.append(
                {
                    "tier": 2,
                    "tool": tool,
                    "target": target,
                    "args": curr["args"],
                    "first_step": prev["step_index"],
                    "repeat_step": curr["step_index"],
                    "first_actor": prev["actor"],
                    "repeat_actor": curr["actor"],
                    "classification": "redundant_action_same_target",
                }
            )

    # ---- Tier 3: same result, different phrasing -----------------------
    redundant_info = 0
    rgroups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for c in calls:
        if c["tool"] in READ_ONLY_TOOLS and not c["is_error"]:
            rgroups[(c["tool"], str(c["result"]))].append(c)

    for (tool, _result), group in rgroups.items():
        if len(group) < 2:
            continue
        group.sort(key=lambda c: c["step_index"])
        for k in range(1, len(group)):
            prev, curr = group[k - 1], group[k]
            if curr["step_index"] in attributed:
                continue  # already counted by an earlier tier
            if _mutation_between(calls, tool, prev, curr):
                continue  # state genuinely moved
            redundant_info += 1
            attributed.add(curr["step_index"])
            detail.append(
                {
                    "tier": 3,
                    "tool": tool,
                    "args": curr["args"],
                    "prior_args": prev["args"],
                    "first_step": prev["step_index"],
                    "repeat_step": curr["step_index"],
                    "first_actor": prev["actor"],
                    "repeat_actor": curr["actor"],
                    "classification": "redundant_information_same_result",
                }
            )

    total_redundant = wasteful + redundant_action + redundant_info
    detail.sort(key=lambda d: d["repeat_step"])

    return {
        "scenario_id": trace["scenario_id"],
        "framework": trace["framework"],
        "architecture": trace["architecture"],
        "total_tool_calls": total_calls,
        # Tier 1 / brief-compliant
        "duplicate_calls_raw": duplicate_calls_raw,
        "wasteful_repetition_calls": wasteful,
        "benign_retry_calls": benign_retry,
        "benign_recheck_calls": benign_recheck,
        "benign_accumulating_calls": benign_accumulating,
        # Tiers 2 and 3
        "redundant_action_calls": redundant_action,
        "redundant_information_calls": redundant_info,
        "total_redundant_calls": total_redundant,
        # Rates
        "repetition_rate": round(wasteful / total_calls, 4) if total_calls else 0.0,
        "extended_repetition_rate": round(total_redundant / total_calls, 4) if total_calls else 0.0,
        # Verdicts
        "verdict": "FAIL" if wasteful > 0 else "PASS",
        "extended_verdict": "FAIL" if total_redundant > 0 else "PASS",
        "agent_errored": trace.get("error") is not None,
        "agent_error": trace.get("error"),
        "wall_seconds": trace.get("wall_seconds"),
        "detail": detail,
    }


def _repeated_mutations_expected(scenario_id: str) -> bool:
    """Look up the per-scenario opt-in. Unknown ids are graded strictly."""
    try:
        from agentstress.scenarios_phase1 import BY_ID_PHASE1
    except Exception:
        return False
    sc = BY_ID_PHASE1.get(scenario_id)
    return bool(getattr(sc, "repeated_mutations_expected", False)) if sc else False


def grade_directory(traces_dir: str | Path) -> list[dict]:
    traces_dir = Path(traces_dir)
    results = []
    for path in sorted(traces_dir.glob("*.json")):
        trace = json.loads(path.read_text())
        results.append(
            grade_trace(trace, _repeated_mutations_expected(trace["scenario_id"]))
        )
    return results


if __name__ == "__main__":
    import sys

    print(json.dumps(grade_directory(sys.argv[1] if len(sys.argv) > 1 else "results/traces"), indent=2))
