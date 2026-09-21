#!/usr/bin/env python3
"""Grade the calibration traces with the Claude judge and compare to human labels.

Reads:  results/calibration_data/*.json, results/calibration_labels.csv
Writes: results/judge_calibration.json, results/agreement_report.md

Scenario metadata (structural_reason, expected_clean_calls) is read from the
LIVE definitions in common/scenarios_phase1.py rather than the copies frozen
into the trace JSONs, so corrections to that metadata take effect without a
re-run of the agents.
"""
from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

from agentstress.scenarios_phase1 import BY_ID_PHASE1
from agentstress.grading.claude_judge import judge_scenario

CAL_DIR = Path("results/calibration_data")
LABELS = Path("results/calibration_labels.csv")
OUT_JSON = Path("results/judge_calibration.json")
OUT_REPORT = Path("results/agreement_report.md")

# Scores within this distance count as agreeing. 0.25 is one rubric step.
TOLERANCE = 0.25


def load_human() -> dict[str, dict]:
    out = {}
    with LABELS.open() as f:
        for row in csv.DictReader(f):
            if not row.get("human_score"):
                continue
            out[row["scenario_id"]] = {
                "score": float(row["human_score"]),
                "verdict": row["human_verdict"].strip().upper(),
                "reasoning": row["human_reasoning"],
                "is_control": bool(row.get("is_control", "").strip()),
            }
    return out


