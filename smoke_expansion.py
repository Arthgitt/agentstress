#!/usr/bin/env python3
"""Free design check for the 71 expansion scenarios — one LangGraph run each.

Not experimental data: nothing here feeds Phase 1 results. It exists to catch
broken scenario designs before the billed run — a knowledge-base query that
never resolves, a task no framework can start, a correctness check that fires
on a sensible answer. Traces go to results/expansion_smoke/, separate from
results/phase1c/.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from agentstress.correctness import check as correctness_check
from agentstress.scenarios_expansion import FAQ_NEW, INV_NEW, RAM_NEW, SR_NEW, UT_NEW
from agentstress.tools import default_world
from agentstress.trace import Trace, set_run_context
from agentstress.grader import grade_trace
from agentstress.harnesses.langgraph_runner import run_scenario

OUT = Path("results/expansion_smoke")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    scenarios = SR_NEW + RAM_NEW + UT_NEW + FAQ_NEW + INV_NEW
    rows = []
    start = time.time()
    for i, sc in enumerate(scenarios, 1):
        path = OUT / f"{sc.id}__langgraph.json"
        if path.exists():
            d = json.loads(path.read_text())
        else:
            tr = Trace(scenario_id=sc.id, framework="langgraph", architecture=sc.architecture)
            set_run_context(tr, default_world())
            run_scenario(sc, tr)
            d = {"scenario_id": sc.id, "agent_output": tr.final_answer,
                 "agent_error": tr.error, "trace": tr.to_json()}
            path.write_text(json.dumps(d, indent=2))

        calls = d["trace"]["calls"]
        tool_errors = [f"{c['tool']}({json.dumps(c['args'])[:40]})" for c in calls if c["is_error"]]
        cx = correctness_check(sc.id, d["trace"], d.get("agent_output") or "")
        sr = grade_trace(d["trace"], sc.repeated_mutations_expected) if sc.target_mode == "SR" else None
        row = {
            "id": sc.id, "mode": sc.target_mode, "calls": len(calls),
            "expected": sc.expected_clean_calls, "harness_error": d.get("agent_error"),
            "tool_errors": tool_errors,
            "correct": None if cx is None else cx["correct"],
            "problems": [] if cx is None else cx["problems"],
            "sr_verdict": None if sr is None else sr["extended_verdict"],
        }
        rows.append(row)
        flag = "ERR " if row["harness_error"] else "    "
        cx_s = "-" if row["correct"] is None else ("right" if row["correct"] else "WRONG")
        print(f"[{i:2d}/{len(scenarios)}] {flag}{sc.id:7s} calls {len(calls):2d}/{sc.expected_clean_calls!s:4s} "
              f"correct={cx_s:5s} tool_err={len(tool_errors)}", flush=True)

    (OUT / "_summary.json").write_text(json.dumps(rows, indent=2))
    print(f"\ndone in {(time.time()-start)/60:.1f} min -> {OUT}/_summary.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
