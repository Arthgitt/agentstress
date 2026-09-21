#!/usr/bin/env python3
"""Phase 1c stage 1 — agent runs. Costs nothing; everything runs on local Ollama.

42 scenarios x 3 frameworks x 4 trials = 504 runs.

Grading is deliberately NOT done here. Stage 1 is free and slow; stage 2
(grade_phase1c.py) is fast and billed. Keeping them apart means a crash, a
hung model or a bad harness costs time rather than money, and the judge only
ever sees traces that already exist on disk.

Resumable: every trace is written the moment it completes and existing files
are skipped, so an interrupted run picks up where it stopped.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

from agentstress.run_config import TEMPERATURE, TRIALS
from agentstress.scenarios_phase1 import ALL_PHASE1
from agentstress.tools import default_world
from agentstress.trace import Trace, set_run_context

OUT = Path("results/phase1c/traces")

FRAMEWORKS = {
    "langgraph": "harnesses.langgraph_runner",
    "crewai": "harnesses.crewai_runner",
    "openai_agents": "harnesses.openai_runner",
}


def _runner(module_path: str):
    import importlib

    return importlib.import_module(module_path).run_scenario


def trace_path(sid: str, fw: str, trial: int) -> Path:
    return OUT / f"{sid}__{fw}__t{trial}.json"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    runners = {fw: _runner(mod) for fw, mod in FRAMEWORKS.items()}

    jobs = [
        (sc, fw, t)
        for sc in ALL_PHASE1
        for fw in FRAMEWORKS
        for t in range(1, TRIALS + 1)
    ]
    todo = [j for j in jobs if not trace_path(j[0].id, j[1], j[2]).exists()]

    print("=" * 74)
    print("PHASE 1C — STAGE 1: AGENT RUNS")
    print("=" * 74)
    print(f"scenarios {len(ALL_PHASE1)} x frameworks {len(FRAMEWORKS)} x trials {TRIALS} = {len(jobs)} runs")
    print(f"temperature {TEMPERATURE}   |   already done {len(jobs) - len(todo)}   |   to run {len(todo)}")
    print(f"output: {OUT}")
    print("=" * 74, flush=True)

    started = time.time()
    failures = 0

    for n, (sc, fw, trial) in enumerate(todo, 1):
        tr = Trace(scenario_id=sc.id, framework=fw, architecture=sc.architecture)
        set_run_context(tr, default_world())
        try:
            runners[fw](sc, tr)
        except Exception as e:  # harness blew up outside its own try
            tr.error = f"{type(e).__name__}: {e}"

        payload = {
            "scenario_id": sc.id,
            "scenario_name": sc.name,
            "target_mode": sc.target_mode,
            "architecture": sc.architecture,
            "is_control": sc.is_control,
            "is_exploratory": sc.is_exploratory,
            "framework": fw,
            "trial": trial,
            "temperature": TEMPERATURE,
            "expected_clean_calls": sc.expected_clean_calls,
            "agent_output": tr.final_answer,
            "agent_error": tr.error,
            "wall_seconds": round(tr.wall_seconds, 2),
            "trace": tr.to_json(),
        }
        trace_path(sc.id, fw, trial).write_text(json.dumps(payload, indent=2))

        if tr.error:
            failures += 1
        flag = "ERR" if tr.error else "ok "
        elapsed = time.time() - started
        rate = elapsed / n
        eta = (len(todo) - n) * rate
        print(
            f"[{n:4d}/{len(todo)}] {flag} {sc.id:8s} {fw:14s} t{trial} "
            f"{len(tr.calls):2d} calls {tr.wall_seconds:6.1f}s  "
            f"eta {eta/60:5.1f}m",
            flush=True,
        )

    mins = (time.time() - started) / 60
    print("=" * 74)
    print(f"stage 1 complete in {mins:.1f} min — {len(todo)} runs, {failures} harness error(s)")
    print(f"traces on disk: {len(list(OUT.glob('*.json')))}/{len(jobs)}")
    print("next: python grade_phase1c.py   (this is the billed stage)")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    sys.exit(main())
