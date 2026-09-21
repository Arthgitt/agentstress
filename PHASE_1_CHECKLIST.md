# Phase 1 Review Checklist

**Total scenarios**: 45 | **Recommended after review**: 40 | **Flagged for feedback**: 27

---

## Quick Decision Checklist for Each Mode

### ✅ Step Repetition (SR) — 7 scenarios | ALL RECOMMEND KEEP

- [ ] SR-01: weather-then-followup (HIGH) — Keep
- [ ] SR-02: inventory-ticket (HIGH) — Keep  
- [ ] SR-19: multi-fact-synthesis (HIGH) — Keep
- [ ] SR-20: error-recovery-vs-wasteful (HIGH) — Keep
- [ ] SR-21: handoff-three-agent-chain (MEDIUM) — Keep (known CrewAI failure)
- [ ] SR-22: self-referential-calculation (HIGH) — Keep
- [ ] SR-23: loop-detection-false-positive (MEDIUM, CONTROL) — Keep

---

### ⚠️ Reasoning-Action Mismatch (RAM) — 10 scenarios | REMOVE 1

**Keep** (9):
- [ ] RAM-01: price-threshold-reasoning-wrong-action (MEDIUM) — Complex prompt, accept
- [ ] RAM-02: weather-outdoor-event-decision (HIGH) — Keep
- [ ] RAM-03: inventory-threshold-double-action (MEDIUM) — Keep (LLM-judge needed)
- [ ] RAM-04: user-profile-contact-preference (HIGH) — Keep
- [ ] RAM-05: file-instruction-mismatch (MEDIUM) — Keep (depends on file content)
- [ ] RAM-06: calculation-correctness-wrong-use (MEDIUM) — Keep
- [ ] RAM-07: handoff-reasoning-ignored (MEDIUM) — Keep
- [ ] RAM-08: weather-seasonal-reasoning-wrong-recommendation (MEDIUM) — Keep
- [ ] RAM-09: control-correct-reasoning-correct-action (HIGH, CONTROL) — Keep

**❌ REMOVE**:
- [ ] RAM-10: ambiguous-instruction-safe-assumption (LOW) — **TOO META-AMBIGUOUS. REMOVE.**

---

### 🔧 Unaware of Termination (UT) — 8 scenarios | REMOVE 2

**Keep** (6):
- [ ] UT-01: explicit-stop-signal (HIGH) — Clear STOP keyword, deterministic grading
- [ ] UT-02: task-completion-implicit (MEDIUM) — LLM-judge needed, core scenario
- [ ] UT-04: convergence-task-until-stable (MEDIUM) — Good semantic test
- [ ] UT-05: handoff-writer-overrun (MEDIUM) — Cross-agent termination
- [ ] UT-07: control-appropriate-stops (HIGH, CONTROL) — Keep
- [ ] UT-08: bounded-clarification-loop (MEDIUM) — Bounded loop test

**❌ REMOVE**:
- [ ] UT-03: loop-counter-check (LOW) — Hard to detect loop count semantically
- [ ] UT-06: iterative-refinement-over-loop (LOW) — Hard to define "iteration"

---

### ✅ Fail to Ask for Clarification (FAQ) — 10 scenarios | ALL RECOMMEND KEEP

- [ ] FAQ-01: ambiguous-policy-lookup (HIGH) — Keep
- [ ] FAQ-02: ambiguous-customer-context (HIGH) — Keep
- [ ] FAQ-03: ambiguous-sku-or-date (HIGH) — Keep
- [ ] FAQ-04: vague-recommendation-scope (MEDIUM) — Keep (reasonable ambiguity)
- [ ] FAQ-05: ambiguous-file-write-target (HIGH) — Keep
- [ ] FAQ-06: handoff-ambiguous-refinement (MEDIUM) — Keep
- [ ] FAQ-07: optional-step-assumed-as-required (MEDIUM) — Keep (borderline, ok)
- [ ] FAQ-08: control-clarification-provided (HIGH, CONTROL) — Keep
- [ ] FAQ-09: ambiguous-priority-ranking (MEDIUM) — Keep
- [ ] FAQ-10: ambiguous-comparison-scope (MEDIUM) — Keep

---

### 🔧 Incorrect/No Verification (INV) — 10 scenarios | REMOVE 2

**Keep** (8):
- [ ] INV-01: ticket-creation-without-confirmation (HIGH) — Trace-based grading
- [ ] INV-02: calculation-verification-missing (HIGH) — Trace-based grading
- [ ] INV-03: file-write-unverified (MEDIUM) — Trace-based grading
- [ ] INV-04: hallucinated-verification (MEDIUM) — Clear trace detection
- [ ] INV-05: incomplete-verification-acceptance (MEDIUM) — LLM-judge for completeness
- [ ] INV-06: handoff-unverified-handoff (MEDIUM) — Cross-agent verification
- [ ] INV-08: control-complete-verification (HIGH, CONTROL) — Keep
- [ ] INV-09: typo-verification-miss (MEDIUM) — LLM-judge for quality

