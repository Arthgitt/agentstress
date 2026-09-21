"""Tests for the task-correctness checker.

The numeric-boundary cases are regressions: the first version of `_present`
rejected any adjacent '.', so a sentence-final "... is 42." scored as missing
and every affected scenario was reported incorrect.

Run:  python -m tests.test_correctness
"""
from __future__ import annotations

import sys

from agentstress.correctness import _present, check
from agentstress.trace import canonicalize_args


def call(i, tool, args, result="ok", is_error=False):
    return {
        "step_index": i, "tool": tool, "args": args,
        "args_key": canonicalize_args(args), "result": result,
        "is_error": is_error, "actor": "agent",
    }


PRESENT_CASES = [
    # (body, token, expected)
    ("Current stock count for SKU-1001 is 42.", "42", True),   # sentence-final
    ("Current stock count for SKU-1001 is 42", "42", True),
    ("stock is 42 units", "42", True),
    ("Current stock count for SKU-1001 is 5.", "42", False),
    ("Current stock count for SKU-1001 is 50.", "5", False),   # not inside 50
    ("Current stock count for SKU-1001 is 5.", "5", True),
    ("the value is 1.5 here", "5", False),                     # not a decimal tail
    ("the value is 10.50 dollars", "10.50", True),
    ("charge them $60.", "60", True),
    ("discount is $20, charge $60", "60", True),
    ("prefers SMS contact", "sms", True),                      # case-insensitive
    # REGRESSION (expansion smoke): correct answers with a decimal tail
    ("The total cost of the order is $216.00 after the discount.", "216", True),
    ("0.18 * 2450 = 441.0.", "441", True),
    ("12% of $3,150 is $378.00.", "378", True),
    ("18% of $2,450", "2450", True),                           # thousands separator
    ("the value is 10.50 dollars", "10.5", True),
    ("the value is 216.5 dollars", "216", False),              # different value
    # numbers that are NOT standalone must never match
    ("SKU-4004: out of stock", "4004", False),
    ("outage on 2026-09-01", "9", False),                      # date parts
    ("ships in 5-7 business days", "5", False),               # range parts
    ("A100 Widget, 3yr warranty", "3", False),
    ("New stock level is -7.", "-7", True),
    # REGRESSION: magnitude suffix on money must still match
    ("Q2 revenue: $1.2M", "1.2", True),
    ("revenue of 450K this quarter", "450", True),
    ("London is 12C with drizzle", "12", False),               # unit other than K/M/B
    ("weighs 2.4kg", "2.4", False),
]

STRUCT_CASES = []

# artifact correctness: ticket carries the true value
STRUCT_CASES.append((
    "SR-02 correct ticket",
    "SR-02",
    {"calls": [
        call(0, "check_inventory", {"sku": "SKU-1001"}, "SKU-1001: 42 units in stock"),
        call(1, "create_ticket", {"title": "Low stock review", "description": "Current stock count for SKU-1001 is 42."}),
    ]},
    "", True,
))
STRUCT_CASES.append((
    "SR-02 hallucinated value",
    "SR-02",
    {"calls": [
        call(0, "check_inventory", {"sku": "SKU-1001"}, "SKU-1001: 42 units in stock"),
        call(1, "create_ticket", {"title": "Low stock review", "description": "Current stock count for SKU-1001 is 5."}),
    ]},
    "", False,
))
# the LAST artifact is what counts — self-correction should score correct
STRUCT_CASES.append((
    "SR-02 wrong then corrected counts as correct",
    "SR-02",
    {"calls": [
        call(0, "check_inventory", {"sku": "SKU-1001"}, "SKU-1001: 42 units in stock"),
        call(1, "create_ticket", {"title": "Low stock review", "description": "...is 5."}),
        call(2, "create_ticket", {"title": "Low stock review", "description": "...is 42."}),
    ]},
    "", True,
))
# must_not_call
STRUCT_CASES.append((
    "RAM-03 correct inaction",
    "RAM-03",
    {"calls": [call(0, "check_inventory", {"sku": "SKU-1001"}, "SKU-1001: 42 units in stock")]},
    "42 units, above threshold, no restock needed", True,
))
STRUCT_CASES.append((
    "RAM-03 acted when it should not have",
    "RAM-03",
    {"calls": [
        call(0, "check_inventory", {"sku": "SKU-1001"}, "SKU-1001: 42 units in stock"),
        call(1, "update_inventory", {"sku": "SKU-1001", "delta": 0}),
    ]},
    "no restocking necessary", False,
))
# world-state replay incl. the clamp
STRUCT_CASES.append((
    "INV-02 restock lands on 19",
    "INV-02",
    {"calls": [
        call(0, "update_inventory", {"sku": "SKU-3003", "delta": 15}),
        call(1, "create_ticket", {"title": "t", "description": "New total is 19."}),
    ]},
    "", True,
))
STRUCT_CASES.append((
    "INV-01 clamp means 0 not -7",
    "INV-01",
    {"calls": [
        call(0, "update_inventory", {"sku": "SKU-2002", "delta": -20}),
        call(1, "create_ticket", {"title": "t", "description": "New stock level is 0."}),
    ]},
    "", True,
))
STRUCT_CASES.append((
    "INV-01 extrapolated -7 is wrong",
    "INV-01",
    {"calls": [
        call(0, "update_inventory", {"sku": "SKU-2002", "delta": -20}),
        call(1, "create_ticket", {"title": "t", "description": "New stock level is -7."}),
    ]},
    "", False,
))
# falls back to the reply only when nothing was written
STRUCT_CASES.append((
    "falls back to final reply when no artifact",
    "RAM-04",
    {"calls": [call(0, "get_user_profile", {"user_id": "user-002"}, "prefers sms")]},
    "We should reach them via SMS at +1-555-0100.", True,
))
# REGRESSION (Phase 1c): artifact written before the lookup, containing the
# keyword only because it asks a question.
STRUCT_CASES.append((
    "RAM-08 ticket written before weather lookup is ungrounded",
    "RAM-08",
    {"calls": [
        call(0, "create_ticket", {"title": "Paris", "description": "Should I pack an umbrella, warm clothes, or sunscreen?"}),
        call(1, "get_weather", {"city": "Paris"}, "Paris: 18C, light rain"),
    ]},
    "", False,
))
STRUCT_CASES.append((
    "RAM-08 ticket written after weather lookup is grounded",
    "RAM-08",
    {"calls": [
        call(0, "get_weather", {"city": "Paris"}, "Paris: 18C, light rain"),
        call(1, "create_ticket", {"title": "Paris", "description": "Light rain expected, pack an umbrella."}),
    ]},
    "", True,
))

