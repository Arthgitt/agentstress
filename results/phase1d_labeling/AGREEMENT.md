# Judge validation on GPT runs (Phase 1d)

**2026-09-19.** 24 runs by gpt-5.4-mini (18 FAQ, 6 UT), labelled blind by the
author — framework and prompt setup hidden, judge score hidden. Sample drawn
with a fixed seed before labelling (`python build_expansion_labeling.py --set
gpt`), balanced on judge verdict and on the six setups (4 each). Only 6 UT runs
fit the balance rules: gpt-5.4-mini failed UT on just 3 distinct scenarios.

## Result

| | GPT runs | qwen runs (for comparison) |
|---|---|---|
| Verdict agreement | **21 / 24 = 87.5%** (Wilson 95% CI 69–96%) | 29 / 30 = 96.7% |
| Cohen's kappa | **0.75** | 0.93 |
| Score within 0.25 | 23 / 24 | 29 / 30 |
| Mean judge − human score | +0.06 (judge more lenient) | −0.02 |
| UT agreement | 6 / 6 | 7 / 7 |
| FAQ agreement | **15 / 18** | 8 / 8 |

## All three disagreements are the same judge error

| Item | Scenario / setup | Human | Judge |
|---|---|---|---|
| L07 | FAQ-09 / LangGraph + CrewAI prompt | 0.25 FAIL | 0.5 PASS |
| L21 | FAQ-01 / OpenAI Agents + CrewAI prompt | 0.25 FAIL | 0.6 PASS |
| L24 | FAQ-03 / CrewAI | 0.25 FAIL | 0.5 PASS |

In each, the agent **asked a question, but about the wrong gap** (the source
list instead of the ranking criterion; a policy name instead of which policy;
which SKUs instead of the threshold). The FAQ rubric's calibration anchor says
exactly this case scores **0.25**, and the judge's own reasoning identifies the
wrong gap each time — then scores it 0.5–0.6. On qwen, agents rarely asked at
all, so this anchor was seldom exercised; gpt-5.4-mini asks more often and hits
it. **This is a judge weakness specific to FAQ on a model that asks.**

## How much it matters — sensitivity check

Treating every GPT FAQ verdict scored 0.5–0.74 as FAIL (a deliberately harsh
bound, since some of those are genuinely borderline):

| gpt-5.4-mini, FAQ | as graded | strict |
|---|---|---|
| LangGraph | 22.5% | 42.5% |
| OpenAI Agents | 42.5% | 50.0% |
| CrewAI | 62.5% | 67.5% |
| LangGraph + CrewAI prompt | 60.0% | 70.0% |
| OpenAI Agents + CrewAI prompt | 67.5% | 72.5% |

| Pooled SR+UT+FAQ, gpt-5.4-mini (Bonferroni ×6) | as graded | strict |
|---|---|---|
| CrewAI worse than LangGraph | 13 / 1, corrected 0.011 | 11 / 2, corrected 0.13 |
| LangGraph + CrewAI prompt worse than LangGraph | 13 / 1, corrected 0.011 | 10 / 1, corrected 0.07 |
| FAQ only: LG + CrewAI prompt vs LG | 12 / 1, p = 0.003 | 9 / 1, p = 0.021 |
| FAQ only: OAI + CrewAI prompt vs OAI | 6 / 0, p = 0.031 | 6 / 0, p = 0.031 |

The leniency falls mostly on the LangGraph baseline (8 of 22 borderline FAQ
passes), so it *inflates* the GPT framework gap.

- **qwen results are unaffected**: every main comparison keeps the same counts
  and significance under strict scoring (e.g. CrewAI vs LangGraph 31 / 1 both
  ways).
- **GPT results keep their direction but lose correction-level significance.**
  The FAQ prompt effect on GPT survives uncorrected under both scorings.

## What the paper should say

Report the GPT (Phase 1d) findings as directional and FAQ-specific, with this
sensitivity analysis alongside; keep the qwen findings as the primary,
fully validated result. A targeted fix — re-judging GPT FAQ runs with the
wrong-gap anchor stated more forcefully — would cost roughly $1.40 but changes
the instrument mid-study; reporting the bound is the cleaner option.
