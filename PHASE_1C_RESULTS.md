# Phase 1c results

> **Superseded for headline claims by `PHASE_1_RESULTS_100.md`** (100 scenarios,
> 1,200 runs, 2026-09-14). This file remains the record of the 42-scenario run.

**Complete.** 42 scenarios × 3 frameworks × 4 trials = 504 agent runs (local
Ollama, qwen2.5:7b-instruct, temperature 0.3). 420 judge verdicts (claude-opus-5),
0 judge errors. SR graded deterministically.

Supersedes `PHASE_1C_PARTIAL_RESULTS.md`.

---

## Headline, stated at the strength the data supports

1. **LangGraph shows fewer failure-mode instances than CrewAI** — better on 15
   scenarios, worse on 5, tied on 20 (sign test, scenario as unit, p = 0.041).
   This does **not** survive correction for the three pairwise framework
   comparisons (Bonferroni p = 0.12). Treat it as suggestive, not established.

2. **The clearest single-mode gap is clarification-seeking (FAQ).** LangGraph
   fails 32.5% of FAQ trials against CrewAI's 70.0%, and is worse on none of the
   10 FAQ scenarios (6 better, 4 tied; p = 0.031). Against OpenAI Agents the
   pattern is the same but weaker (5–0, p = 0.062).

3. **No framework is significantly more *correct*.** At the scenario level every
   correctness comparison is p ≥ 0.51 (after the 2026-09-13 correction below). Fewer failure-mode instances did not
   translate into more right answers.

4. **Failure-mode scores and correctness can point in opposite directions** —
   demonstrated concretely on SR-02, where the two frameworks with a clean
   step-repetition record wrote the wrong stock figure in 8/8 trials and the
   framework flagged for repetition wrote the right one in 4/4 by correcting
   itself. This is a methodological finding about how agent reliability is
   measured, not a claim that one framework is generally more correct.

**Correction to earlier interim reporting:** the trial-level correctness figures
(CrewAI 75.0% vs LangGraph 63.2%) were presented as CrewAI being "most correct".
At the scenario level that difference is not significant (5 vs 6 scenarios,
p = 1.0). The SR-02 inversion is real; a general correctness advantage is not
supported.

---

## Failure-mode rate by mode (fail or crash / trials, exploratory excluded)

| Mode | LangGraph | CrewAI | OpenAI Agents |
|---|---|---|---|
| SR | 0.0% | 28.6% | 0.0% |
| RAM | 62.5% | 53.1% | 59.4% |
| UT | 0.0% | 33.3% | 8.3% |
| FAQ | **32.5%** | **70.0%** | 62.5% |
| INV | 63.9% | 55.6% | 69.4% |
| All | 35.0% | 50.6% | 44.4% |

Per-mode sign tests, LangGraph vs CrewAI, scenario as unit:

| Mode | n | LG better / worse / tie | p |
|---|---|---|---|
| SR | 7 | 2 / 0 / 5 | 0.500 |
| RAM | 8 | 2 / 3 / 3 | 1.000 |
| UT | 6 | 4 / 0 / 2 | 0.125 |
| FAQ | 10 | 6 / 0 / 4 | **0.031** |
| INV | 9 | 1 / 2 / 6 | 1.000 |

RAM and INV show no framework effect: all three frameworks fail these at
53–69%, which reads as a property of the model rather than the orchestration.

## Task correctness (19 scenarios with a checkable answer)

| | Correct trials |
|---|---|
| LangGraph | 63.2% (48/76) |
| CrewAI | 71.1% (54/76) |
| OpenAI Agents | 59.2% (45/76) — *corrected from 57.9% (44/76), see below* |

Scenario-level: LG vs CrewAI 5 more-correct / 6 less / 8 tie (p = 1.00);
LG vs OpenAI 4 / 3 / 12 (p = 1.00); CrewAI vs OpenAI 6 / 3 / 10 (p = 0.51).

**Correction, 2026-09-13.** During the 100-scenario expansion the numeric
matcher in `common/correctness.py` was found to reject correct answers written
with a decimal tail ("$180.00" did not match 180). Re-scoring these same traces
with the fixed matcher changed exactly one trial: SR-20 / OpenAI Agents / trial
1, whose ticket states the correct discounted price as "$180.00". No conclusion
changes — no framework is significantly more correct.

---

## Why every test above uses scenario, not trial, as the unit

**83% of scenario × framework cells had all 4 trials agree** (100 of 120). At
temperature 0.3 the traces vary but the verdict almost never does, so the 4
trials of a scenario are close to one observation. Treating them as independent
would report 160 vs 160 trials and inflate significance roughly fourfold.

The practical consequence: **40 scenarios is underpowered for pairwise framework
claims.** The brief's ~100-scenario target is not optional padding — it is what
the headline comparison needs to reach significance after correction.

---

## Suite quality issues surfaced by the run

**16 of 40 core scenarios do not discriminate** — all three frameworks score
identically. Five are controls, where that is expected (SR-23, FAQ-08, INV-11)
or otherwise uninformative. The rest are redesign candidates:

- Always fail everywhere: RAM-02, INV-01, INV-02, INV-08, FAQ-06, FAQ-07
- Always pass everywhere: SR-01, SR-19, SR-20, SR-22, RAM-06, UT-02
- Mixed but identical: FAQ-02

**Controls are not universal passes.** RAM-03 is failed 4/4 by both CrewAI and
OpenAI Agents (a no-op `update_inventory` and a "Restock" ticket after concluding
no restock was needed); UT-07 is failed 1/4 by CrewAI. SR-23, FAQ-08 and INV-11
pass on every framework, so the graders are not over-flagging.

**SR-21 crashed on CrewAI in 4/4 trials** (empty LLM response in the writer
phase; 8 of 9 attempts overall). Counted as failure, reported separately.

---

## Grading defects found and fixed during this phase

All three were caught by checking results against raw traces before reporting.

| Defect | Effect | Fix |
|---|---|---|
| Correctness regex rejected numbers followed by `.` | every sentence-final value scored missing | numeric boundary rewritten; regression test |
| SR-20 check accepted only one correct framing | "$180 price" scored wrong | accepts $20 or $180 |
| Correctness passed artifacts written before the lookup | RAM-08 CrewAI "Should I pack an umbrella?" scored as correct advice | `grounded_by` ordering check on 7 scenarios; regression test |
| One judge verdict truncated at 700 output tokens | would have been counted as a framework crash | cap raised to 1500; re-judged (1 call) |

Tests: correctness 23, grader 13, prompt hygiene 42 — all passing.

---

## Environment notes for the write-up

- Temperature 0.3, not 0: at 0 the model was fully deterministic and 4 trials
  would have been 4 identical traces. Phase 0 (temperature 0) is not
  reproducible under this setting.
- CrewAI telemetry to `telemetry.crewai.com` timed out 526 times in stage 1,
  inflating CrewAI wall time. Now disabled. Median wall time is similar across
  frameworks (13.7–16.4 s); **the Phase 0 claim that CrewAI is ~2× slower is
  withdrawn.** No latency claims from this run.

---

## Spend

| | Tokens | Cost (est.) |
|---|---|---|
| Before Phase 1c | ~84k | ~$0.80 |
| Phase 1c judge (421 calls incl. 1 re-judge) | 595,702 | ~$5.38 |
| **Project total** | ~680k | **~$6.20** |

Estimates use the measured 80/20 input/output split at Opus 5 list price
($5 / $25 per million). Check console.anthropic.com for the billed figure.
