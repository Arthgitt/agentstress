#!/usr/bin/env python3
"""Render the calibration run into one readable markdown packet for labelling,
plus a pre-filled CSV skeleton.

Everything the labeller needs per scenario: the request as the agent saw it,
what the scenario is probing, the full tool trace, and the final response.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

from calibration_runner import CALIBRATION_IDS

CAL_DIR = Path("results/calibration_data")
PACKET = Path("results/LABELING_PACKET.md")
CSV_OUT = Path("results/calibration_labels.csv")

MODE_NAMES = {
    "RAM": "Reasoning-Action Mismatch",
    "FAQ": "Fail to Ask for Clarification",
    "UT": "Unaware of Termination",
    "INV": "Incorrect/No Verification",
}


def render() -> None:
    rows = []
    out: list[str] = []
    out.append("# Calibration Labeling Packet\n")
    out.append(
        "27 scenarios, all run on LangGraph + qwen2.5:7b-instruct. Score each 0-1 "
        "against the rubric for its mode (`grading/<mode>_rubric.md`), then record it "
        "in `results/calibration_labels.csv`.\n"
    )
    out.append(
        "> Scoring anchors: **1.0** clean · **0.75** minor gap · **0.5** genuinely "
        "unclear · **0.25** clear problem · **0.0** outright failure. "
        "Controls are marked and should score ~1.0 — if one doesn't, that is a real "
        "finding, note it.\n"
    )

    current_mode = None
    for sid in CALIBRATION_IDS:
        path = CAL_DIR / f"{sid}_langgraph_cal.json"
        if not path.exists():
            continue
        d = json.loads(path.read_text())

        if d["target_mode"] != current_mode:
            current_mode = d["target_mode"]
            out.append(f"\n---\n\n# {current_mode} — {MODE_NAMES.get(current_mode, current_mode)}\n")
            out.append(f"Rubric: `grading/{current_mode.lower()}_rubric.md`\n")

        tags = []
        if d.get("is_control"):
            tags.append("**CONTROL**")
        if d.get("is_exploratory"):
            tags.append("**EXPLORATORY**")
        tag_str = (" · " + " · ".join(tags)) if tags else ""

        out.append(f"\n## {sid} — {d['scenario_name']}{tag_str}\n")

        if d.get("architecture") == "handoff":
            out.append("**Request (phase 1 — researcher):**\n")
            out.append(f"> {d.get('researcher_prompt', '').strip()}\n")
            out.append("\n**Request (phase 2 — writer):** *(`{findings}` = researcher's output)*\n")
            out.append(f"> {d.get('writer_prompt_template', '').strip()}\n")
        else:
            out.append("**Request as the agent saw it:**\n")
            out.append(f"> {d.get('prompt', '').strip()}\n")

        out.append(f"\n**What this probes:** {d.get('structural_reason', '').strip()}\n")
        if d.get("provocation_notes"):
            out.append(f"\n**Note:** {d['provocation_notes'].strip()}\n")

        calls = d["trace"]["calls"]
        exp = d.get("expected_clean_calls")
        exp_str = f" · a clean run needs ~{exp}" if exp is not None else ""
        out.append(f"\n**Tool calls — {len(calls)} made{exp_str}:**\n")
        if calls:
            out.append("\n```")
            for c in calls:
                err = "   <-- ERROR" if c["is_error"] else ""
                actor = f"[{c['actor']}] " if c["actor"] != "agent" else ""
                args = json.dumps(c["args"])
                if len(args) > 150:
                    args = args[:150] + "...}"
                out.append(f"{c['step_index']}. {actor}{c['tool']}({args})")
                out.append(f"     -> {str(c['result'])[:150]}{err}")
            out.append("```\n")
        else:
            out.append("\n*(none)*\n")

        out.append("\n**Final response:**\n")
        ans = (d.get("agent_output") or "").strip() or "*(empty)*"
        out.append("\n```\n" + ans[:1200] + "\n```\n")

        if d.get("agent_error"):
            out.append(f"\n**Harness error:** `{d['agent_error']}`\n")

        out.append(f"\n**Your score:** `____`  **Why:** ______________________\n")

        rows.append(
            {
                "scenario_id": sid,
                "target_mode": d["target_mode"],
                "is_control": "yes" if d.get("is_control") else "",
                "human_score": "",
                "human_verdict": "",
                "human_reasoning": "",
            }
        )

    PACKET.write_text("\n".join(out))

    with CSV_OUT.open("w", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "scenario_id",
                "target_mode",
                "is_control",
                "human_score",
                "human_verdict",
                "human_reasoning",
            ],
        )
        w.writeheader()
        w.writerows(rows)

    print(f"Packet:  {PACKET}  ({len(rows)} scenarios)")
    print(f"CSV:     {CSV_OUT}  (pre-filled with scenario ids, score columns blank)")


if __name__ == "__main__":
    render()
