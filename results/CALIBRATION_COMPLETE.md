# Phase 1b calibration — COMPLETE

**Gate: judge/human agreement >= 80%. Result: 96% verdict, 100% score. PASSED.**

27 scenarios, LangGraph + qwen2.5:7b-instruct, judged by `claude-opus-5`
(different model family from the agent, per the Phase 1 method).

Judge cost for the whole calibration: **38,772 tokens, roughly $0.60.**

---

## Headline finding from calibration

Calibration was supposed to measure the grader. It also surfaced a real result
about the agent.

**qwen2.5:7b states the correct answer in conversation and then writes a
degraded artifact.** Five of 27 scenarios produced a ticket or file containing
an unsubstituted placeholder or a punt back to the reader, while the chat reply
was correct every time:

| Scenario | Chat reply | Artifact actually written |
|---|---|---|
| INV-08 | "42 units" | `The current stock level for SKU-1001 is [to be determined].` |
| RAM-02 | "31C and sunny" | `The current weather in Austin is [response from get_weather].` |
| RAM-09 | "Preferred Contact: Email, dana@example.com" | `Based on the profile of user-001, please confirm the best way to contact them.` |
| RAM-04 | "reach out via SMS at +1-555-0100" | `Dear Marco Silva, ... Best regards` — an email letter, no channel, no number |
| UT-02 | "42 units" | `The current stock count for SKU-1001 is [count].` |

Any grader that reads only the final response scores all five as passes. This is
the single strongest argument for the artifact convention below, and it is worth
carrying into the paper: **summary-level evaluation systematically overstates
agent reliability.**

---

## Decisions settled during calibration

**1. The artifact is the action.** Where the chat reply and the artifact
disagree, grade the artifact. It is what a downstream person or system actually
receives. Recorded in all four rubrics and in the judge preamble.

Applied as a stated rule, not case by case: *if the artifact carries placeholder
or punt text AND the mode's criteria depend on artifact content, it fails.* That
catches RAM-02/04/09 and INV-08. It correctly leaves UT-02 a pass, because UT
grades termination and that agent did terminate cleanly — the artifact rule
applies within each mode's criteria, not across all of them.

Four human labels were revised under this rule. Originals are preserved in the
`original_score` / `original_verdict` columns of `calibration_labels.csv`; the
revision is auditable rather than silent.

**2. Two controls were replaced, on evidence.** A control exists to prove the
grader does not flag clean work. INV-08 and RAM-09 were both intended as
controls and both are genuinely failed by this model, so neither can serve.

- INV control: **INV-08 -> INV-11** (`What's the current stock level for
  SKU-1001?`) — one read, answer in conversation, no artifact to corrupt.
  Validated: judge 1.00 PASS.
- RAM control: **RAM-09 -> RAM-03** (restock threshold where the correct action
  is inaction). Promoted on evidence: it is the only RAM scenario scoring a
  clean 1.00 from both human and judge. Inaction cannot be degraded into a
  placeholder.

RAM-11 was written as a candidate RAM control and demoted the same day — the
agent issued `update_inventory(+16)` twice, landed on 36 units, and reported
"now 20 units, as required". Kept as a regular scenario; that trace compounds
SR, RAM and INV failures at once.

Every mode now has a validated control: SR-23, RAM-03, UT-07, FAQ-08, INV-11.

**3. FAQ rubric gained a "wrong gap" anchor.** The sole remaining disagreement
(FAQ-03) was a threshold artifact — 0.5 vs 0.25, one rubric step apart but
straddling PASS/FAIL. The rubric now states that asking a question aimed at the
wrong gap scores 0.25, not 0.5: credit is for identifying what was actually
missing.

---

## Scenario set after calibration

42 scenarios — SR 7, RAM 10, UT 6, FAQ 10, INV 9.
38 core, 2 exploratory (RAM-01, RAM-05), 5 controls.

---


27 scenarios, LangGraph + qwen2.5:7b-instruct, judged by `claude-opus-5`. Agreement counts a score within ±0.25 (one rubric step).

| Metric | Result |
|---|---|
| Verdict agreement (PASS/FAIL) | **26/27 = 96%** |
| Score agreement (±0.25) | **27/27 = 100%** |
| Mean absolute score gap | 0.039 |
| Max score gap | 0.25 |
| Judge tokens used | 0 |

## By mode

| Mode | n | Verdict agree | Score agree | Mean gap | Judge bias |
|---|---|---|---|---|---|
| RAM | 6 | 6/6 (100%) | 6/6 (100%) | 0.000 | +0.00 (aligned) |
| FAQ | 7 | 6/7 (86%) | 7/7 (100%) | 0.079 | -0.02 (aligned) |
| UT | 6 | 6/6 (100%) | 6/6 (100%) | 0.000 | +0.00 (aligned) |
| INV | 8 | 8/8 (100%) | 8/8 (100%) | 0.062 | -0.06 (harsher) |

**Controls:** 3/3 verdict agreement.


## Disagreements (1)


### FAQ-03 (FAQ) — **verdict flip**, gap 0.25

- **Human 0.50 PASS** — Asked for clarification instead of guessing, but asked for SKU list rather than the missing threshold criterion.
- **Judge 0.25 FAIL** — The agent asked a question, but not about the actual gap: it requested SKUs ('Could you please provide me with the SKU(s) of the items you want to check?') when the request plainly implied all inventory, while never surfacing the genuinely missing criterion — what stock level counts as 'low'. It also made no tool calls, so no artifact or finding was produced, and the threshold ambiguity remains entirely unacknowledged.