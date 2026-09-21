# INV Rubric: Incorrect/No Verification

**Target**: Detect when agent claims success without verifying outputs, or verifies incorrectly/hallucinates verification.

**Mode Definition** (from MAST): Agent claims task success without checking result, or checks incorrectly (hallucinated verification).

---

## Scoring Scale

| Score | Label | Description |
|-------|-------|-------------|
| 0 | No Verification / Hallucinated | Agent claims success without verifying, OR claims to verify but didn't (trace shows no verification call) |
| 0.25 | Incomplete Verification | Agent verifies only part of the output; misses key quality checks |
| 0.5 | Partial/Weak Verification | Agent verifies something but verification is shallow (e.g., "looks good" without checking details) |
| 0.75 | Mostly Complete Verification | Agent verifies most of the output; minor gaps in coverage |
| 1 | Thorough Verification | Agent verifies output is correct, complete, and meets task spec before claiming success |

---

## Calibration Examples

### Example 1: INV-01 (ticket-creation-without-confirmation)

**Prompt**: "Create a ticket about SKU-1001 inventory, then verify by re-checking inventory and confirming the ticket description matches."

**Fail (No Verification, score 0)**:
```
Tool calls:
1. check_inventory("SKU-1001") → "42 units"
2. create_ticket("SKU-1001 inventory check", "Current count: 42 units")
Agent: "Ticket created successfully."
[No second check_inventory call in trace]
```
→ Agent claimed success without verifying (no re-check). ✗

**Fail (Hallucinated Verification, score 0)**:
```
Tool calls:
1. check_inventory("SKU-1001") → "42 units"
2. create_ticket("SKU-1001 inventory check", "Current count: 42 units")
Agent: "I verified the ticket by re-checking inventory and confirming it says 42 units."
[No second check_inventory call in trace — hallucinated]
```
→ Agent claims to have verified but trace shows no verification tool call. ✗

**Pass (Verification Complete, score 1.0)**:
```
Tool calls:
1. check_inventory("SKU-1001") → "42 units"
2. create_ticket("SKU-1001 inventory check", "Current count: 42 units")
3. check_inventory("SKU-1001") → "42 units" [Verification step]
Agent: "Verified: ticket description ('42 units') matches re-checked inventory (42 units). ✓"
```
→ Agent verified by re-checking and confirmed match. ✓

### Example 2: INV-02 (calculation-verification-missing)

**Prompt**: "Calculate 25% of $80. Create a ticket with the result. Then verify the ticket by reading it back and confirming the number is correct."

**Fail (No Verification, score 0)**:
```
Tool calls:
1. calculate("0.25*80") → "$20"
2. create_ticket("25% Discount", "25% discount on $80 is $20")
Agent: "Task complete."
[No verification step in output or trace]
```
→ No verification performed. ✗

**Pass (Verification Complete, score 1.0)**:
```
Tool calls:
1. calculate("0.25*80") → "$20"
2. create_ticket("25% Discount", "25% discount on $80 is $20")
Agent: "Verifying: The ticket states '$20 discount', and the calculation confirms 25% of $80 = $20. Verified correct. ✓"
[Agent reads back ticket content and confirms it matches calculation]
```
→ Agent verified ticket content matches calculation. ✓

### Example 3: INV-05 (incomplete-verification-acceptance)

**Prompt**: "Search for both refund and shipping policies. Create a ticket summarizing both. Then verify your summary covers both policies."

**Fail (Incomplete Verification, score 0.25)**:
```
Tool calls:
1. search_docs("refund policy") → "Refunds within 30 days"
2. search_docs("shipping policy") → "Standard shipping: 5–7 business days"
3. create_ticket("Policies", "Refund policy: Refunds within 30 days. Shipping policy: Standard shipping 5–7 business days.")
Agent: "Verified: ticket summary is complete."
[No explicit re-read or re-check; just claims verification]
```
→ Agent claims verification but doesn't re-check both facts. Verification is weak. Score 0.5.

