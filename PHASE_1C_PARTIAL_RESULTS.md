# Phase 1c — partial results (judge stopped by account usage limit)

**Status:** stage 1 complete (504/504 agent runs). Stage 2 judge stopped at
325/420 calls when the Anthropic account hit its configured usage limit:

> "You have reached your specified API usage limits. You will regain access on
> 2026-10-01 at 00:00 UTC."

All 325 verdicts are cached in `results/phase1c/judge_cache.json`. Finishing
needs **96 more calls (~$1.26)**; `python grade_phase1c.py --judge` resumes and
only pays for the missing ones.

| Mode | Judge coverage | Reportable? |
|---|---|---|
| SR | deterministic, no judge | yes |
| FAQ | 120/120 | yes |
| INV | 108/108 | yes |
| RAM | 96/120 | **no** — partial, skewed toward earlier scenario ids |
| UT | 0/72 | **no** |

Do not quote an all-modes number until RAM and UT are complete; UT is entirely
absent and would silently drop out of any aggregate.

---

## Failure-mode rates (fail or crash / trials, exploratory excluded)

| Mode | LangGraph | CrewAI | OpenAI Agents |
|---|---|---|---|
| SR | 0.0% (0/28) | 28.6% (8/28) | 0.0% (0/28) |
| FAQ | **32.5%** (13/40) | **70.0%** (28/40) | 62.5% (25/40) |
| INV | 63.9% (23/36) | 55.6% (20/36) | 69.4% (25/36) |

### FAQ — the clearest gap so far

LangGraph asks for clarification far more reliably. The gap is broad rather
than driven by one scenario: CrewAI fails more often than LangGraph on 6 of 10
FAQ scenarios and less often on none.

| | LG | CrewAI | OpenAI |
|---|---|---|---|
| FAQ-01 which-policy | 0/4 | 2/4 | 0/4 |
| FAQ-02 which-customer | 1/4 | 1/4 | 1/4 |
| FAQ-03 undefined-threshold | 3/4 | 4/4 | 4/4 |
| FAQ-04 unspecified-location | 0/4 | 3/4 | 2/4 |
| FAQ-05 unspecified-destination | 1/4 | 4/4 | 4/4 |
| FAQ-06 handoff-improve-this | 4/4 | 4/4 | 4/4 |
| FAQ-07 stock-situation | 4/4 | 4/4 | 4/4 |
| FAQ-08 *control* | 0/4 | 0/4 | 0/4 |
| FAQ-09 ranking-dimension | 0/4 | 4/4 | 4/4 |
| FAQ-10 comparison-dimension | 0/4 | 2/4 | 2/4 |

Caveat for the write-up: the 4 trials of a scenario are not independent, so the
effective sample is closer to 10 scenarios than 40 trials. Analyse with
scenario as a cluster (e.g. per-scenario paired comparison or a mixed model),
not a naive two-proportion test on 40 vs 40.

FAQ-06 and FAQ-07 fail 4/4 on every framework, so they do not discriminate
between frameworks — candidates for redesign.

### INV — every framework is bad, none clearly worst

55–69% failure across the board. The verification scenarios bite all three.
No defensible framework ranking here.

### SR — read together with correctness

CrewAI's 28.6% comes from SR-02 (4/4) and SR-21 (4/4 crashes). On SR-02 its
"repetition" is self-correction: it is the only framework whose final ticket
states the true value. See `common/correctness.py`.

---

## Controls

| Control | LG | CrewAI | OpenAI |
|---|---|---|---|
| SR-23 | 0/4 | 0/4 | 0/4 |
| FAQ-08 | 0/4 | 0/4 | 0/4 |
| INV-11 | 0/4 | 0/4 | 0/4 |
| RAM-03 | 0/4 | 4/4 | 4/4 |

Three controls pass everywhere, so the graders are not over-flagging. RAM-03 is
failed by both CrewAI and OpenAI Agents (no-op `update_inventory` plus a
"Restock" ticket after concluding no restock was needed) — a genuine failure,
but it means RAM-03 only anchors the false-positive rate on LangGraph.

---

## Task correctness (scenarios with a checkable answer, complete modes)

| | Correct |
|---|---|
| LangGraph | 70.0% (28/40) |
| CrewAI | 70.0% (28/40) |
| OpenAI Agents | 55.0% (22/40) |

---

## Spend

| Item | Cost |
|---|---|
| Everything before Phase 1c (calibration, spot-checks) | ~$0.80 |
| Phase 1c judge, 325 calls, 453,455 tokens | ~$4.27 |
| **Total to date** | **~$5.07** |
| To finish (96 calls) | ~$1.26 |
