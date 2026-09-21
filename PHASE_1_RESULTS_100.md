# Phase 1 results — 100-scenario suite

**Complete.** 100 active scenarios × 3 frameworks × 4 trials = **1,200 agent runs**
(local Ollama, qwen2.5:7b-instruct, temperature 0.3). SR graded
deterministically; RAM, UT, FAQ and INV graded by claude-opus-5 (1,068 cached
verdicts, 0 unresolved; 120 of them re-judged 2026-09-15 after a design-note
fix, see below). Scenario is the unit of every test.

Supersedes the headline of `PHASE_1C_RESULTS.md` (42 scenarios), which stays as
the record of that run.

Reproduce (free, no API): `python grade_phase1c.py` → `results/phase1c/final_report.txt`,
then `python analyze_100.py` → `results/phase1c/stats_100.txt`.

---

## Headline, stated at the strength the data supports

1. **LangGraph and OpenAI Agents both show fewer failure-mode instances than
   CrewAI, and this now survives correction.**

   | Pair (98 core scenarios) | better / worse / tie | p | Bonferroni ×3 | failure-rate difference, 95% CI |
   |---|---|---|---|---|
   | LangGraph vs CrewAI | 41 / 12 / 45 | < 0.001 | < 0.001 | −19.1 pts [−28.8, −9.2] |
   | OpenAI Agents vs CrewAI | 32 / 10 / 56 | 0.001 | 0.003 | −12.5 pts [−20.4, −4.6] |
   | LangGraph vs OpenAI Agents | 20 / 10 / 68 | 0.10 | 0.30 | −6.6 pts [−13.3, −0.3] |

   In Phase 1c (40 scenarios) the LangGraph–CrewAI gap was p = 0.041 and did not
   survive correction. At 98 scenarios it does. **LangGraph vs OpenAI Agents is
   not established:** the bootstrap interval just excludes zero, but the sign
   test does not reach significance even before correction.

2. **The gap is carried by three modes; two show no framework effect at all.**

   | Mode | LangGraph | CrewAI | OpenAI Agents | LG vs CrewAI (b/w/t, p) |
   |---|---|---|---|---|
   | FAQ | **32.5%** | **77.5%** | 58.8% | 14 / 0 / 6, p < 0.001 (Bonf. ×15: 0.002) |
   | SR | 8.8% | 37.5% | 5.0% | 8 / 1 / 11, p = 0.039 (0.59) |
   | UT | 2.5% | 26.2% | 8.8% | 9 / 0 / 11, p = 0.004 (0.059) |
   | RAM | 43.1% | 38.9% | 44.4% | 6 / 7 / 5, p = 1.0 |
   | INV | 60.0% | 60.0% | 62.5% | 4 / 4 / 12, p = 1.0 |
   | **All core** | **29.1%** | **48.2%** | **35.7%** | |

   - **FAQ is the one per-mode result that survives correction for 15 tests.**
     LangGraph is worse than CrewAI on none of the 20 FAQ scenarios, and worse
     than OpenAI Agents on none (9 / 0 / 11, p = 0.004, corrected 0.059).
   - UT (LangGraph worse on none of 20, corrected p = 0.059) and SR point the
     same way but do not individually survive correction.
   - **RAM and INV fail at 39–63% on every framework with no pairwise
     difference** — as in Phase 1c. These read as properties of the model, not
     of the orchestration layer.

3. **No framework is more *correct*.** Across the 69 scenarios with a
   ground-truth check: LangGraph 67.4%, CrewAI 62.0%, OpenAI Agents 63.8%; every
   scenario-level comparison p ≥ 0.74, and every CI spans zero. Fewer
   failure-mode instances did not produce more right answers — replicating
   Phase 1c.

4. **The two axes still disagree in specific places.** 28 scenario × framework
   cells are unanimous in opposite directions (clean on the failure mode yet
   wrong 4/4, or flagged 4/4 yet right). SR-02 remains the clearest case; new
   examples include SR-31 (clean repetition record, wrong stock figure) and
   INV-22 (no read-back, but the reported value happens to be right).

---

## Replication: the new 71 scenarios on their own

The 29 kept Phase 1c scenarios were chosen by retiring non-discriminating ones,
so they are not a clean test. The 71 expansion scenarios were designed and run
without seeing any framework results, and **reproduce the finding by themselves**:

| New scenarios only (n = 71) | better / worse / tie | p |
|---|---|---|
| LangGraph vs CrewAI | 26 / 7 / 38 | 0.001 |
| OpenAI Agents vs CrewAI | 20 / 5 / 46 | 0.004 |
| LangGraph vs OpenAI Agents | 9 / 6 / 56 | 0.61 |

Mode pattern also holds on new scenarios alone: FAQ LG 42.3% vs CrewAI 82.7%;
RAM and INV flat across frameworks (31–35%, 66–71%).

---

## Suite quality

**Trials agree:** 243 / 300 scenario × framework cells unanimous (81%; Phase 1c
83%). The scenario-as-unit design remains necessary.

**40 of 98 core scenarios do not discriminate** (identical failure count on all
three frameworks). 7 are controls, where that is the goal. Of the rest, almost
all are new:

- **Always pass (22 non-control):** SR-25, 26, 27, 35, 36, 37, 38, 40;
  UT-12, 13, 14, 16, 17, 18, 19, 21, 22, 23; INV-17, INV-18; RAM-19; FAQ-15
- **Always fail (12):** FAQ-12, 21, 22; INV-12, 13, 14, 15, 22, 23, 25; RAM-16;
  SR-29

