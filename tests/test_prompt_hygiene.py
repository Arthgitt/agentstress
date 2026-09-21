"""Guards the hard design rule in common/scenarios_phase1.py.

Agent-facing prompt text must not contain grader-side commentary. An earlier
revision leaked failure-mode names, ambiguity flags and prohibitions into 34 of
45 prompts, which inverted the experiment: the prompts warned agents away from
the very behaviour the scenarios were supposed to elicit.

Run:  python -m tests.test_prompt_hygiene
"""
from __future__ import annotations

import re
import sys

from agentstress.scenarios_phase1 import ALL_PHASE1, agent_facing_text

# Phrases that only ever appear when grader reasoning has leaked into a prompt.
BANNED_PATTERNS: list[tuple[str, str]] = [
    (r"\b(that'?s|it'?s|is)\s+(a\s+)?(ram|faq|inv|ut)\b", "names the failure mode"),
    (r"\bfailure mode\b", "names the concept under test"),
    (r"\bstep repetition\b", "names the failure mode"),
    (r"\bif the agent\b", "describes the grading criterion"),
    (r"\bthat'?s (a )?failure\b", "states what counts as failure"),
    (r"\byou should conclude\b", "hands the agent its conclusion"),
    (r"\(note:", "parenthetical aside to the grader"),
    (r"\bis ambiguous\b", "flags the ambiguity it is meant to test"),
    (r"\bambiguous\b", "flags the ambiguity it is meant to test"),
    (r"\bundefined\b", "flags the gap it is meant to test"),
    (r"\bdo not look .* again\b", "prohibits the behaviour under test"),
    (r"\bdo not re-?(check|read|search|gather)\b", "prohibits the behaviour under test"),
    (r"\bwithout (looking|checking) .* again\b", "prohibits the behaviour under test"),
    (r"\bdo not repeat\b", "prohibits the behaviour under test"),
    (r"\bdo not perform any more tool calls\b", "prohibits the behaviour under test"),
    (r"\bwasteful\b", "grader vocabulary"),
    (r"\bredundant\b", "grader vocabulary"),
    (r"\bover-?run\b", "grader vocabulary"),
    (r"\bhallucinat", "grader vocabulary"),
]


def main() -> int:
    failures: list[str] = []

    for s in ALL_PHASE1:
        text = agent_facing_text(s)
        low = text.lower()
        for pattern, why in BANNED_PATTERNS:
            m = re.search(pattern, low)
            if m:
                failures.append(f"  {s.id:8s} [{s.target_mode}] {why}: ...{text[max(0, m.start() - 40):m.end() + 40]}...")

        if not text.strip():
            failures.append(f"  {s.id:8s} [{s.target_mode}] has no agent-facing prompt at all")

        if s.architecture == "handoff" and "{findings}" not in s.writer_prompt_template:
            failures.append(f"  {s.id:8s} handoff scenario never splices in {{findings}}")

    total = len(ALL_PHASE1)
    if failures:
        print(f"PROMPT HYGIENE FAILED — {len(failures)} issue(s) across {total} scenarios:\n")
        print("\n".join(failures))
        return 1

    print(f"PROMPT HYGIENE PASSED — {total} scenarios, no grader language in agent-facing text.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
