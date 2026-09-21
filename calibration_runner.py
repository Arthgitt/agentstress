#!/usr/bin/env python3
"""Run 27 calibration scenarios on LangGraph, save outputs for hand-labeling."""
import json
import time
from pathlib import Path

from agentstress.scenarios_phase1 import BY_ID_PHASE1
from agentstress.tools import default_world
from agentstress.trace import Trace, set_run_context
from agentstress.harnesses.langgraph_runner import run_scenario

# Calibration subset: every judge-graded mode, each with its control first.
# SR is excluded — it is graded deterministically and needs no judge calibration.
CALIBRATION_IDS = [
    # RAM (6)
    "RAM-09", "RAM-02", "RAM-03", "RAM-04", "RAM-06", "RAM-07",
    # FAQ (7)
    "FAQ-08", "FAQ-01", "FAQ-02", "FAQ-03", "FAQ-04", "FAQ-05", "FAQ-09",
    # UT (6)
    "UT-07", "UT-01", "UT-02", "UT-04", "UT-05", "UT-08",
    # INV (8)
    "INV-08", "INV-01", "INV-02", "INV-03", "INV-04", "INV-05", "INV-06", "INV-09",
]

def run_calibration():
    cal_dir = Path("results/calibration_data")
    cal_dir.mkdir(parents=True, exist_ok=True)

    results = []
    total = len(CALIBRATION_IDS)
    print(f"\n{'='*80}")
    print(f"CALIBRATION RUN: {total} scenarios on LangGraph")
    print(f"{'='*80}\n")

    for i, scenario_id in enumerate(CALIBRATION_IDS, 1):
        scenario = BY_ID_PHASE1.get(scenario_id)
        if not scenario:
            print(f"[{i:2d}/{total}] {scenario_id:8s} — NOT FOUND")
            continue

        try:
            print(f"[{i:2d}/{total}] {scenario_id:8s} {scenario.name:40s} ", end="", flush=True)

            trace = Trace(
                scenario_id=scenario_id,
                framework="langgraph",
                architecture=scenario.architecture
            )
            set_run_context(trace, default_world())
            run_scenario(scenario, trace)

            # Save calibration data
            cal_data = {
                "scenario_id": scenario_id,
                "scenario_name": scenario.name,
                "target_mode": scenario.target_mode,
                "architecture": scenario.architecture,
                "is_control": scenario.is_control,
                "is_exploratory": scenario.is_exploratory,
                "confidence": scenario.confidence,
                # Everything the agent actually saw. For handoff scenarios both
                # phases are recorded so the labeller can see where a repeated or
                # unverified call sat relative to the agent boundary.
                "prompt": scenario.prompt,
                "researcher_prompt": scenario.researcher_prompt,
                "writer_prompt_template": scenario.writer_prompt_template,
                "structural_reason": scenario.structural_reason,
                "provocation_notes": scenario.provocation_notes,
                "expected_clean_calls": scenario.expected_clean_calls,
                "agent_output": trace.final_answer,
                "agent_error": trace.error,
                "trace": trace.to_json(),
                "wall_seconds": trace.wall_seconds,
            }

            # Save to file
            cal_file = cal_dir / f"{scenario_id}_langgraph_cal.json"
            cal_file.write_text(json.dumps(cal_data, indent=2))
            results.append(cal_data)

            status = "✓" if not trace.error else "✗"
            print(f"{status} ({trace.wall_seconds:.1f}s)")
        except Exception as e:
            print(f"✗ ERROR: {type(e).__name__}")
            results.append({
                "scenario_id": scenario_id,
                "error": str(e)
            })

    # Save master index
    index_file = cal_dir / "_index.json"
    index_file.write_text(json.dumps(results, indent=2))

    print(f"\n{'='*80}")
    print(f"Calibration data saved to: {cal_dir}")
    print(f"Total scenarios: {len([r for r in results if 'error' not in r])}/{len(CALIBRATION_IDS)}")
    print(f"{'='*80}\n")

    return results

if __name__ == "__main__":
    run_calibration()
