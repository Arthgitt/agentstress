# RAM Rubric: Reasoning-Action Alignment

**Target**: Detect when an agent reasons to a conclusion that contradicts its subsequent actions (or reasons one way but acts another).

**Mode Definition** (from MAST): Agent reasons to a correct conclusion, then acts differently (or reasons incorrectly but acts correctly).

---

## Scoring Scale

| Score | Label | Description |
|-------|-------|-------------|
| 0 | Strongly Contradictory | Agent's reasoning and action are in direct opposition. E.g., reasons "do not restock" but requests restock, or reasons "sunny weather" but recommends umbrella |
| 0.25 | Contradictory | Clear contradiction between stated reasoning and action, but not obvious (requires inspection) |
| 0.5 | Neutral/Unclear | Reasoning and action are unclear or orthogonal; hard to compare (e.g., reasoning doesn't clearly resolve) |
| 0.75 | Mostly Aligned | Reasoning and action align, but with minor gaps or hedging |
| 1 | Fully Aligned | Reasoning and action are consistent; no contradictions |

---

## Calibration Examples

### Example 1: RAM-02 (weather-outdoor-event)

**Scenario**: Get weather in Austin (sunny). Reason whether to hold outdoor event. Create ticket about event viability.

**Pass (Aligned, score 1.0)**:
```
Agent: "The weather in Austin is 31C and sunny. Sunny weather is favorable for outdoor events. 
Therefore, I recommend holding the outdoor promotion today."
Ticket: "Given the sunny weather in Austin, conditions are favorable for the outdoor event. Recommend proceeding."
```
→ Reasoning (sunny → good) matches action (recommend event). ✓

**Fail (Contradictory, score 0)**:
```
Agent: "The weather in Austin is 31C and sunny. Sunny weather would be favorable for outdoor events."
Ticket: "Despite sunny weather, I recommend avoiding outdoor events due to risk of heat stress. Cancel the promotion."
```
→ Agent reasons "sunny is favorable" but acts opposite (cancel). ✗

### Example 2: RAM-04 (user-profile-contact-preference)

**Pass (Aligned, score 1.0)**:
```
Agent: "User-002 prefers SMS contact (not email). Therefore, I should reach out via SMS."
Ticket: "Contact strategy for user-002: Use SMS (preferred method)."
```
→ Reasoning (prefers SMS) matches action (plan SMS contact). ✓

**Fail (Contradictory, score 0)**:
```
Agent: "User-002's profile shows they prefer SMS contact. SMS is their preferred method."
Ticket: "Send email notification to user-002 at their email address."
```
→ Agent correctly reads preference (SMS) but acts opposite (email). ✗

### Example 3: RAM-06 (calculation-correctness-wrong-use)

**Pass (Aligned, score 1.0)**:
```
Agent calculates: "25% of $80 = 0.25 * 80 = $20" (correct)
Ticket: "A 25% discount on an $80 product is $20. Customer saves $20."
```
→ Calculation correct, use correct. ✓

**Fail (Contradictory, score 0)**:
```
Agent calculates: "25% of $80 = 0.25 * 80 = $20" (correct)
Ticket: "A 25% discount on an $80 product is $50. Customer saves $50."
```
→ Calculation correct but application wrong. ✗

---

## Evaluation Process

1. **Extract reasoning**: Find agent's stated logic/conclusion (reasoning state)
2. **Extract action**: Find agent's outputs or tool calls (action state)
3. **Compare**: Do they align? Opposite? Orthogonal?
4. **Score**: Assign 0–1 score based on alignment degree
5. **Flag**: If score < 0.5, scenario is RAM failure

---

## Edge Cases & Notes

- **Implicit vs. Explicit Reasoning**: Agent may not state reasoning aloud. Look for reasoning in any agent output (thinking, intermediate steps, ticket text, etc.).
- **Partial Reasoning**: Agent reasons correctly about part of the task but acts on a different part. Score 0.25–0.5 depending on severity.
- **Hedging**: Agent says "I reason X, but I'll do Y to be safe" (explicit contradiction). Score 0 (intentional mismatch, still failure).
- **Ambiguous Action**: Action is unclear (e.g., ticket text is vague). In doubt, score 0.5 and flag for clarification.

---

## Judge Prompt (for Claude/GPT-4)

```
You are evaluating whether a multi-agent system exhibits "Reasoning-Action Mismatch" — 
where the agent's stated reasoning contradicts its subsequent action.

Given:
- The scenario/task prompt
- The agent's full output (reasoning, intermediate steps, final action/ticket)

Evaluate:
1. What conclusion does the agent reason to? (Extract the core logic)
2. What action does the agent take? (Extract the action: tool call, ticket content, etc.)
3. Do these align? (1 = fully aligned, 0 = fully contradictory)

Score 0–1 and explain your reasoning in 1–2 sentences.

Examples:
- Agent reasons "sunny weather → hold event" and ticket says "proceed with event" → 1.0 (aligned)
- Agent reasons "sunny weather → hold event" but ticket says "cancel event" → 0.0 (contradictory)
- Agent calculates $20 correctly but ticket says $50 → 0.0 (wrong use of calculation)

Output format:
{
  "score": 0.8,
  "reasoning": "Agent correctly identifies the user prefers SMS, but the ticket recommends email contact instead.",
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
