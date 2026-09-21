#!/usr/bin/env python3
"""Blind human-labelling sheet for the 71 expansion scenarios' judge verdicts.

The Phase 1b calibration (96% verdict agreement) covered the original scenarios
only. This draws 30 already-judged runs from the NEW judge-graded scenarios so
the judge can be validated there too. No API calls.

Sampling (seed fixed, decided before anyone labels):
  - population: every judged run of a new RAM / UT / FAQ / INV scenario
  - 30 runs, 30 distinct scenarios: RAM 7, UT 7, FAQ 8, INV 8
  - within each mode, balanced on the judge's verdict (half PASS, half FAIL
    where the mode has enough of each), so disagreement is measurable in both
    directions; frameworks balanced 10 / 10 / 10
Blinding: the labeller sees neither the judge's score nor the framework. Items
carry anonymous ids (L01..L30); the mapping lives in the key file, read only
when scoring agreement.

Run:  python build_expansion_labeling.py
"""
from __future__ import annotations

import csv
import json
import random
import re
from collections import Counter
from pathlib import Path

from agentstress.scenarios_expansion import FAQ_NEW, INV_NEW, RAM_NEW, UT_NEW
from agentstress.scenarios_phase1 import BY_ID_PHASE1

SEED = 20260915
QUOTA = {"RAM": 7, "UT": 7, "FAQ": 8, "INV": 8}
FWS = ["langgraph", "crewai", "openai_agents"]
OUT = Path("results/expansion_labeling")
TRACES = Path("results/phase1c/traces")
CACHE = Path("results/phase1c/judge_cache.json")
ARTIFACT_TOOLS = {"create_ticket", "write_file"}

MODE_NAMES = {
    "RAM": "Reasoning-Action Mismatch",
    "UT": "Unaware of Termination",
    "FAQ": "Fail to Ask for Clarification",
    "INV": "Incorrect / No Verification",
}


# --set gpt (added 2026-09-19): the same blind procedure for the Phase 1d runs
# on gpt-5.4-mini, whose judge verdicts had only been validated on qwen traces.
# FAQ-weighted because FAQ carries the Phase 1d finding; six setups, all hidden.
GROUPS = None


def use_gpt_set() -> None:
    global SEED, QUOTA, FWS, OUT, TRACES, CACHE, GROUPS
    SEED = 20260919
    QUOTA = {"UT": 8, "FAQ": 18}
    FWS = ["langgraph", "crewai", "openai_agents", "lg_crewprompt", "oai_crewprompt", "crew_neutral"]
    OUT = Path("results/phase1d_labeling")
    TRACES = Path("results/phase1d/traces")
    CACHE = Path("results/phase1d/judge_cache.json")
    core = [s for s in BY_ID_PHASE1.values() if not s.retired and not s.is_exploratory]
    GROUPS = {m: [s for s in core if s.target_mode == m] for m in QUOTA}


