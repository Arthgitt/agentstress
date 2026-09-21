# Phase 1b Status: Calibration Infrastructure Complete ✅

**Date**: 2026-08-24  
**Status**: Ready for calibration set selection & hand-labeling  
**Next**: Phase 1b Step 2 (Calibration data preparation)

---

## Completed in Phase 1b Step 1

### 1. Grading Rubrics (All 4 modes)

✅ **RAM Rubric** (`grading/ram_rubric.md`)
- Scoring scale: 0 (strongly contradictory) → 1 (fully aligned)
- 3 calibration examples (price-threshold, user-profile, calculation)
- Judge prompt ready for Claude integration

✅ **FAQ Rubric** (`grading/faq_rubric.md`)
- Scoring scale: 0 (no clarification) → 1 (appropriate clarification)
- 3 calibration examples (policy-lookup, customer-context, file-write)
- Judge prompt ready for Claude integration

✅ **UT Rubric** (`grading/ut_rubric.md`)
- Scoring scale: 0 (excessive looping) → 1 (appropriate stopping)
- 3 calibration examples (explicit-stop, implicit-completion, convergence)
- Judge prompt ready for Claude integration

✅ **INV Rubric** (`grading/inv_rubric.md`)
- Scoring scale: 0 (no/hallucinated verification) → 1 (thorough verification)
- 2-track evaluation: deterministic (trace-based) + semantic (LLM-judge)
- 3 calibration examples (ticket-creation, calculation, incomplete-verification)
- Judge prompt ready for Claude integration

### 2. Claude Judge Harness (`grading/claude_judge.py`)

✅ **Complete implementation** with functions:
- `judge_ram()`: Evaluate Reasoning-Action Mismatch
- `judge_faq()`: Evaluate Fail to Ask for Clarification
- `judge_ut()`: Evaluate Unaware of Termination
- `judge_inv()`: Evaluate Incorrect/No Verification
- `judge_scenario()`: Dispatch router

✅ **Features**:
- Uses Anthropic Claude (Opus 5) as judge model
- Automatic JSON response parsing with fallback
- Token counting for budget tracking
- Structured `JudgeResult` TypedDict output

✅ **API Setup**: Ready to use with `ANTHROPIC_API_KEY` env var

---

## MAST Prevalence Data (Partial)

**Sourced from arXiv:2503.13657 via web search**:

| Category | Prevalence |
|----------|-----------|
| Task Verification (category) | 23.5% |
|   - No or Incomplete Verification (INV) | 6.8% |
|   - Incorrect Verification (INV) | 7.4% |
| System Design Issues (category) | 44.2% |
| Inter-Agent Misalignment (category) | 32.3% |
|   - Fail to Ask for Clarification (FAQ) | [Subset of 32.3%, exact % TBD] |

**Status**: INV prevalence confirmed at ~14.2% (6.8% + 7.4%). FAQ likely 5–15% within Inter-Agent Misalignment category, exact figure pending full paper review.

---

## Next: Phase 1b Step 2 — Calibration Set Selection

### What to Do

**Select 20–30 scenarios for hand-labeling** (these will ground-truth the judge):

**Core strategy**:
1. Include all 5 controls (SR-23, RAM-09, FAQ-08, UT-07, INV-08) — should be easy/clear
2. Sample 5–6 HIGH confidence scenarios per mode (if available)
3. Sample MEDIUM confidence scenarios for edge cases
4. Ensure all 4 grading modes represented (RAM, FAQ, UT, INV)
5. Keep deterministic modes (SR) out of LLM-judge calibration

**Recommendation for you to approve**:

| Mode | Controls | HIGH | MEDIUM | Total | Rationale |
|------|----------|------|--------|-------|-----------|
| RAM | RAM-09 | RAM-02, RAM-04 | RAM-03, RAM-06, RAM-07 | 6 | 2 for confidence, 3 for edge cases |
| FAQ | FAQ-08 | FAQ-01, FAQ-02, FAQ-03, FAQ-05 | FAQ-04, FAQ-09 | 7 | All HIGH + sample of MEDIUM |
| UT | UT-07 | UT-01 | UT-02, UT-04, UT-05 | 5 | One HIGH, three MEDIUM for semantic challenges |
| INV | INV-08 | INV-01, INV-02 | INV-03, INV-04, INV-05, INV-06 | 8 | Mix of trace-based + semantic |
| **TOTAL** | **5** | **11** | **11** | **27** | |

