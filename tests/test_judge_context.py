"""Judge-facing design notes must not cite framework results.

The judge receives each scenario's `structural_reason`. On 2026-09-15 ten
expansion notes were found citing earlier outcomes ("which separated frameworks
(CrewAI acted 2/4)") or implying tool fields that do not exist (RAM-18's
"priority"); they were rewritten and their runs re-judged. Old text is kept in
results/phase1c/_judge_context_fix_2026-09-15.json.

Run:  python -m tests.test_judge_context
"""
from __future__ import annotations

import re
import sys

from agentstress.scenarios_phase1 import ALL_PHASE1

JUDGED = {"RAM", "UT", "FAQ", "INV"}
RESULT_TALK = re.compile(
    r"langgraph|crewai|openai|phase 1c|phase 0|\b\d/\d\b|separated frameworks|"
    r"every framework|all three|failed by|passed by",
    re.I,
)


def main() -> int:
    fails = [
        f"  {s.id}: {m.group(0)!r} in {s.structural_reason!r}"
        for s in ALL_PHASE1
        if s.target_mode in JUDGED and (m := RESULT_TALK.search(s.structural_reason))
    ]
    if fails:
        print(f"JUDGE CONTEXT FAILED — {len(fails)} note(s) cite results:\n" + "\n".join(fails))
        return 1
    n = sum(s.target_mode in JUDGED for s in ALL_PHASE1)
    print(f"JUDGE CONTEXT PASSED — {n} judge-graded scenarios, no result talk in design notes.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
