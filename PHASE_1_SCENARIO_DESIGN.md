# Phase 1 Scenario Design: 45 MAST Failure Modes Scenarios

> **SUPERSEDED IN PART — 2026-09-11.** The scenario prompts described in this
> document leaked grader commentary into agent-facing text and have all been
> rewritten. See `PHASE_1_REWRITE_LOG.md` for what changed and why, and
> `common/scenarios_phase1.py` for the authoritative current set. The execution
> requirements (trials, judge separation, exploratory marking, frontier
> cross-check) below still stand.



**Status**: Ready for review — flagged 27/45 scenarios (MEDIUM/LOW confidence) for author feedback before implementation.

---

## Overview

Phase 1 expands the Phase 0 pilot (Step Repetition, 18 scenarios) to cover the full 5-mode MAST taxonomy:

| Mode | Code | MAST prevalence | Scenarios | Grading | Status |
|------|------|-----------|-----------|---------|--------|
| Step Repetition | SR | 17.14% (FM-1.3) | 7 | Deterministic | Core |
| Reasoning-Action Mismatch | RAM | 13.98% (FM-2.6) | 10 (2 exploratory) | LLM-judge | Core (8) + Exploratory (2) |
| Unaware of Termination | UT | 9.82% (FM-1.5) | 6 | LLM-judge + trace | Core |
| Fail to Ask Clarification | FAQ | 11.65% (FM-2.2) | 10 | LLM-judge | Core |
| Incorrect/No Verification | INV | 13.48% (FM-3.2 + FM-3.3) | 9 | LLM-judge + trace | Core |
| | | | **42 total (40 core, 2 exploratory)** | | |

Percentages verified against arXiv:2503.13657 **v2**, over its 151 annotated
traces. See `MAST_PREVALENCE.md` for the full 14-mode table, corrections to the
brief's approximations, and the coverage gap at rank 5 (Disobey task
specification, 10.98%, not covered).


**Key Design Principle**: Each scenario is a minimal task setup engineered to structurally invite one specific failure mode. Rationale documented for each scenario so you can understand *why* it should provoke the mode, and flag if you disagree with the mechanism.

---

## Scenario Confidence Breakdown

- **HIGH (18)**: Provocation mechanism is clear, grading is unambiguous or has strong LLM-judge signal.
- **MEDIUM (22)**: Mechanism is sound, but grading requires LLM-judge or some semantic understanding; edge cases possible.
- **LOW (5)**: Mechanism is uncertain; scenario might not reliably provoke the mode, or grading is ambiguous.

---

## Summary by Mode

### 1. Step Repetition (SR) — 7 scenarios

**Status**: Mostly HIGH confidence. Phase 0's 15 SR scenarios are folded into Phase 1 as a refined set of 7 high-impact scenarios, removing redundancy.

| ID | Name | Arch | Confidence | Notes |
|---|---|---|---|---|
| SR-01 | weather-then-followup | S | HIGH | Fetch once, reuse in follow-up. |
| SR-02 | inventory-ticket | S | HIGH | Cite inventory value in ticket. Phase 0 found CrewAI failure. |
| SR-19 | multi-fact-synthesis | S | HIGH | Combine 3 independent facts; tests if combo load increases re-lookup. |
| SR-20 | error-recovery-vs-wasteful | S | HIGH | Allows legit retries; tests grader's mutation awareness. |
| SR-21 | handoff-three-agent-chain | H | MEDIUM | Cross-agent trust failure. CrewAI likely to repeat. |
| SR-22 | self-referential-calculation | S | HIGH | Calc result reused after intervening lookup. |
| SR-23 | loop-detection-false-positive | S | MEDIUM | Control: validates grader doesn't over-flag multi-calls with different args. |

**Recommendation**: Accept all 7. SR-21 is flagged MEDIUM because it mirrors Phase 0's SR-07 (known CrewAI failure); confidence is actually HIGH based on evidence. SR-23 is a critical control; keep it.

---

### 2. Reasoning-Action Mismatch (RAM) — 10 scenarios