def main() -> None:
    human = load_human()
    print(f"Loaded {len(human)} human labels.\n")

    # Resume: keep prior judgements, re-call only rows that errored. Judging is
    # billed per call, so a rerun should not re-pay for work already done.
    cached: dict[str, dict] = {}
    if OUT_JSON.exists():
        for r in json.loads(OUT_JSON.read_text()):
            if r.get("judge_verdict") != "ERROR":
                cached[r["scenario_id"]] = r
        if cached:
            print(f"Reusing {len(cached)} cached judgements; re-judging the rest.\n")

    records = []
    tokens = 0

    for sid, h in human.items():
        path = CAL_DIR / f"{sid}_langgraph_cal.json"
        if not path.exists():
            print(f"  {sid:8s} SKIP (no trace)")
            continue
        d = json.loads(path.read_text())
        sc = BY_ID_PHASE1[sid]

        if d["architecture"] == "handoff":
            shown = (
                f"[phase 1 - researcher]\n{sc.researcher_prompt}\n\n"
                f"[phase 2 - writer]\n{sc.writer_prompt_template}"
            )
        else:
            shown = sc.prompt

        # Reuse only the JUDGE's output. The human side and the comparison are
        # always recomputed, so revised labels take effect without re-billing.
        c = cached.get(sid)
        if c:
            res = {
                "score": c["judge_score"],
                "verdict": c["judge_verdict"],
                "reasoning": c["judge_reasoning"],
                "tokens_used": 0,
            }
        else:
            res = judge_scenario(
                scenario_id=sid,
                target_mode=d["target_mode"],
                framework="langgraph",
                agent_output=d.get("agent_output") or "",
                prompt=shown,
                structural_reason=sc.structural_reason,
                tool_calls=d["trace"]["calls"],
                expected_clean_calls=sc.expected_clean_calls,
            )
        tokens += res["tokens_used"]

        delta = abs(res["score"] - h["score"]) if res["score"] >= 0 else None
        score_agree = delta is not None and delta <= TOLERANCE
        verdict_agree = res["verdict"] == h["verdict"]

        records.append(
            {
                "scenario_id": sid,
                "target_mode": d["target_mode"],
                "is_control": h["is_control"],
                "human_score": h["score"],
                "human_verdict": h["verdict"],
                "human_reasoning": h["reasoning"],
                "judge_score": res["score"],
                "judge_verdict": res["verdict"],
                "judge_reasoning": res["reasoning"],
                "delta": delta,
                "score_agree": score_agree,
                "verdict_agree": verdict_agree,
            }
        )

        mark = "OK " if verdict_agree and score_agree else ("~  " if verdict_agree else "XX ")
        print(
            f"  {mark}{sid:8s} human={h['score']:.2f}/{h['verdict']:4s}  "
            f"judge={res['score']:.2f}/{res['verdict']:4s}"
        )

    OUT_JSON.write_text(json.dumps(records, indent=2))

    # ---- aggregate -------------------------------------------------------
    n = len(records)
    v_agree = sum(r["verdict_agree"] for r in records)
    s_agree = sum(r["score_agree"] for r in records)
    deltas = [r["delta"] for r in records if r["delta"] is not None]

    by_mode: dict[str, list] = {}
    for r in records:
        by_mode.setdefault(r["target_mode"], []).append(r)

    lines = ["# Judge / human agreement — calibration\n"]
    lines.append(
        f"{n} scenarios, LangGraph + qwen2.5:7b-instruct, judged by "
        f"`claude-opus-5`. Agreement counts a score within ±{TOLERANCE} "
        f"(one rubric step).\n"
    )
    lines.append("| Metric | Result |")
    lines.append("|---|---|")
    lines.append(f"| Verdict agreement (PASS/FAIL) | **{v_agree}/{n} = {100*v_agree/n:.0f}%** |")
    lines.append(f"| Score agreement (±{TOLERANCE}) | **{s_agree}/{n} = {100*s_agree/n:.0f}%** |")
    if deltas:
        lines.append(f"| Mean absolute score gap | {statistics.mean(deltas):.3f} |")
        lines.append(f"| Max score gap | {max(deltas):.2f} |")
    lines.append(f"| Judge tokens used | {tokens:,} |")

    lines.append("\n## By mode\n")
    lines.append("| Mode | n | Verdict agree | Score agree | Mean gap | Judge bias |")
    lines.append("|---|---|---|---|---|---|")
    for mode in ["RAM", "FAQ", "UT", "INV"]:
        rs = by_mode.get(mode, [])
        if not rs:
            continue
        m = len(rs)
        va = sum(r["verdict_agree"] for r in rs)
        sa = sum(r["score_agree"] for r in rs)
        ds = [r["delta"] for r in rs if r["delta"] is not None]
        signed = [r["judge_score"] - r["human_score"] for r in rs if r["judge_score"] >= 0]
        bias = statistics.mean(signed) if signed else 0.0
        direction = "harsher" if bias < -0.05 else ("softer" if bias > 0.05 else "aligned")
        lines.append(
            f"| {mode} | {m} | {va}/{m} ({100*va/m:.0f}%) | {sa}/{m} ({100*sa/m:.0f}%) | "
            f"{statistics.mean(ds):.3f} | {bias:+.2f} ({direction}) |"
        )

    controls = [r for r in records if r["is_control"]]
    if controls:
        ca = sum(r["verdict_agree"] for r in controls)
        lines.append(f"\n**Controls:** {ca}/{len(controls)} verdict agreement.\n")

    disagreements = [r for r in records if not r["verdict_agree"] or not r["score_agree"]]
    lines.append(f"\n## Disagreements ({len(disagreements)})\n")
    if not disagreements:
        lines.append("None.\n")
    for r in sorted(disagreements, key=lambda x: -(x["delta"] or 0)):
        flag = "**verdict flip**" if not r["verdict_agree"] else "score gap"
        gap = f"gap {r['delta']:.2f}" if r["delta"] is not None else "judge errored"
        lines.append(f"\n### {r['scenario_id']} ({r['target_mode']}) — {flag}, {gap}\n")
        lines.append(f"- **Human {r['human_score']:.2f} {r['human_verdict']}** — {r['human_reasoning']}")
        lines.append(f"- **Judge {r['judge_score']:.2f} {r['judge_verdict']}** — {r['judge_reasoning']}")

    OUT_REPORT.write_text("\n".join(lines))

    print(f"\n{'='*64}")
    print(f"Verdict agreement: {v_agree}/{n} = {100*v_agree/n:.0f}%")
    print(f"Score agreement (±{TOLERANCE}): {s_agree}/{n} = {100*s_agree/n:.0f}%")
    print(f"Judge tokens: {tokens:,}")
    print(f"Report: {OUT_REPORT}")
    print("=" * 64)


if __name__ == "__main__":
    main()
