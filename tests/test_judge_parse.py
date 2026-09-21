"""Judge-response parsing, including the salvage path for near-JSON replies.

The malformed cases are the exact tails of the 5 responses (out of 648) that
failed json.loads in the 2026-09-14 expansion batch.

Run:  python -m tests.test_judge_parse
"""
from __future__ import annotations

import sys
from types import SimpleNamespace

from agentstress.grading.claude_judge import verdict_from_content


def _v(text):
    return verdict_from_content([SimpleNamespace(type="text", text=text)])


CASES = [
    # (response text, expected score, expected verdict, salvaged?)
    ('{"score": 1.0, "reasoning": "fine", "verdict": "PASS"}', 1.0, "PASS", False),
    ('Here you go:\n{"score": 0.25, "reasoning": "x", "verdict": "FAIL"}', 0.25, "FAIL", False),
    ('{"score": 0.0, "reasoning": "no gap acknowledged."verdict": "FAIL"}', 0.0, "FAIL", True),
    ('{"score": 0.75, "reasoning": "as the final response does."e, "verdict": "PASS"}', 0.75, "PASS", True),
    ('{"score": 1.0, "reasoning": "would be included)."\', "verdict": "PASS"}', 1.0, "PASS", True),
    ('{"score": 0.75, "reasoning": "no alternative plan is proposed."], "verdict": "PASS"}', 0.75, "PASS", True),
    # Must stay ERROR: no score, or an ambiguous verdict.
    ('{"reasoning": "x" "verdict": "PASS"}', -1.0, "ERROR", False),
    ('{"score": 0.5, "reasoning": "said "verdict": "PASS"} then "verdict": "FAIL"}', -1.0, "ERROR", False),
    ("I cannot grade this.", -1.0, "ERROR", False),
]


def main() -> int:
    fails = 0
    for text, score, verdict, salvaged in CASES:
        got = _v(text)
        ok = (got["score"] == score and got["verdict"] == verdict
              and bool(got.get("parse_salvaged")) == salvaged)
        if not ok:
            fails += 1
            print(f"FAIL  {text[:60]!r}\n      got {got}")
    print(f"{len(CASES) - fails}/{len(CASES)} judge-parse cases pass")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