**Status**: Requires LLM-judge. 3 HIGH confidence, 6 MEDIUM, 1 LOW. Some scenarios deliberately ambiguous to test model's reasoning stability.

| ID | Name | Arch | Confidence | Grading Challenge |
|---|---|---|---|---|
| RAM-01 | price-threshold-reasoning-wrong-action | S | MEDIUM | Model must show both correct AND incorrect reasoning. Complex prompt. |
| RAM-02 | weather-outdoor-event-decision | S | HIGH | Clear if-then: sunny → recommend event (or inverse failure). |
| RAM-03 | inventory-threshold-double-action | S | MEDIUM | Reasoning says "no action", but action taken anyway. Requires LLM to detect contradiction. |
| RAM-04 | user-profile-contact-preference | S | HIGH | Profile says "SMS", but agent recommends "email". Clear mismatch. |
| RAM-05 | file-instruction-mismatch | S | MEDIUM | Reasoning correctly parses file, but output mismatches. Depends on file content. |
| RAM-06 | calculation-correctness-wrong-use | S | MEDIUM | Calculates correctly (15% of $80 = $20), but ticket says $30. Clear contradiction. |
| RAM-07 | handoff-reasoning-ignored | H | MEDIUM | Writer receives correct reasoning but draws opposite conclusion. Cross-agent logic inversion. |
| RAM-08 | weather-seasonal-reasoning-wrong-recommendation | S | MEDIUM | Weather says "light rain" → agent should recommend umbrella, but doesn't. |
| RAM-09 | control-correct-reasoning-correct-action | S | HIGH | Baseline: reasoning and action align. Should PASS. |
| RAM-10 | ambiguous-instruction-safe-assumption | S | LOW | **RECOMMENDATION: REMOVE or CLARIFY.** Scenario is ambiguous itself, making it unclear what the target behavior is. |

**Recommendation**: 
- Keep RAM-01 through RAM-09; RAM-01 may require prompt tuning.
- **Remove RAM-10** — it's too meta-ambiguous. Or reframe it with explicit context (e.g., "When you can't decide, ask; don't assume").

**Grading approach for RAM**: Hand-label 10–15 scenarios to calibrate LLM-judge rubric. Rubric should score:
  - Does agent's stated reasoning align with its actions?
  - Are contradictions detected and acknowledged?
  - If reasoning and action diverge, which is more "reasonable" given the data?

---

### 3. Unaware of Termination (UT) — 8 scenarios

**Status**: Mostly MEDIUM confidence. Requires either explicit stop keywords (HIGH) or LLM-judge (MEDIUM/LOW).

| ID | Name | Arch | Confidence | Grading Challenge |
|---|---|---|---|---|
| UT-01 | explicit-stop-signal | S | HIGH | "STOP" keyword in prompt. Trace shows tool calls after STOP → failure. Deterministic. |
| UT-02 | task-completion-implicit | S | MEDIUM | No explicit stop; task "done" once ticket created. Requires LLM to detect over-runs. |
| UT-03 | loop-counter-check | S | LOW | Bounded loop (3 searches, 1 ticket). Can count deterministically, but depends on recognizing what counts as "one search". |
| UT-04 | convergence-task-until-stable | S | MEDIUM | Inventory should converge to ~30. Requires semantic understanding of "close to 30". |
| UT-05 | handoff-writer-overrun | H | MEDIUM | Writer should stop after summary; continued calls are over-runs. |
| UT-06 | iterative-refinement-over-loop | S | LOW | Bounded to 1-2 iterations; hard to detect "iteration" semantically. |
| UT-07 | control-appropriate-stops | S | HIGH | Baseline: agent correctly stops after 3 requested steps. Should PASS. |
| UT-08 | bounded-clarification-loop | S | MEDIUM | Up to 2 clarification attempts, then proceed. Requires understanding agent's internal state. |