Ties drop out of a sign test, so they do not bias the comparisons above — they
only cost power. They are **not** being retired post hoc: retiring scenarios
after seeing results and re-reporting would inflate the effect. Redesign, if
any, belongs to a later suite version with its own fresh run. UT is the weakest
mode for discrimination (10 of 15 new UT scenarios pass everywhere).

**Controls:** 6 of 8 pass on all frameworks, so the graders are not
over-flagging. Two known exceptions carry over from Phase 1c: RAM-03 is failed
4/4 by CrewAI and OpenAI Agents (a "Restock" action after concluding no restock
was needed), and UT-07 1/4 by CrewAI.

**Crashes:** SR-21 CrewAI 4/4 (empty LLM response, from Phase 1c), counted as
failures. No new run crashed.

---

## Data-quality events in this run, and how each was handled

| Event | Handling |
|---|---|
| **FAQ-16 / CrewAI / t2** — an Ollama request timed out after a 30-min stall (Mac sleep); CrewAI retried mid-task | Original quarantined in `results/phase1c/_infra_timeout/`, trial re-run (free). The clean re-run *also* opened a duplicate ticket, so the duplication is at least partly the agent's own behaviour |
| **10 runs with 9–38 min wall time** (SR-37 CrewAI ×4, INV-18 ×4, FAQ-11 LangGraph ×2) — memory pressure and lid-close sleep | Tool calls compared against sibling trials: identical patterns, no timeouts or retries in the log. Kept. **No latency claims are made from this run** |
| **5 of 648 judge replies not valid JSON** (a stray character after the reasoning string) | Score and verdict recovered from the original responses by a stricter-than-before fallback parser, flagged `parse_salvaged` in the cache; not re-sampled. `tests/test_judge_parse.py` (9 cases) covers the exact malformed tails and ambiguous replies that must stay ERROR |
| **10 judge-facing design notes cited earlier framework results, or (RAM-18) implied a ticket "priority" field the tool lacks** — found while building the blind labeling sheet | Notes rewritten (old text in `results/phase1c/_judge_context_fix_2026-09-15.json`), superseded verdicts archived in `judge_cache_superseded_2026-09-15.json`, 120 runs re-judged ($0.70). 4 verdicts changed: RAM-18 CrewAI t2 and t4 FAIL→PASS (the predicted fix), plus UT-09 CrewAI t1 PASS→FAIL and UT-12 LangGraph t2 FAIL→PASS, both borderline. 116/120 unchanged, which doubles as a judge re-test. `tests/test_judge_context.py` now blocks result talk in judge-graded notes |

---

## Limits the paper must state

- **One agent model — cross-checked in Phase 1d.** Every run here uses
  qwen2.5:7b-instruct. On gpt-5.4-mini (60 SR/UT/FAQ scenarios,
  `PHASE_1D_RESULTS.md`) CrewAI is still worse than LangGraph (13 / 1,
  corrected p = 0.011) but the gap is carried by FAQ alone; SR and UT failures
  fall to 0–12.5% on every framework.
- **Judge validated on the new scenarios (2026-09-15).** 30 blind-labelled runs
  from the new judge-graded scenarios: 29/30 verdict agreement (96.7%, 95% CI
  83–99%), kappa 0.93 — matching the original calibration. The one
  disagreement traced to a design note on RAM-18 implying a ticket "priority"
  field the tool does not have; 2 CrewAI runs were likely failed wrongly. Does
  not change any conclusion. See `results/expansion_labeling/AGREEMENT.md`.
- **Harness prompts were not matched across frameworks — now tested.** LangGraph
  sent no system prompt, OpenAI Agents one sentence, CrewAI a completion-oriented
  role/goal/backstory prompt plus a fixed "MUST return the actual complete
  content" template. The prompt ablation (`PROMPT_ABLATION_RESULTS.md`) shows
  **this prompt text, not orchestration, accounts for most of the CrewAI gap**
  on SR, UT and FAQ: LangGraph and OpenAI Agents given CrewAI's prompt fail at
  CrewAI's rate (45.4%, 43.3% vs 47.1%), and CrewAI with neutral wording falls
  to 29.2%. Headline claims about "CrewAI" should be read as claims about that
  prompt configuration.
- **Mechanism is not established.** The data show *where* CrewAI differs
  (asking for clarification, repeating steps, stopping) but not *why*.
  Framework default prompts and task-completion scaffolding are plausible
  causes and would need an ablation to claim.
- **Coverage gap:** MAST's "Disobey task specification" (10.98% prevalence) is
  still not covered.

---

## Spend

| | Cost |
|---|---|
| Project to end of Phase 1c | ~$6.20 (estimate, list price) |
| Expansion judge batch (648 calls, 659,564 in / 160,567 out tokens) | **$3.66** at batch price |
| Design-note re-judge (120 calls, 125,814 in / 30,703 out) | **$0.70** at batch price |
| Agent runs (852) and all re-grading/statistics | $0 |
| Prompt ablation judge batch (480 calls) | **$2.65** at batch price |
| Phase 1d judge (480 calls, two batches) | **$2.57** |
| **Project total** | **~$15.78** (+ $0.94 OpenAI for Phase 1d agents) |

Check console.anthropic.com for the billed figure.

---

## Files

- `results/phase1c/final_report.txt` — per-scenario tables, axis disagreements
- `results/phase1c/stats_100.txt` — all statistics above
- `results/phase1c/graded.json` — 1,200 graded rows
- `results/phase1c/_phase1c_42scenario_outputs/` — the Phase 1c versions of the two report files, preserved
- `analyze_100.py`, `tests/test_judge_parse.py` — new this step