### Hand-Labeling Process

Once calibration set is approved:

1. **Run each calibration scenario 1 time** against LangGraph only (reduce cost)
   - Execute scenario → get agent output + trace
   - Save to `results/calibration_data/{scenario_id}_langgraph_trial1.json`

2. **Human (you) labels each scenario**
   - Read the scenario prompt, agent output, tool trace
   - Assign score (0–1) per rubric
   - Record in `results/calibration_labels.json`:
     ```json
     {
       "scenario_id": "RAM-02",
       "human_score": 0.9,
       "human_reasoning": "Agent reasons correctly about user preference (SMS) and recommends SMS contact. Reasoning and action aligned.",
       "human_verdict": "PASS"
     }
     ```

3. **Judge labels each scenario**
   - Run Claude judge on same scenario
   - Compare: human score vs. judge score
   - Calculate inter-rater agreement (target ≥80% or Krippendorff's α ≥0.7)

4. **Iterate if needed**
   - If agreement < 80%: Review rubric wording, adjust judge prompts, re-run subset
   - Document any systematic biases (judge over/under-scores specific mode)

---

## Files Ready for Phase 1b Step 2

```
/Users/arthpatel/Desktop/stress-test-tool/
├── grading/
│   ├── ram_rubric.md          ← Calibration examples included
│   ├── faq_rubric.md
│   ├── ut_rubric.md
│   ├── inv_rubric.md
│   └── claude_judge.py        ← Ready to import and use
├── results/
│   └── calibration_data/      ← Will hold scenario outputs for labeling
└── PHASE_1_EXECUTION_PLAN.md  ← Step 2 detailed in § 2.1–2.2
```

---

## Decisions Needed from You

1. **Approve calibration subset** (27 scenarios listed above)? Or modify?
2. **Hand-labeling approach**: Will you label yourself, or prefer I guide a different labeler?
3. **Timeline**: When can calibration labels be ready? (Estimate: 2–3 hours for 27 scenarios at ~5 min each)
4. **Judge re-tuning**: If agreement < 80%, acceptable to iterate rubrics + judge prompts?

---

## Budget Impact

- **Calibration runs**: 27 scenarios × 1 trial = 27 runs on LangGraph (Ollama: free)
- **Judge API calls**: 27 scenarios × 4 modes max = ~108 API calls (Claude Opus 5)
  - ~500 tokens per call → ~54k tokens
  - Cost: ~$0.27 (input) + ~$0.27 (output) ≈ **$0.54 for calibration**

---

## Once Calibration is Done

Move to **Phase 1c: Main Run**
- 38 core scenarios × 3 frameworks × 4 trials = 456 runs
- Judge grades ~200 of them (RAM, FAQ, UT, INV scenarios; SR is deterministic)
- Total: ~$5–10 in judge API costs

---

## Quick Reference: Judge Usage

```python
from grading.claude_judge import judge_scenario

result = judge_scenario(
    scenario_id="RAM-02",
    target_mode="RAM",
    framework="langgraph",
    agent_output="Agent output text...",
    prompt="Original task prompt...",
    tool_calls=[...]  # Required for UT, INV
)

print(f"Score: {result['score']}")      # 0.0–1.0
print(f"Verdict: {result['verdict']}")  # "PASS" or "FAIL"
print(f"Reasoning: {result['reasoning']}")
```

---

## Status Summary

| Component | Status | Notes |
|-----------|--------|-------|
| RAM Rubric | ✅ Done | 3 examples, judge prompt ready |
| FAQ Rubric | ✅ Done | 3 examples, judge prompt ready |
| UT Rubric | ✅ Done | 3 examples, judge prompt ready |
| INV Rubric | ✅ Done | 3 examples, 2-track grading, judge prompt ready |
| Claude Judge Harness | ✅ Done | All 4 modes implemented, tested |
| MAST Data | ⚠️ Partial | INV confirmed, FAQ in progress |
| Calibration Set | ⏳ Pending | Awaiting your approval (27 scenarios proposed) |
| Hand-Labeling | ⏳ Pending | Awaiting calibration set approval + your labels |
| Judge Calibration | ⏳ Pending | Awaiting calibration labels |

---

**Ready to move to Phase 1b Step 2?** Confirm the calibration subset above, and we'll prepare the scenarios for labeling.
