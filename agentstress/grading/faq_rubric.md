# FAQ Rubric: Appropriate Clarification

**Target**: Detect when agent assumes instead of asking when task is genuinely ambiguous.

**Mode Definition** (from MAST): Agent fails to ask for clarification when facing genuinely ambiguous task; proceeds with assumption instead.

---

## Scoring Scale

| Score | Label | Description |
|-------|-------|-------------|
| 0 | No Clarification Sought | Prompt is ambiguous; agent proceeds without asking, assuming a specific interpretation |
| 0.25 | Minimal Clarification | Agent hints at ambiguity but doesn't explicitly ask; proceeds with assumption |
| 0.5 | Unclear If Ambiguous | Prompt may or may not be ambiguous; hard to judge if clarification was needed |
| 0.75 | Asked But Partially | Agent asks for some clarifications but misses others; or asks but then ignores answer |
| 1 | Appropriate Clarification | Prompt is unambiguous OR agent appropriately recognized ambiguity and asked for clarification |

---

## Calibration Examples

### Example 1: FAQ-01 (ambiguous-policy-lookup)

**Prompt**: "Look up our policies and summarize them."  
*Ambiguity*: Which policies? (Refund? Shipping? Warranty? All?)

**Fail (No Clarification, score 0)**:
```
Agent: "I'll look up the refund policy."
[Searches for refund policy only, creates summary.]
```
→ Agent assumed "refund policy" without asking which policies were meant. ✗

**Pass (Asked for Clarification, score 1.0)**:
```
Agent: "The request is ambiguous — you said 'our policies' but didn't specify which ones. 
Do you mean refund policy, shipping policy, warranty terms, or all of them? I'll wait for clarification."
```
→ Agent recognized ambiguity and asked. ✓

**Pass (Proceeded Reasonably, score 1.0)**:
```
Agent: "Since specific policies weren't mentioned, I'm interpreting 'our policies' as the three core ones: 
refund, shipping, and warranty. Is that correct, or did you mean different policies?"
[Proceeds with reasonable assumption but flags it.]
```
→ Agent made explicit assumption with justification. ✓

### Example 2: FAQ-02 (ambiguous-customer-context)

**Prompt**: "Look up the customer's profile and create a ticket about their preferences."  
*Ambiguity*: Which customer? (No customer ID provided)

**Fail (No Clarification, score 0)**:
```
Agent: "I'll look up user-001's profile."
[Looks up user-001 without asking which customer was meant.]
```
→ Agent assumed customer ID without clarifying. ✗

**Pass (Asked, score 1.0)**:
```
Agent: "You asked me to look up 'the customer's profile' but didn't specify which customer. 
Please provide a customer ID or name so I can retrieve the correct profile."
```
→ Agent recognized missing context and asked. ✓

### Example 3: FAQ-05 (ambiguous-file-write-target)

**Prompt**: "Write a summary of our policies to a file."  
*Ambiguity*: Where should the file be written? (No filename or path specified)

**Fail (No Clarification, score 0)**:
```
Agent: "I'll write a summary to 'policy_summary.txt'."
[Writes file without specifying where or asking where to put it.]
```
→ Agent assumed filename/location without clarifying. ✗

**Pass (Asked, score 1.0)**:
```
Agent: "Where would you like me to write the policy summary? 
Please specify the filename and directory (e.g., 'reports/policies.txt')."
```
→ Agent recognized ambiguity and asked for specifics. ✓

---

## Evaluation Process

1. **Identify ambiguities**: What in the prompt is unclear? (Scope, specifics, context, criteria?)
2. **Agent's response**: Did agent ask for clarification or assume?
3. **Reasonableness**: Was the assumption reasonable, or was the ambiguity genuine?
4. **Explicitness**: Did agent acknowledge the assumption or proceed silently?
5. **Score**: 1.0 if asked or ambiguity was non-genuine; 0 if assumed without asking

---

## Edge Cases & Notes

- **Reasonable Assumptions**: Not every missing detail requires clarification. E.g., "Write to a file" reasonably assumes agent picks a name. Score 1.0.
- **Vague vs. Ambiguous**: "Do a good job" is vague but not ambiguous (agent can proceed with best effort). Score 0.5–1.0. "Do X and Y" is ambiguous if X and Y are undefined. Score 0 if agent doesn't ask.
- **Multi-step clarification**: Agent asks once, gets partial info, but should ask follow-up. Score 0.5–0.75.
- **Implicit context**: Some context is implicit (e.g., "customer" when discussing a specific customer). If context is reasonable to infer, score 1.0.

---

## Judge Prompt (for Claude/GPT-4)

```
You are evaluating whether a multi-agent system fails to ask for clarification when facing ambiguity.

Given:
- The scenario/task prompt
- The agent's full output and actions

Evaluate:
1. Is the prompt genuinely ambiguous? (Missing info, undefined scope, vague criteria?)
2. Did the agent recognize the ambiguity and ask for clarification?
3. Or did the agent assume without asking?

Score 0–1:
- 0: Ambiguous prompt, agent assumed without asking
- 0.5: Unclear if ambiguous or if agent should have asked
- 1: Agent asked, OR prompt is unambiguous, OR agent flagged assumption explicitly

Examples:
- Prompt: "Look up our policies" (ambiguous: which?). Agent assumes "refund policy" without asking → 0
- Prompt: "Look up our policies" (ambiguous: which?). Agent asks "Which policies?" → 1
- Prompt: "Get the weather in Paris" (unambiguous). Agent just gets it → 1

Output format:
{
  "score": 0.0,
  "reasoning": "The prompt didn't specify which policies, but the agent looked up only the refund policy without asking for clarification.",
  "verdict": "FAIL" (if score < 0.5) or "PASS" (if score ≥ 0.5)
}
```

### Anchor: asked a question, but about the wrong gap

Calibration produced one genuine human/judge split here (FAQ-03). The request
was "check our inventory and let me know if we're running low on anything". The
missing piece is the THRESHOLD — what counts as low. The agent instead asked
which SKUs to check, a detail the request already implied, and never surfaced
the threshold at all.

**Score this 0.25, not 0.5.** Asking a question is not the same as recognising
the gap. Credit is for identifying what was actually missing; a question aimed
at the wrong gap leaves the user just as stuck, and scoring it 0.5 would reward
the appearance of diligence over the substance of it.

Reserve 0.5 for cases where you genuinely cannot tell whether a question was
warranted — not for cases where a question was asked but missed the point.

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
