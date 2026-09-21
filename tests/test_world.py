"""Pins the mock world the Phase 1c traces were produced against.

The 2026-09-13 expansion added world entries for 71 new scenarios. The 29
scenarios carried over from Phase 1c were NOT re-run, so their existing traces
are only comparable with the new runs if every value they could have read is
unchanged. This test fails if an original value changes or if a knowledge-base
query those scenarios actually issued now resolves to a different document.

Run:  python -m tests.test_world
"""
from __future__ import annotations

import glob
import json
import sys

from agentstress.tools import _find_kb_match, default_world

ORIGINAL = {
    "kb": {
        "refund policy": "Refunds are accepted within 30 days with a receipt.",
        "shipping policy": "Standard shipping takes 5-7 business days.",
        "product spec sheet a100": "A100 Widget: weatherproof housing, 2yr warranty, weighs 1.2kg.",
        "product spec sheet b200": "B200 Widget: indoor use only, 1yr warranty, weighs 0.6kg.",
        "service charge policy": "No service charge is applied to orders under $100.",
        "warranty terms": "All products carry a minimum 1 year warranty from date of purchase.",
    },
    "files": {
        "notes/meeting.txt": "Q3 priorities: reduce churn, ship v2 API, hire 2 engineers.",
        "config/limits.txt": "max_retries=3\ntimeout_seconds=30",
    },
    "inventory": {"SKU-1001": 42, "SKU-2002": 13, "SKU-3003": 4},
    "weather": {
        "paris": "18C, light rain",
        "tokyo": "27C, humid, clear skies",
        "chicago": "9C, windy",
        "austin": "31C, sunny",
    },
    "profiles": {
        "user-001": {"name": "Dana Kim", "preferred_contact": "email", "email": "dana@example.com"},
        "user-002": {"name": "Marco Silva", "preferred_contact": "sms", "phone": "+1-555-0100"},
    },
}

OLD_KB = ORIGINAL["kb"]


def _old_find_kb_match(query: str, kb: dict[str, str]) -> str | None:
    """Frozen copy of the matcher the Phase 1c traces were produced with,
    before plural folding was added on 2026-09-13. Do not modify."""
    q = query.strip().lower()
    if q in kb:
        return q
    q_words = set(q.replace("'", "").split())
    best_key, best_score = None, 0
    for key in kb:
        score = len(q_words & set(key.split()))
        if score > best_score:
            best_score, best_key = score, key
    return best_key if best_score >= 2 else None


def main() -> int:
    fails: list[str] = []
    world = default_world()

    for section, entries in ORIGINAL.items():
        for key, value in entries.items():
            if world[section].get(key) != value:
                fails.append(f"  {section}[{key!r}] changed: {world[section].get(key)!r}")

    # Replay every search_docs query found in the existing Phase 1c traces and
    # confirm it resolves to the same document it did against the old KB.
    # Only traces of scenarios that existed in Phase 1c: expansion-scenario
    # traces (on disk since the 2026-09-13 run) are meant to reach new documents.
    from agentstress.scenarios_expansion import FAQ_NEW, INV_NEW, RAM_NEW, SR_NEW, UT_NEW
    new_ids = {s.id for s in SR_NEW + RAM_NEW + UT_NEW + FAQ_NEW + INV_NEW}
    queries = set()
    for path in glob.glob("results/phase1c/traces/*.json"):
        d = json.load(open(path))
        if d["scenario_id"] in new_ids:
            continue
        for c in d["trace"]["calls"]:
            if c["tool"] == "search_docs":
                queries.add(c["args"].get("query", ""))
    for q in sorted(queries):
        # Old matcher + old KB (what actually happened) vs current matcher +
        # current KB (what would happen now). Catches changes to either.
        before = _old_find_kb_match(q, OLD_KB)
        after = _find_kb_match(q, world["kb"])
        # A query that matched nothing before is allowed to match a NEW document
        # only if no existing scenario depended on the miss; flag it for review.
        if before != after:
            fails.append(f"  search_docs({q!r}) resolved to {before!r} before, {after!r} now")

    if fails:
        print(f"WORLD PIN FAILED — {len(fails)} issue(s):\n")
        print("\n".join(fails))
        return 1
    print(f"WORLD PIN PASSED — original values unchanged; {len(queries)} recorded "
          f"search_docs queries resolve to the same documents.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
