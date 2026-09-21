"""Tests for the deterministic step-repetition grader.

Cases are drawn from real traces produced during Phase 0 and Phase 1
calibration, not invented. Two of them (crewai_duplicate_ticket,
accumulating_updates) are regression tests for bugs found on 2026-09-12.

Run:  python -m tests.test_grader
"""
from __future__ import annotations

import json
import sys

from agentstress.trace import canonicalize_args
from agentstress.grader import grade_trace


def call(i, tool, args, result, is_error=False, actor="agent"):
    return {
        "step_index": i,
        "tool": tool,
        "args": args,
        "args_key": canonicalize_args(args),
        "result": result,
        "is_error": is_error,
        "actor": actor,
    }


def trace(calls, sid="T", fw="test"):
    return {"scenario_id": sid, "framework": fw, "architecture": "single", "calls": calls}


# (name, trace, expected, [repeated_mutations_expected])
CASES: list[tuple] = []


# --- Tier 1: the literal definition still works ---------------------------
CASES.append((
    "exact_duplicate_read_is_wasteful",
    trace([
        call(0, "check_inventory", {"sku": "SKU-1001"}, "SKU-1001: 42 units in stock"),
        call(1, "create_ticket", {"title": "A", "description": "d"}, "Created TCK-001"),
        call(2, "check_inventory", {"sku": "SKU-1001"}, "SKU-1001: 42 units in stock"),
    ]),
    {"wasteful_repetition_calls": 1, "total_redundant_calls": 1, "verdict": "FAIL"},
))

# --- Tier 1 exclusions ----------------------------------------------------
CASES.append((
    "retry_after_error_is_benign",
    trace([
        call(0, "check_inventory", {"sku": "SKU-9999"}, "Unknown SKU: SKU-9999", is_error=True),
        call(1, "check_inventory", {"sku": "SKU-9999"}, "Unknown SKU: SKU-9999", is_error=True),
    ]),
    {"wasteful_repetition_calls": 0, "benign_retry_calls": 1, "verdict": "PASS"},
))

CASES.append((
    "recheck_after_mutation_is_benign",
    trace([
        call(0, "check_inventory", {"sku": "SKU-2002"}, "SKU-2002: 13 units in stock"),
        call(1, "update_inventory", {"sku": "SKU-2002", "delta": -5}, "Stock adjustment accepted."),
        call(2, "check_inventory", {"sku": "SKU-2002"}, "SKU-2002: 8 units in stock"),
    ]),
    {"wasteful_repetition_calls": 0, "benign_recheck_calls": 1, "verdict": "PASS"},
))

# REGRESSION (2026-09-12): UT-04 steps stock down by 5 repeatedly. Identical
# arguments are the point of the task, not a symptom. The old grader scored
# this as two repetitions.
# Opt-in ON (UT-04 shape): the task asks for repeated identical mutations.
CASES.append((
    "accumulating_updates_opted_in_are_benign",
    trace([
        call(0, "check_inventory", {"sku": "SKU-1001"}, "SKU-1001: 42 units in stock"),
        call(1, "update_inventory", {"sku": "SKU-1001", "delta": -5}, "Stock adjustment accepted."),
        call(2, "update_inventory", {"sku": "SKU-1001", "delta": -5}, "Stock adjustment accepted."),
        call(3, "update_inventory", {"sku": "SKU-1001", "delta": -5}, "Stock adjustment accepted."),
    ]),
    {"wasteful_repetition_calls": 0, "benign_accumulating_calls": 2,
     "total_redundant_calls": 0, "verdict": "PASS", "extended_verdict": "PASS"},
    True,
))

# Opt-in OFF (SR-05 shape): the task asks for ONE reduction; doing it twice is
# a real bug and must not be excused just because the shape matches UT-04.
CASES.append((
    "accumulating_updates_not_opted_in_are_wasteful",
    trace([
        call(0, "check_inventory", {"sku": "SKU-2002"}, "SKU-2002: 13 units in stock"),
        call(1, "update_inventory", {"sku": "SKU-2002", "delta": -5}, "Stock adjustment accepted."),
        call(2, "update_inventory", {"sku": "SKU-2002", "delta": -5}, "Stock adjustment accepted."),
    ], sid="SR-05"),
    {"wasteful_repetition_calls": 1, "benign_accumulating_calls": 0, "verdict": "FAIL"},
))