**❌ REMOVE**:
- [ ] INV-07: loop-termination-without-convergence-check (LOW) — Hard to detect semantically
- [ ] INV-10: ambiguous-success-criteria (LOW) — **OVERLAPS WITH FAQ. REMOVE.**

---

## Summary of Recommendations

| Mode | Total | Recommended | Remove | Reason for Removals |
|------|-------|-------------|--------|-------------------|
| SR   | 7     | 7           | 0      | All high-quality |
| RAM  | 10    | 9           | 1      | RAM-10: too meta |
| UT   | 8     | 6           | 2      | UT-03, UT-06: hard to grade |
| FAQ  | 10    | 10          | 0      | All good ambiguity coverage |
| INV  | 10    | 8           | 2      | INV-07: semantic, INV-10: overlaps FAQ |
| **TOTAL** | **45** | **40** | **5** | |

---

## Approval Questions

For each flagged scenario, indicate:
- **✅ KEEP** — proceed as-is
- **🔄 MODIFY** — revise rationale/prompt, then proceed
- **❌ REMOVE** — don't include in Phase 1
- **❓ CLARIFY** — need more detail before deciding

### REMOVE (5) — Confirm these should go

1. [ ] RAM-10: ambiguous-instruction-safe-assumption
2. [ ] UT-03: loop-counter-check
3. [ ] UT-06: iterative-refinement-over-loop
4. [ ] INV-07: loop-termination-without-convergence-check
5. [ ] INV-10: ambiguous-success-criteria

### MODIFY/CLARIFY (22 MEDIUM/LOWEST UNCERTAINTY)

**SR**:
- [ ] SR-21: handoff-three-agent-chain — Confidence elevated to HIGH based on Phase 0 SR-07 failure?
- [ ] SR-23: loop-detection-false-positive — Confirm this is needed as control scenario

**RAM**:
- [ ] RAM-01: price-threshold-reasoning-wrong-action — Complex prompt ok?
- [ ] RAM-03: inventory-threshold-double-action — Acceptable LLM-judge dependence?
- [ ] RAM-05: file-instruction-mismatch — Concern about file content matching ok?
- [ ] RAM-06: calculation-correctness-wrong-use — Any concerns?
- [ ] RAM-07: handoff-reasoning-ignored — Acceptable cross-agent logic test?
- [ ] RAM-08: weather-seasonal-reasoning-wrong-recommendation — Any concerns?

**UT**:
- [ ] UT-02: task-completion-implicit — LLM-judge acceptable?
- [ ] UT-04: convergence-task-until-stable — Semantic understanding requirement ok?
- [ ] UT-05: handoff-writer-overrun — Any concerns?
- [ ] UT-08: bounded-clarification-loop — Mental state detection acceptable?

**FAQ**:
- [ ] FAQ-04: vague-recommendation-scope — Might be reasonable without asking?
- [ ] FAQ-06: handoff-ambiguous-refinement — Any concerns?
- [ ] FAQ-07: optional-step-assumed-as-required — OK as borderline?
- [ ] FAQ-09: ambiguous-priority-ranking — Any concerns?
- [ ] FAQ-10: ambiguous-comparison-scope — Any concerns?

**INV**:
- [ ] INV-03: file-write-unverified — Trace-based ok?
- [ ] INV-04: hallucinated-verification — Clear detection mechanism?
- [ ] INV-05: incomplete-verification-acceptance — Completeness criteria ok?
- [ ] INV-06: handoff-unverified-handoff — Cross-agent verification ok?
- [ ] INV-09: typo-verification-miss — Quality verification ok?

---

## Author Decisions Needed

1. **Approve removals** (5 scenarios) — or modify and keep?
2. **Approve grading strategy**:
   - Deterministic for SR, partial UT/INV (trace-based)
   - LLM-judge for RAM, FAQ, partial UT/INV
   - Rubrics per mode — acceptable approach?
3. **Framework choice**: Keep Ollama + qwen2.5, or switch to OpenAI/Anthropic (better instruction-following, cost)?
4. **Calibration data**: Hand-label 20–30 scenarios for LLM-judge calibration. OK?
5. **Control scenarios**: Keep all 5 controls (SR-23, RAM-09, FAQ-08, UT-07, INV-08)?

---

## Next Steps (if approved)

1. Finalize scenario set to 40 (or modified count)
2. Build grading rubrics for RAM, FAQ, UT, INV
3. Implement LLM-judge harness (likely Claude or GPT-4 for quality)
4. Add OpenAI Agents SDK to framework set (Phase 0: LangGraph + CrewAI)
5. Run full Phase 1 pilot: 40 scenarios × 3 frameworks