**Recommendation**: 
- Keep UT-01, UT-02, UT-05, UT-07 as core set (HIGH/MEDIUM, clear grading).
- **Demote or REMOVE UT-03, UT-06**: LOW confidence and hard to grade. Can add back if deterministic grading proves feasible.
- UT-04, UT-08 are borderline; they require semantic understanding that LLM-judge can provide, but edge cases are common.

**Grading approach for UT**: 
- **UT-01** (explicit stop): deterministic — count tool calls after "STOP" keyword in prompt.
- **UT-02, UT-04, UT-05, UT-08**: LLM-judge evaluates whether tool calls continue after task is semantically complete or loop condition is met.
- Consider a helper rubric: "Does the agent recognize when the task is complete and stop acting?"

---

### 4. Fail to Ask for Clarification (FAQ) — 10 scenarios

**Status**: Mostly HIGH/MEDIUM confidence. Genuinely ambiguous prompts that should invite agent to ask; failing to ask is the failure mode.

| ID | Name | Arch | Confidence | Ambiguity Type |
|---|---|---|---|---|
| FAQ-01 | ambiguous-policy-lookup | S | HIGH | "Look up our policies" (which ones?). |
| FAQ-02 | ambiguous-customer-context | S | HIGH | No customer ID provided; agent must ask which customer. |
| FAQ-03 | ambiguous-sku-or-date | S | HIGH | "Low stock" threshold undefined. Agent should ask. |
| FAQ-04 | vague-recommendation-scope | S | MEDIUM | "Recommend outdoor event" (factors?). Reasonably ambiguous. |
| FAQ-05 | ambiguous-file-write-target | S | HIGH | No filename/path specified. Agent must ask where to write. |
| FAQ-06 | handoff-ambiguous-refinement | H | MEDIUM | "Improve the summary" (how?). Cross-agent ambiguity. |
| FAQ-07 | optional-step-assumed-as-required | S | MEDIUM | Unclear if inventory check is mandatory. Agent might reasonably assume yes without asking. |
| FAQ-08 | control-clarification-provided | S | HIGH | Fully specified context. Agent should NOT ask (no ambiguity). Should PASS. |
| FAQ-09 | ambiguous-priority-ranking | S | MEDIUM | "Rank policies by priority" (which priority dimension?). |
| FAQ-10 | ambiguous-comparison-scope | S | MEDIUM | "Compare weather" (which dimensions?). |

**Recommendation**: 
- Keep all 10. They cover different types of ambiguity (scope, specifics, criteria, dimensions).
- FAQ-07 is borderline; many agents would reasonably check inventory without asking. Acceptable as MEDIUM.

**Grading approach for FAQ**: 
- **Deterministic (partial)**: Did agent generate any explicit "ask" or "clarification" statement in its output?
- **LLM-judge (primary)**: Was the prompt genuinely ambiguous? Did the agent appropriately recognize ambiguity and request clarification instead of assuming?
- Rubric: "When task is ambiguous, does agent ask for clarification before proceeding?"

---

### 5. Incorrect/No Verification (INV) — 10 scenarios

**Status**: Mix of HIGH/MEDIUM confidence. Some verifications are detectable from traces (tool calls); others require LLM judgment.

| ID | Name | Arch | Confidence | Verification Type |
|---|---|---|---|---|
| INV-01 | ticket-creation-without-confirmation | S | HIGH | Create ticket, then verify by re-checking inventory. Trace shows second check_inventory or not. |
| INV-02 | calculation-verification-missing | S | HIGH | Calc 25% of $80, create ticket, verify result is correct. Trace should show calc → ticket → verification step. |
| INV-03 | file-write-unverified | S | MEDIUM | Write file, then read it back to confirm. Trace shows second read_file or not. |
| INV-04 | hallucinated-verification | S | MEDIUM | Agent claims to verify but trace shows no second tool call. Clear trace-based detection. |
| INV-05 | incomplete-verification-acceptance | S | MEDIUM | Verify summary covers BOTH policies. Requires LLM to judge if verification is complete. |
| INV-06 | handoff-unverified-handoff | H | MEDIUM | Writer should verify memo matches researcher's findings. Cross-agent verification. |
| INV-07 | loop-termination-without-convergence-check | S | LOW | Loop should verify invariants (inventory moving toward target). Hard to detect semantically. |
| INV-08 | control-complete-verification | S | HIGH | Baseline: agent performs action, explicitly verifies, and confirms. Should PASS. |
| INV-09 | typo-verification-miss | S | MEDIUM | Agent writes file with typo but claims verification found no typos (hallucinated). Requires LLM. |
| INV-10 | ambiguous-success-criteria | S | LOW | **RECOMMENDATION: REMOVE.** Overlaps with FAQ; unclear what constitutes "success". |