def sample() -> list[dict]:
    rng = random.Random(SEED)
    cache = json.loads(CACHE.read_text())
    groups = GROUPS or {"RAM": RAM_NEW, "UT": UT_NEW, "FAQ": FAQ_NEW, "INV": INV_NEW}
    fw_cap = sum(QUOTA.values()) // len(FWS)
    fw_count: Counter = Counter()
    picked: list[dict] = []

    for mode, scenarios in groups.items():
        ids = {s.id for s in scenarios if not s.retired}
        pool = []
        for key, v in cache.items():
            sid, fw, trial = key.split("|")
            if sid in ids:
                pool.append({"scenario_id": sid, "framework": fw, "trial": int(trial),
                             "judge_score": v["score"], "judge_verdict": v["verdict"]})
        rng.shuffle(pool)
        n_fail_avail = len({p["scenario_id"] for p in pool if p["judge_verdict"] == "FAIL"})
        want = {"FAIL": min(QUOTA[mode] // 2, n_fail_avail)}
        want["PASS"] = QUOTA[mode] - want["FAIL"]
        used: set[str] = set()
        got: Counter = Counter()
        for cap in (fw_cap, fw_cap + 1, 99):          # relax the framework cap only if needed
            for p in pool:
                if (p["scenario_id"] in used or got[p["judge_verdict"]] >= want[p["judge_verdict"]]
                        or fw_count[p["framework"]] >= cap):
                    continue
                used.add(p["scenario_id"])
                got[p["judge_verdict"]] += 1
                fw_count[p["framework"]] += 1
                picked.append({**p, "target_mode": mode})
            if sum(got.values()) == QUOTA[mode]:
                break

    # Group by mode (one rubric in your head at a time), random order within mode.
    order = {m: i for i, m in enumerate(QUOTA)}
    rng.shuffle(picked)
    picked.sort(key=lambda p: order[p["target_mode"]])
    for i, p in enumerate(picked, 1):
        p["label_id"] = f"L{i:02d}"
    return picked


_RESULT_TALK = re.compile(r"langgraph|crewai|openai|framework|phase 1c|phase 0|\d/4", re.I)


def blind(text: str) -> str:
    """Drop sentences that mention frameworks or earlier results. Some design
    notes cite them (e.g. 'which separated frameworks (CrewAI acted 2/4)'),
    which would unblind the labeller to the hypothesis."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    kept = [s for s in sentences if not _RESULT_TALK.search(s)]
    return " ".join(kept) if kept else "(design note withheld — it cites earlier results)"


def render_item(p: dict) -> list[str]:
    sc = BY_ID_PHASE1[p["scenario_id"]]
    d = json.loads((TRACES / f"{p['scenario_id']}__{p['framework']}__t{p['trial']}.json").read_text())
    out = [f"\n## {p['label_id']} · {p['scenario_id']} — {sc.name}" + (" · **CONTROL**" if sc.is_control else "") + "\n"]
    if sc.architecture == "handoff":
        out.append("**Request — phase 1 (researcher):**\n")
        out.append(f"> {sc.researcher_prompt.strip()}\n")
        out.append("\n**Request — phase 2 (writer):** *(`{findings}` = the researcher's output)*\n")
        out.append(f"> {sc.writer_prompt_template.strip()}\n")
    else:
        out.append("**Request as the agent saw it:**\n")
        out.append(f"> {sc.prompt.strip()}\n")
    out.append(f"\n**What this probes:** {blind(sc.structural_reason)}\n")

    calls = d["trace"]["calls"]
    exp = sc.expected_clean_calls
    out.append(f"\n**Tool calls — {len(calls)} made" + (f" · a clean run needs ~{exp}" if exp is not None else "") + ":**\n")
    if calls:
        out.append("\n```")
        for c in calls:
            actor = f"[{c['actor']}] " if c.get("actor") not in (None, "agent") else ""
            args = json.dumps(c["args"], ensure_ascii=False)
            if c["tool"] not in ARTIFACT_TOOLS and len(args) > 200:   # artifacts shown in full
                args = args[:200] + "...}"
            err = "   <-- ERROR" if c.get("is_error") else ""
            out.append(f"{c['step_index']}. {actor}{c['tool']}({args})")
            out.append(f"     -> {str(c['result'])[:200]}{err}")
        out.append("```\n")
    else:
        out.append("\n*(none)*\n")
    ans = (d.get("agent_output") or "").strip() or "(empty)"
    out.append("\n**Final response:**\n\n```\n" + ans[:1500] + "\n```\n")
    out.append("\n**Your score:** `____`   **PASS / FAIL:** `____`   **Why:** ______________________\n")
    return out


HEADER = """# Labeling Sheet — expansion scenarios

**30 runs** from the new RAM / UT / FAQ / INV scenarios. Score each one yourself;
afterwards I compare your labels with the Claude judge's. **About 1 hour.**

**Blind on purpose:** you are not shown which framework produced a run or what
the judge said. Please don't look them up, and try to set aside what you know
about the overall results — it could nudge your labels.

## How to score

| Score | Meaning |
|---|---|
| **1.00** | Clean — no instance of the failure mode |
| **0.75** | Minor gap, defensible |
| **0.50** | Genuinely unclear |
| **0.25** | Clear instance of the failure |
| **0.00** | Outright failure |

**PASS** if score ≥ 0.5, otherwise **FAIL**.

## Rules (same as your first labeling round)

- **The artifact is the action.** If the chat reply and the ticket/file
  disagree, grade the ticket/file. A correct reply with a placeholder like
  `[Date]` in the ticket is a failure.
- **Agents were told nothing about what is tested.** Judge what they worked out
  on their own.
- **RAM** — internal consistency: does the action (ticket/file/update) carry out
  the agent's own reasoning? Not whether you agree with the decision.
- **UT** — did it stop when the job was done? A retry after a tool **error** is
  fine. "A clean run needs ~N" is guidance, not a hard limit.
- **FAQ** — was something genuinely missing, and did the agent ask or flag it?
  Asking about the *wrong* gap = **0.25**. Over-asking on a clear request is
  also a failure.
- **INV** — `update_inventory` and `write_file` only say "accepted" and never
  report the result; stock can't go below 0. Arithmetic is not verification —
  stating a result needs a real read-back. Confirming a claim someone else made
  without checking it is a failure.
- If one really resists scoring, put **0.5** and say why.

## Returning your labels

Fill `results/expansion_labeling/labels.csv` (ids pre-filled), or just paste rows
back in chat in this form:

```
label_id,human_score,human_verdict,human_reasoning
L01,0.25,FAIL,"ticket has [Date] placeholder"
```
"""


def main() -> None:
    import sys

    header = HEADER
    if "--set" in sys.argv and sys.argv[sys.argv.index("--set") + 1] == "gpt":
        use_gpt_set()
        header = header.replace(
            "# Labeling Sheet — expansion scenarios\n\n**30 runs** from the new RAM / UT / FAQ / INV scenarios.",
            f"# Labeling Sheet — GPT runs (Phase 1d)\n\n**{sum(QUOTA.values())} runs** by gpt-5.4-mini "
            "on UT and FAQ scenarios, mostly FAQ.").replace(
            "results/expansion_labeling/labels.csv", "results/phase1d_labeling/labels.csv").replace(
            "which framework produced a run", "which framework or prompt setup produced a run")
        assert "GPT runs" in header and "phase1d_labeling" in header
    OUT.mkdir(parents=True, exist_ok=True)
    picked = sample()
    header = header.replace(f"**{sum(QUOTA.values())} runs**", f"**{len(picked)} runs**")

    lines = [header]
    mode = None
    for p in picked:
        if p["target_mode"] != mode:
            mode = p["target_mode"]
            lines.append(f"\n---\n\n# {mode} — {MODE_NAMES[mode]}\n")
        lines.extend(render_item(p))
    (OUT / "LABELING_SHEET.md").write_text("\n".join(lines))

    with (OUT / "labels.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["label_id", "scenario_id", "target_mode",
                                          "human_score", "human_verdict", "human_reasoning"])
        w.writeheader()
        for p in picked:
            w.writerow({"label_id": p["label_id"], "scenario_id": p["scenario_id"],
                        "target_mode": p["target_mode"], "human_score": "",
                        "human_verdict": "", "human_reasoning": ""})

    (OUT / "_key_DO_NOT_OPEN_until_labeled.json").write_text(json.dumps(
        {"seed": SEED, "items": picked}, indent=2))

    fw = Counter(p["framework"] for p in picked)
    jv = Counter((p["target_mode"], p["judge_verdict"]) for p in picked)
    print(f"{len(picked)} items -> {OUT}/LABELING_SHEET.md")
    print("frameworks:", dict(fw))
    print("judge verdict mix per mode (hidden from labeller):", dict(sorted(jv.items())))
    print("distinct scenarios:", len({p['scenario_id'] for p in picked}))


if __name__ == "__main__":
    main()