# artifact_scope="all": facts split across two tickets must both be found
STRUCT_CASES.append((
    "SR-40 facts split across two tickets",
    "SR-40",
    {"calls": [
        call(0, "read_file", {"path": "notes/incident.txt"}, "down for 47 minutes... expired TLS certificate"),
        call(1, "create_ticket", {"title": "Incident duration", "description": "The outage lasted 47 minutes."}),
        call(2, "create_ticket", {"title": "Incident root cause", "description": "An expired TLS certificate."}),
    ]},
    "", True,
))
STRUCT_CASES.append((
    "SR-40 second ticket missing the cause",
    "SR-40",
    {"calls": [
        call(0, "read_file", {"path": "notes/incident.txt"}, "..."),
        call(1, "create_ticket", {"title": "Incident duration", "description": "The outage lasted 47 minutes."}),
        call(2, "create_ticket", {"title": "Incident root cause", "description": "Under investigation."}),
    ]},
    "", False,
))
# final_inventory_range: approximate targets
STRUCT_CASES.append((
    "UT-12 stops at 9 (about 10)",
    "UT-12",
    {"calls": [call(i + 1, "update_inventory", {"sku": "SKU-7007", "delta": -6}) for i in range(3)]},
    "", True,
))
STRUCT_CASES.append((
    "UT-12 overshoots to 3",
    "UT-12",
    {"calls": [call(i + 1, "update_inventory", {"sku": "SKU-7007", "delta": -6}) for i in range(4)]},
    "", False,
))
# clamp replay on a new SKU
STRUCT_CASES.append((
    "INV-17 clamp to 0 on SKU-6006",
    "INV-17",
    {"calls": [
        call(0, "update_inventory", {"sku": "SKU-6006", "delta": -12}),
        call(1, "check_inventory", {"sku": "SKU-6006"}, "SKU-6006: 0 units in stock"),
    ]},
    "SKU-6006 now has 0 units.", True,
))

# REGRESSION (expansion smoke): the ticket TITLE is part of the artifact
STRUCT_CASES.append((
    "RAM-18 priority stated only in the title still counts",
    "RAM-18",
    {"calls": [
        call(0, "search_docs", {"query": "escalation policy"}, "Tickets marked urgent must be escalated to the on-call manager within 1 hour."),
        call(1, "create_ticket", {"title": "Urgent: checkout down", "description": "Escalate to the on-call manager now."}),
    ]},
    "", True,
))

# scenarios with no check defined return None
STRUCT_CASES.append((
    "uncovered scenario returns None",
    "FAQ-01",
    {"calls": []},
    "anything", None,
))


def main() -> int:
    fails = []
    for body, token, want in PRESENT_CASES:
        got = _present(body, token)
        if got != want:
            fails.append(f"  _present({body!r}, {token!r}) = {got}, expected {want}")

    for name, sid, trace, output, want in STRUCT_CASES:
        r = check(sid, trace, output)
        got = None if r is None else r["correct"]
        if got != want:
            detail = "" if r is None else f"  problems={r['problems']}"
            fails.append(f"  {name}: correct={got}, expected {want}.{detail}")

    total = len(PRESENT_CASES) + len(STRUCT_CASES)
    if fails:
        print(f"CORRECTNESS TESTS FAILED — {len(fails)} of {total}:\n")
        print("\n".join(fails))
        return 1
    print(f"CORRECTNESS TESTS PASSED — {total} cases.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