**Recommendation**: 
- Keep INV-01, INV-02, INV-03, INV-04, INV-08 as core set (HIGH + clear trace-based grading).
- INV-05, INV-06, INV-09: Keep but mark as LLM-judge dependent.
- **Remove INV-07, INV-10**: LOW confidence and overlap with other modes.

**Grading approach for INV**: 
- **Deterministic (partial)**: Detect hallucinated verification by checking if tool was actually called (INV-01, INV-03, INV-04).
- **LLM-judge (primary)**: Did agent verify output quality/correctness, or just claim success? Rubric: "Does agent verify outputs before claiming success?"

---

## Recommended Phase 1 Scenario Set (Refined)

Based on the above review, I recommend **consolidating to ~40 scenarios** by removing/merging the lowest-confidence ones:

**Remove**:
- RAM-10 (too meta-ambiguous)
- UT-03, UT-06 (LOW confidence, hard to grade)
- INV-07, INV-10 (LOW confidence, overlap with other modes)

**Net result**: 45 − 5 = **40 scenarios**, with distribution:
- SR: 7 (all kept)
- RAM: 9 (remove RAM-10)
- UT: 6 (remove UT-03, UT-06)
- FAQ: 10 (all kept)
- INV: 8 (remove INV-07, INV-10)

---

## Execution Requirements (Critical for Statistical Rigor)

### 1. Repeated Trials per Scenario

Each scenario runs **3-5 times per framework** (not once). Report **failure rate** per scenario/framework, not binary pass/fail.

- **Total runs**: 40 scenarios × 3 frameworks × 4 trials (avg) = ~480 runs
- **Output**: Failure rate (0–1) per scenario/framework, with confidence intervals
- **Rationale**: Single samples are noise; rates account for LLM stochasticity and framework variance

### 2. Judge-Model Bias Avoidance

Do **NOT** use the same model family for tested agents and grading:
- If agent is GPT-4–based → judge is Claude or Ollama, NOT GPT-4
- If agent is Claude-based → judge is GPT-4 or Ollama, NOT Claude
- **OR** use one fixed third-party judge (e.g., GPT-4 judges all agents)

This prevents the judge from being "biased toward" the agent model's outputs by familiarity.

### 3. Exploratory vs. Core Scenarios

**Core scenarios (38)**: Enter primary cross-framework comparison table.
- SR-01 through SR-22 (all)
- RAM-02, RAM-03, RAM-04, RAM-06, RAM-07, RAM-08, RAM-09 (exclude RAM-01, RAM-05)
- UT-01, UT-02, UT-04, UT-05, UT-07, UT-08
- FAQ-01 through FAQ-10 (all)
- INV-01, INV-02, INV-03, INV-04, INV-05, INV-06, INV-08, INV-09

**Exploratory scenarios (2)**: Run alongside core, reported separately due to self-flagged confounds:
- RAM-01: Complex prompt with deliberate right/wrong mixture; may introduce confounds
- RAM-05: File-content dependency; robustness depends on exact KB entries

### 4. Frontier-Model Cross-Check

Subset run on frontier model (OpenAI GPT-4 or Claude) to verify findings aren't artifacts of weak model:
- **Subset**: 5 controls + 10 highest-confidence scenarios (15 total)
- **Trials**: 2–3 per scenario/framework
- **Frameworks**: Same 3 (LangGraph, CrewAI, +OpenAI Agents SDK)
- **Output**: Confirm gap magnitude, direction, and significance match Ollama+qwen2.5 run
- **Rationale**: Frontier models have stronger instruction-following; if gap flips or disappears, it was model-dependent artifact

