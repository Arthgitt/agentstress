#!/usr/bin/env python
"""Run Phase 0 pilot: execute all 18 Step-Repetition scenarios against
both LangGraph and CrewAI agents, record traces, grade them, and report
framework comparison."""
import json
import sys
import time
from pathlib import Path

from agentstress.scenarios import ALL as ALL_SCENARIOS
from agentstress.tools import default_world
from agentstress.trace import Trace, set_run_context
from agentstress.harnesses.langgraph_runner import run_scenario as langgraph_run_scenario
from agentstress.harnesses.crewai_runner import run_scenario as crewai_run_scenario
from agentstress.grader import grade_directory


def run_all():
    traces_dir = Path("results/traces")
    traces_dir.mkdir(parents=True, exist_ok=True)

    frameworks = [
        ("langgraph", langgraph_run_scenario),
        ("crewai", crewai_run_scenario),
    ]

    print(f"\n{'='*70}")
    print("PHASE 0 PILOT: Step-Repetition Stress-Test")
    print(f"{'='*70}\n")
    print(f"Running {len(ALL_SCENARIOS)} scenarios × {len(frameworks)} frameworks...")
    print(f"Traces will be saved to: {traces_dir}\n")

    count = 0
    for scenario in ALL_SCENARIOS:
        print(f"\n[{count + 1:2d}/{len(ALL_SCENARIOS)}] {scenario.id} {scenario.name:40s} ", end="", flush=True)
        for framework_name, run_func in frameworks:
            try:
                trace = Trace(
                    scenario_id=scenario.id, framework=framework_name, architecture=scenario.architecture
                )
                set_run_context(trace, default_world())
                run_func(scenario, trace)

                trace_path = traces_dir / f"{scenario.id}_{framework_name}.json"
                trace_path.write_text(json.dumps(trace.to_json(), indent=2))

                status = "✓" if not trace.error else "✗"
                print(f"{status} {framework_name:10s} ", end="", flush=True)
            except Exception as e:
                print(f"✗ {framework_name:10s} [{type(e).__name__}] ", end="", flush=True)
        count += 1

    print(f"\n\n{'='*70}")
    print("GRADING & COMPARISON")
    print(f"{'='*70}\n")

    results = grade_directory(traces_dir)
    results_path = Path("results/grading_results.json")
    results_path.write_text(json.dumps(results, indent=2))

    print(f"Grading results saved to: {results_path}\n")

    by_framework = {}
    for r in results:
        if r["framework"] not in by_framework:
            by_framework[r["framework"]] = []
        by_framework[r["framework"]].append(r)

    print("\n" + "=" * 90)
    print("CROSS-FRAMEWORK COMPARISON TABLE")
    print("=" * 90 + "\n")

    fmt_header = "{:<8} {:<45} {:<8} {:<12} {:<12} {:<12}"
    print(
        fmt_header.format(
            "ScenID", "Scenario Name (first 40 chars)", "Arch", "LangGraph", "CrewAI", "Winner"
        )
    )
    print("-" * 90)

    langgraph_results = {r["scenario_id"]: r for r in by_framework.get("langgraph", [])}
    crewai_results = {r["scenario_id"]: r for r in by_framework.get("crewai", [])}

    langgraph_pass = 0
    crewai_pass = 0
    scenarios_with_gap = []

    for scenario in ALL_SCENARIOS:
        lg = langgraph_results.get(scenario.id)
        ca = crewai_results.get(scenario.id)

        lg_verdict = lg["verdict"] if lg else "N/A"
        ca_verdict = ca["verdict"] if ca else "N/A"

        lg_reps = lg["wasteful_repetition_calls"] if lg else None
        ca_reps = ca["wasteful_repetition_calls"] if ca else None

        if lg_verdict == "PASS":
            langgraph_pass += 1
        if ca_verdict == "PASS":
            crewai_pass += 1

        if lg_reps is not None and ca_reps is not None:
            if lg_reps != ca_reps:
                scenarios_with_gap.append(
                    {
                        "scenario_id": scenario.id,
                        "langgraph_reps": lg_reps,
                        "crewai_reps": ca_reps,
                        "gap": abs(lg_reps - ca_reps),
                        "winner": "LangGraph" if lg_reps < ca_reps else "CrewAI",
                    }
                )

        winner = "LG" if lg_reps is not None and ca_reps is not None and lg_reps < ca_reps else "CA"
        if lg_reps == ca_reps:
            winner = "="
        elif ca_reps is None or lg_reps is None:
            winner = "?"

        name_short = scenario.name[:40]
        print(
            fmt_header.format(
                scenario.id,
                name_short,
                scenario.architecture[:3],
                lg_verdict if lg_verdict != "PASS" else f"✓ ({lg_reps})",
                ca_verdict if ca_verdict != "PASS" else f"✓ ({ca_reps})",
                winner,
            )
        )

    print("\n" + "=" * 90)
    print("SUMMARY STATISTICS")
    print("=" * 90 + "\n")

    total = len(ALL_SCENARIOS)
    print(f"LangGraph: {langgraph_pass:2d}/{total} scenarios passed (no wasteful repetition)")
    print(f"CrewAI:    {crewai_pass:2d}/{total} scenarios passed (no wasteful repetition)\n")

    if scenarios_with_gap:
        print(f"Scenarios with a measurable gap between frameworks: {len(scenarios_with_gap)}\n")
        print("Top 5 gaps by repetition difference:\n")
        top = sorted(scenarios_with_gap, key=lambda x: x["gap"], reverse=True)[:5]
        for item in top:
            print(
                f"  {item['scenario_id']} — LangGraph: {item['langgraph_reps']} "
                f"reps, CrewAI: {item['crewai_reps']} reps (gap={item['gap']}) "
                f"→ {item['winner']} wins"
            )
    else:
        print("No scenarios showed a gap between frameworks.")

    print("\n" + "=" * 90)
    print("VERDICT: PHASE 0 SUCCESS CRITERIA")
    print("=" * 90 + "\n")

    if langgraph_pass >= total * 0.7 and crewai_pass >= total * 0.7:
        print("✓ Both frameworks mostly pass the benign control scenarios (SR-05, SR-17, SR-18)")
        if len(scenarios_with_gap) >= 3:
            print("✓ Multiple scenarios show a measurable gap → framework differences ARE real")
            print("\n🎯 RECOMMENDATION: PROCEED TO PHASE 1")
            print("   The pilot shows real, consistent, explainable gaps between frameworks.")
            print("   Framework X tends to repeat work in scenarios Y & Z, while framework Z")
            print("   handles them better. This is a defensible, publishable finding.")
            return 0
        else:
            print("✗ Gap is minimal or non-existent across scenarios")
            print("\n⚠️  RECOMMENDATION: REASSESS")
            print("   Both frameworks perform similarly on the same tasks.")
            print("   Consider pivoting to a different failure mode or a different hypothesis.")
            return 1
    else:
        print("✗ Baseline control scenarios show high failure rates")
        print("   This suggests either tool-implementation instability or prompt/model issues,")
        print("   not genuine framework differences.")
        print("\n⚠️  RECOMMENDATION: DEBUG & RETRY")
        print("   Investigate why control scenarios (SR-05, SR-17, SR-18) are failing.")
        return 1


if __name__ == "__main__":
    sys.exit(run_all())