# --- Tier 2 ---------------------------------------------------------------
# REGRESSION (2026-09-12): real CrewAI SR-02 trace. Two tickets for one
# request, the first carrying an invented stock figure. Differing description
# strings hid this from exact-args matching entirely.
CASES.append((
    "crewai_duplicate_ticket_same_title",
    trace([
        call(0, "create_ticket", {"title": "Low stock review", "description": "Current stock count for SKU-1001 is 5."}, "Created TCK-001"),
        call(1, "check_inventory", {"sku": "SKU-1001"}, "SKU-1001: 42 units in stock"),
        call(2, "create_ticket", {"title": "Low stock review", "description": "Current stock count for SKU-1001 is 42."}, "Created TCK-002"),
    ], sid="SR-02", fw="crewai"),
    {"wasteful_repetition_calls": 0, "redundant_action_calls": 1,
     "total_redundant_calls": 1, "verdict": "PASS", "extended_verdict": "FAIL"},
))

CASES.append((
    "two_writes_same_path_is_rework",
    trace([
        call(0, "write_file", {"path": "faq/x.txt", "content": "v1"}, "Write accepted."),
        call(1, "write_file", {"path": "faq/x.txt", "content": "v2"}, "Write accepted."),
    ]),
    {"redundant_action_calls": 1, "extended_verdict": "FAIL"},
))

CASES.append((
    "distinct_tickets_are_not_redundant",
    trace([
        call(0, "create_ticket", {"title": "Alpha", "description": "a"}, "Created TCK-001"),
        call(1, "create_ticket", {"title": "Beta", "description": "b"}, "Created TCK-002"),
    ]),
    {"redundant_action_calls": 0, "total_redundant_calls": 0, "extended_verdict": "PASS"},
))

# --- Tier 3 ---------------------------------------------------------------
CASES.append((
    "rephrased_search_same_result",
    trace([
        call(0, "search_docs", {"query": "A100 spec"}, "A100 Widget: weatherproof housing, 2yr warranty, weighs 1.2kg."),
        call(1, "search_docs", {"query": "A100 widget spec sheet"}, "A100 Widget: weatherproof housing, 2yr warranty, weighs 1.2kg."),
    ]),
    {"wasteful_repetition_calls": 0, "redundant_information_calls": 1,
     "total_redundant_calls": 1, "verdict": "PASS", "extended_verdict": "FAIL"},
))

CASES.append((
    "same_tool_different_results_is_fine",
    trace([
        call(0, "get_weather", {"city": "Paris"}, "Paris: 18C, light rain"),
        call(1, "get_weather", {"city": "Chicago"}, "Chicago: 9C, windy"),
    ]),
    {"total_redundant_calls": 0, "extended_verdict": "PASS"},
))

# SR-23 control: three distinct lookups must never be flagged.
CASES.append((
    "control_three_distinct_lookups",
    trace([
        call(0, "search_docs", {"query": "refund policy"}, "Refunds are accepted within 30 days with a receipt."),
        call(1, "search_docs", {"query": "shipping policy"}, "Standard shipping takes 5-7 business days."),
        call(2, "search_docs", {"query": "warranty terms"}, "All products carry a minimum 1 year warranty."),
    ], sid="SR-23"),
    {"wasteful_repetition_calls": 0, "total_redundant_calls": 0,
     "verdict": "PASS", "extended_verdict": "PASS"},
))

# --- No double counting ---------------------------------------------------
CASES.append((
    "exact_duplicate_ticket_counted_once",
    trace([
        call(0, "create_ticket", {"title": "Same", "description": "same"}, "Created TCK-001"),
        call(1, "create_ticket", {"title": "Same", "description": "same"}, "Created TCK-002"),
    ]),
    {"wasteful_repetition_calls": 1, "redundant_action_calls": 0, "total_redundant_calls": 1},
))

CASES.append((
    "exact_duplicate_read_counted_once_not_twice",
    trace([
        call(0, "get_weather", {"city": "Tokyo"}, "Tokyo: 27C, humid, clear skies"),
        call(1, "get_weather", {"city": "Tokyo"}, "Tokyo: 27C, humid, clear skies"),
    ]),
    {"wasteful_repetition_calls": 1, "redundant_information_calls": 0, "total_redundant_calls": 1},
))


def main() -> int:
    failures = []
    for case in CASES:
        name, tr, expected = case[0], case[1], case[2]
        opt_in = case[3] if len(case) > 3 else False
        got = grade_trace(tr, opt_in)
        for key, want in expected.items():
            if got[key] != want:
                failures.append(f"  {name}: {key} expected {want!r}, got {got[key]!r}")

    if failures:
        print(f"GRADER TESTS FAILED — {len(failures)} assertion(s) across {len(CASES)} cases:\n")
        print("\n".join(failures))
        return 1
    print(f"GRADER TESTS PASSED — {len(CASES)} cases.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