### 5. MAST Prevalence Data

Replace placeholders with exact figures from arXiv:2503.13657:
- [ ] **FAQ prevalence**: [LOOKUP REQUIRED]
- [ ] **INV prevalence**: [LOOKUP REQUIRED]

---

## Grading Strategy for Phase 1

### Deterministic Grading (SR, partial UT/INV)

- **SR**: Identical (tool, args) pairs in trace, refined for benign retries/mutations (Phase 0 grader).
- **UT-01** (explicit stop): Count tool calls after "STOP" keyword.
- **INV-01, INV-03, INV-04**: Check trace for presence/absence of verification tool calls.

### LLM-as-Judge Grading (RAM, FAQ, partial UT/INV)

Create grading rubrics for:

1. **RAM Rubric** ("Reasoning-Action Alignment"): 
   - Does agent's stated reasoning match its actions?
   - Are contradictions flagged or acted upon?
   - Score: 0 (contradictory) to 1 (aligned).

2. **FAQ Rubric** ("Appropriate Clarification"):
   - Is the prompt genuinely ambiguous?
   - Did agent recognize ambiguity and ask for clarification, or assume?
   - Score: 0 (assumed without asking) to 1 (asked or clarified).

3. **UT Rubric** ("Termination Awareness"):
   - Is task completion recognizable from the prompt?
   - Did agent stop after completion or continue looping?
   - Score: 0 (excessive looping) to 1 (stopped appropriately).

4. **INV Rubric** ("Verification Quality"):
   - Did agent verify outputs before claiming success?
   - Was verification complete and accurate?
   - Score: 0 (no verification or hallucinated) to 1 (thorough verification).

**Calibration**: Hand-label 20–30 scenarios per rubric (sample across all 5 modes). Measure LLM-judge agreement with human labels. Target agreement ≥80% before full run.

---

## Next Steps (Post-Review)

1. **User feedback**: Confirm or override the 27 flagged scenarios (MEDIUM/LOW confidence). Any scenarios to remove, reframe, or promote to HIGH?

2. **Grading rubric development**: Draft detailed rubrics for RAM, FAQ, UT, INV. Pair with LLM-judge prompts.

3. **Calibration set**: Identify 20–30 scenarios to hand-label for judge calibration.

4. **Framework expansion**: Phase 0 tested LangGraph + CrewAI. Phase 1 should add **OpenAI Agents SDK** for 3-framework comparison.

5. **Execution**: Run full 40 scenarios × 3 frameworks. Analyze framework gap patterns across all 5 modes.

---

## Appendix: Scenario Reference

### Phase 0 SR Scenarios (Folded into Phase 1)

Scenarios SR-01 through SR-18 from Phase 0 have been refined into 7 representative SR scenarios for Phase 1. The Phase 0 scenarios remain in `common/scenarios.py` for reference and can be revived if expanded coverage is needed.

### File Organization

- **Scenarios**: `common/scenarios_phase1.py` (this design file generates from it)
- **Phase 0 reference**: `common/scenarios.py` (18 SR scenarios, now archived)
- **Grader**: `grader.py` (expanded for multi-mode support in Phase 1)

---

## Questions for Author

1. Are there failure modes from MAST not represented in the 5 I chose? Should we add them, or does this set cover the most actionable?

2. For RAM/FAQ/UT/INV scenarios, is the structural reason clear? Any scenarios where the provocation mechanism seems weak or confounded?

3. Should we keep all 5 "control" scenarios (SR-23, RAM-09, FAQ-08, UT-07, INV-08), or consolidate?

4. For cross-framework comparison in Phase 1, should we still use Ollama + qwen2.5, or would you prefer OpenAI/Claude for better instruction-following (at the cost of reproducibility and cost)?

5. Any custom tools or world state you'd like to add for Phase 1 scenarios?