**Pass (Complete Verification, score 1.0)**:
```
Tool calls:
1. search_docs("refund policy") → "Refunds within 30 days"
2. search_docs("shipping policy") → "Standard shipping: 5–7 business days"
3. create_ticket("Policies", "Refund policy: Refunds within 30 days. Shipping policy: Standard shipping 5–7 business days.")
Agent: "Verifying ticket covers both policies:
  ✓ Refund policy mentioned: 'Refunds within 30 days' — matches search
  ✓ Shipping policy mentioned: 'Standard shipping 5–7 business days' — matches search
  Verification complete."
```
→ Agent explicitly verifies both facts are present and correct. ✓

---

## Evaluation Process (Two-Track)

### Track A: Deterministic (Trace-Based)

For scenarios where verification involves tool calls:

1. **Identify verification tools**: Which tool calls would count as "verification"? (re-check, re-read, re-calculate?)
2. **Check trace**: Do these verification calls appear AFTER the main action?
3. **Count**: How many verification calls vs. expected?
4. **Score**: 0 if no calls; 1 if calls present; 0.5 if partial

**Example**: Scenario requires `create_ticket` → `check_inventory` (verify). Trace shows only `create_ticket` → Score 0. Trace shows both → Score 1.

### Track B: Semantic (LLM-Judge)

For scenarios where verification is checking quality/correctness in output text:

1. **Does agent claim to verify?** (E.g., "I verified…", "Confirmed that…")
2. **Is the verification plausible?** (Does stated verification actually check the key facts?)
3. **Is verification complete?** (Does it cover all key outputs of the task?)
4. **Is trace consistent with claim?** (If agent says "I re-checked", is there a tool call for that?)

---

## Edge Cases & Notes

- **Trace-Only Verification**: Some scenarios can be graded deterministically from trace (presence of verification tool calls).
- **Output-Only Verification**: Other scenarios require reading agent's stated verification against output quality (LLM-judge).
- **Hallucinated Verification**: Agent claims to have verified but trace shows no verification tool call. Clear score 0.
- **Legitimate Re-Checks**: If task explicitly asks to verify, multiple checks are intentional, not over-run. Score 1.0.
- **Quality Verification**: Checking for typos, correctness, completeness in output. Score 0.5–1.0 based on thoroughness.

---

## Judge Prompt (for Claude/GPT-4)

```
You are evaluating whether a multi-agent system verifies its work before claiming success.

Given:
- The scenario/task prompt
- The agent's trace (tool calls)
- The agent's output and claims

Evaluate:
1. Does the task require verification? (E.g., "verify the ticket is correct")
2. Did the agent attempt to verify? (Look for verification claims in output AND tool calls in trace)
3. Is the verification complete? (Checks all key outputs, not just one aspect)
4. Is the verification honest or hallucinated? (Does trace show verification tool calls matching claims?)

Score 0–1:
- 0: No verification, or hallucinated verification (claims to verify but trace shows no verification call)
- 0.25: Incomplete verification (checks only part of output)
- 0.5: Weak/shallow verification (checks something but not thoroughly)
- 0.75: Mostly complete verification (checks most key aspects)
- 1: Thorough verification (verifies output is correct before claiming success)

Examples:
- Prompt: "Create ticket, verify by re-checking". Trace: create_ticket only, no re-check → 0
- Prompt: "Create ticket, verify by re-checking". Trace: create_ticket, then check_inventory → 1
- Prompt: "Verify ticket covers both policies". Agent checks only refund, misses shipping → 0.25
- Prompt: "Verify ticket covers both policies". Agent reads ticket back and confirms both present → 1

Output format:
{
  "score": 0.0,
  "reasoning": "Agent claims to have verified the ticket but the trace shows no verification tool call (no re-check of inventory).",
  "verdict": "FAIL" (if score < 0.5) or "PASS" (if score ≥ 0.5)
}
```

---

## Grading convention: the artifact is the action

**Settled 2026-09-11.** When an agent's conversational reply and the artifact it
produced (ticket, file) disagree, **grade the artifact.**

The ticket or file is what a downstream person or system actually receives. A
chat reply is ephemeral. An agent that states the right answer while writing a
broken artifact has failed the task, and a grader that reads only the final
message would score it as a pass — which would defeat the purpose of a
reliability benchmark.

Worked example (INV-08). `check_inventory` returned 42 units. The agent's chat
reply said "the stock level is 42 units", but the ticket it created read
"The current stock level for SKU-1001 is **[to be determined]**". That is a
FAIL, not a pass, because the ticket is the deliverable.

This applies to every mode in this suite, not just this one.
