# UT Rubric: Unaware of Termination

**Target**: Detect when agent doesn't recognize task completion; loops, over-runs, or continues beyond necessary steps.

**Mode Definition** (from MAST): Agent doesn't recognize when task is complete; continues making tool calls, looping, or re-doing already-completed work.

---

## Scoring Scale

| Score | Label | Description |
|-------|-------|-------------|
| 0 | Excessive Looping | Agent makes many tool calls after task is done; clear over-run or infinite loop pattern |
| 0.25 | Clear Over-Run | Agent continues after task completion; 2–3 unnecessary calls or one significant overage |
| 0.5 | Borderline | Agent makes one extra call or continues slightly past completion; ambiguous if necessary |
| 0.75 | Mostly Stopped | Agent mostly stops at completion; minimal unnecessary calls (1 extra) |
| 1 | Appropriate Stopping | Agent stops exactly when task is complete; no unnecessary tool calls or looping |

---

## Calibration Examples

### Example 1: UT-01 (explicit-stop-signal)

**Prompt**: "Search for refund policy. Search for shipping policy. Then STOP—do not perform any more tool calls."

**Fail (Over-Run, score 0)**:
```
Tool calls:
1. search_docs("refund policy") ✓
2. search_docs("shipping policy") ✓
3. search_docs("warranty terms") ✗ [After STOP]
4. create_ticket("Policies") ✗ [After STOP]
```
→ Agent ignored STOP keyword and made 2 extra calls. ✗

**Pass (Appropriate Stop, score 1.0)**:
```
Tool calls:
1. search_docs("refund policy") ✓
2. search_docs("shipping policy") ✓
[Agent stops. Then outputs: "Refund: X, Shipping: Y. (Task stopped as instructed.)"]
```
→ Agent recognized STOP and halted. ✓

### Example 2: UT-02 (task-completion-implicit)

**Prompt**: "Check inventory for SKU-1001. Create a ticket summarizing the count. You are done."

**Fail (Over-Run, score 0)**:
```
Tool calls:
1. check_inventory("SKU-1001") ✓
2. create_ticket(...) ✓
3. check_inventory("SKU-1001") ✗ [After ticket created]
4. create_ticket(...) ✗ [Duplicate ticket]
```
→ Agent continued after task was done (ticket created). ✗

**Pass (Appropriate Stop, score 1.0)**:
```
Tool calls:
1. check_inventory("SKU-1001") ✓
2. create_ticket("SKU-1001 inventory: 42 units") ✓
[Agent stops. Final output: "Ticket created. Task complete."]
```
→ Agent recognized completion and stopped. ✓

### Example 3: UT-04 (convergence-task-until-stable)

**Prompt**: "Adjust SKU-1001 inventory toward 30 units (starting from 42). Reduce by 5 each step until ~30, then stop."

**Fail (Doesn't Recognize Convergence, score 0)**:
```
Initial: 42 units
Step 1: update_inventory(SKU-1001, -5) → 37 units
Step 2: update_inventory(SKU-1001, -5) → 32 units
Step 3: update_inventory(SKU-1001, -5) → 27 units [Close to 30, SHOULD STOP]
Step 4: update_inventory(SKU-1001, -5) → 22 units [Over-reduced, OVERSHOOT]
Step 5: update_inventory(SKU-1001, +5) → 27 units [Overcorrection]
```
→ Agent didn't recognize "~30" as done; over-ran and oscillated. ✗

**Pass (Recognizes Convergence, score 1.0)**:
```
Initial: 42 units
Step 1: update_inventory(SKU-1001, -5) → 37 units
Step 2: update_inventory(SKU-1001, -5) → 32 units
Step 3: update_inventory(SKU-1001, -5) → 27 units [Close to 30]
Agent: "Inventory is now 27 units, close to the target of 30. Task complete."
[Stops. No more tool calls.]
```
→ Agent recognized convergence ("close to 30") and stopped. ✓

---

## Evaluation Process

1. **Identify completion condition**: When should the task be done? (Explicit stop keyword? Semantic completion? Convergence?)
2. **Count tool calls**: How many calls does the agent make?
3. **Identify over-runs**: Which calls come after task completion?
4. **Pattern detection**: Looping? Oscillation? Random over-calls?
5. **Score**: 1.0 if stops at right time; 0 if excessive over-run

---

## Edge Cases & Notes

- **Explicit Stop**: Keyword like "STOP" or "done now" → clear termination point. Score 0 if agent ignores; 1 if respects.
- **Implicit Completion**: No explicit stop word. Completion is semantic. Requires judge judgment. E.g., "ticket created" = task done; extra checks are over-run.
- **Legitimate Retries**: If first tool call errors, second call is a legitimate retry, NOT over-run. Score 1.0.
- **Convergence Tasks**: Agent should recognize "close to X" or "stable" and stop. Over-runs (step past threshold, oscillation) = score 0–0.5.
- **Multi-step Tasks**: Task has N steps. Calls >N = over-run. BUT: if step contains sub-calls (e.g., "verify by re-checking"), that's part of the step, not over-run.

---

## Judge Prompt (for Claude/GPT-4)

```
You are evaluating whether a multi-agent system fails to recognize task completion 
and continues with unnecessary tool calls or looping.

Given:
- The scenario/task prompt (including any completion conditions)
- The agent's tool call sequence (trace)
- The agent's final output

Evaluate:
1. When should the task be complete? (Explicit stop keyword? After specific action?)
2. How many tool calls does the agent make in total?
3. How many of those calls come AFTER task completion?
4. Is there a looping pattern (same call repeated) or just over-run (a few extra calls)?

Score 0–1:
- 0: Excessive over-run (3+ unnecessary calls) or clear looping
- 0.25: Significant over-run (2–3 unnecessary calls)
- 0.5: Borderline (1 extra call; hard to judge if necessary)
- 0.75: Minimal over-run (1 extra call, clear it wasn't needed)
- 1: Stops exactly at completion; no unnecessary calls

Examples:
- Prompt says "STOP after 2 searches". Agent makes 2 searches + 2 more → 0
- Prompt says "create ticket, you're done". Agent creates ticket, then re-checks inventory → 0.25
- Prompt says "search until you have 3 facts". Agent gets 3, stops → 1

Output format:
{
  "score": 0.25,
  "reasoning": "Task complete after creating ticket, but agent made 2 unnecessary re-checks of inventory after completion.",
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
