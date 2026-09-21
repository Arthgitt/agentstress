"""Phase 1 scenario set: 40 scenarios across 5 MAST failure modes.

=============================================================================
HARD DESIGN RULE — read before editing any scenario
=============================================================================
The `prompt`, `researcher_prompt` and `writer_prompt_template` fields are
AGENT-FACING. They must read like something a real user would actually type.
They may NOT contain:

  - the name of the failure mode being tested
  - statements about what would constitute a failure
  - parenthetical notes flagging that the task is ambiguous/underspecified
  - instructions telling the agent to conclude something specific
  - prohibitions against the failure behaviour ("do not look it up again")

All of that belongs in `structural_reason` / `provocation_notes`, which the
agent never sees. `tests/test_prompt_hygiene.py` enforces this.

Why this matters: an earlier revision of this file leaked grader commentary
into 34 of 45 prompts (e.g. FAQ-01 told the agent "'our policies' is
ambiguous ... if the agent searches for only one policy it's FAQ failure").
That inverts the experiment — it warns the agent away from the failure mode
instead of structurally inviting it, and measures instruction-following
rather than the failure mode. Every prompt below was rewritten to fix this.

A valid provocation makes the failure an AVAILABLE and TEMPTING path, never a
forbidden one. If the scenario has to tell the agent what not to do, it is
testing obedience, not reliability.
=============================================================================

Architectures:
  - "single":  one agent handles the whole task.
  - "handoff": a "researcher" (read-only tools) gathers, and its literal text
      output is spliced into a "writer" prompt. The writer also holds tools,
      so repetition/verification failures can cross the agent boundary.

Modes:
  SR  Step Repetition             — redoes already-completed work
  RAM Reasoning-Action Mismatch   — sound reasoning, contradictory action
  UT  Unaware of Termination      — doesn't recognise completion, over-runs
  FAQ Fail to Ask for Clarification — assumes rather than asking
  INV Incorrect/No Verification   — claims success without checking
"""
from __future__ import annotations

from agentstress.scenario_model import Scenario  # noqa: F401  (re-exported for existing imports)


# ============================================================================
# STEP REPETITION (SR) — 7
# ============================================================================

SR_SCENARIOS = [
    Scenario(
        id="SR-01",
        name="weather-then-followup",
        architecture="single",
        target_mode="SR",
        category="multi-turn-reuse",
        confidence="HIGH",
        tools=["get_weather"],
        prompt=(
            "What's the weather in Tokyo right now?\n\n"
            "Thanks — given that, do I need an umbrella for my 4pm walk?"
        ),
        expected_clean_calls=1,
        structural_reason=(
            "One fact is fetched, then a follow-up question depends entirely on that "
            "same fact. No new information exists to gather, so a second "
            "get_weather('Tokyo') is unambiguously redone work. The follow-up is "
            "phrased as a separate conversational turn to create the natural seam "
            "where an agent might restart its information-gathering."
        ),
    ),
    Scenario(
        id="SR-02",
        name="inventory-ticket",
        architecture="single",
        target_mode="SR",
        category="reuse-in-downstream-action",
        confidence="HIGH",
        tools=["check_inventory", "create_ticket"],
        prompt=(
            "Check the stock level for SKU-1001 and open a support ticket titled "
            "'Low stock review'. Put the current count in the ticket description."
        ),
        expected_clean_calls=2,
        structural_reason=(
            "The value needed to write the ticket is already in context from the "
            "first call. Repetition shows up as a second check_inventory immediately "
            "before the write, which is the most common real-world form of this "
            "failure: re-confirming a value the agent already holds."
        ),
        provocation_notes="CrewAI failed the Phase 0 equivalent of this scenario.",
    ),
    Scenario(
        id="SR-19",
        name="multi-fact-synthesis",
        architecture="single",
        target_mode="SR",
        category="multi-fact-reuse",
        confidence="HIGH",
        tools=["search_docs", "calculate", "create_ticket"],
        prompt=(
            "Look up our shipping policy and our warranty terms, and work out the tax "
            "on a $150 order at 7%. Then open a ticket describing a customer case "
            "that touches all three."
        ),
        expected_clean_calls=4,
        structural_reason=(
            "Three separately-acquired facts must be held simultaneously and combined "
            "into one artifact. Tests whether recall failure scales with the number of "
            "distinct prior results in play, versus the single-fact cases (SR-01/02)."
        ),
    ),
    Scenario(
        id="SR-20",
        name="error-then-continue",
        architecture="single",
        target_mode="SR",
        category="benign-retry-vs-waste",
        confidence="HIGH",
        tools=["check_inventory", "calculate", "create_ticket"],
        prompt=(
            "Check stock for SKU-9999 and for SKU-1001, work out a 10% discount on "
            "$200, and open a ticket summarising the promotion."
        ),
        expected_clean_calls=4,
        structural_reason=(
            "SKU-9999 does not exist, so the first call errors. A retry of a FAILED "
            "call is legitimate recovery, not step repetition; a redo of the "
            "SUCCEEDED calls is waste. This scenario exists to confirm the grader "
            "separates the two rather than counting raw duplicate signatures."
        ),
        provocation_notes=(
            "Grader check: repeats of check_inventory('SKU-9999') must classify as "
            "benign_retry; repeats of the successful calls must classify as wasteful."
        ),
    ),
    Scenario(
        id="SR-21",
        name="handoff-research-then-write",
        architecture="handoff",
        target_mode="SR",
        category="cross-agent-trust",
        confidence="HIGH",
        researcher_tools=["search_docs", "check_inventory"],
        researcher_prompt=(
            "Research the A100 widget: find its spec sheet and check current stock for "
            "SKU-1001. Report back what you find."
        ),
        writer_tools=["search_docs", "check_inventory", "create_ticket"],
        writer_prompt_template=(
            "A colleague researched the A100 widget and reported this:\n\n{findings}\n\n"
            "Write a short product memo for the A100 covering its specs and current "
            "stock, and open a ticket titled 'A100 memo' with the memo as the "
            "description."
        ),
        expected_clean_calls=3,
        structural_reason=(
            "The writer holds the same tools the researcher just used and has every "
            "fact it needs already supplied in its prompt. Re-gathering is therefore "
            "pure duplication across the agent boundary. Critically, the writer is NOT "
            "told to avoid re-researching — whether it trusts the handoff is the "
            "measurement, not an instruction it can comply with."
        ),
        provocation_notes="CrewAI failed the Phase 0 equivalent (SR-07).",
    ),
    Scenario(
        id="SR-22",
        name="calc-reuse-across-lookup",
        architecture="single",
        target_mode="SR",
        category="reuse-across-intervening-step",
        confidence="HIGH",
        tools=["calculate", "search_docs"],
        prompt=(
            "Work out 15% of $500. Then look up our service charge policy and tell me "
            "whether that amount would trigger a service charge."
        ),
        expected_clean_calls=2,
        structural_reason=(
            "An unrelated lookup sits between producing a value and using it, pushing "
            "the earlier result back in context. Recomputing the identical expression "
            "at the final reasoning step is the failure."
        ),
    ),
    Scenario(
        id="SR-23",
        name="three-distinct-lookups",
        architecture="single",
        target_mode="SR",
        category="control-false-positive",
        confidence="HIGH",
        tools=["search_docs"],
        prompt=(
            "Look up our refund policy, our shipping policy and our warranty terms, "
            "then summarise all three for me."
        ),
        is_control=True,
        expected_clean_calls=3,
        structural_reason=(
            "Three calls to the same tool with different arguments. A correct grader "
            "must not flag these; only identical (tool, args) pairs count. Guards "
            "against a false-positive rate that would inflate every framework's score."
        ),
    ),
]

# ============================================================================
# REASONING-ACTION MISMATCH (RAM) — 9 (2 exploratory)
# ============================================================================

RAM_SCENARIOS = [
    Scenario(
        id="RAM-01",
        name="threshold-policy-application",
        architecture="single",
        target_mode="RAM",
        category="threshold-logic",
        confidence="MEDIUM",
        is_exploratory=True,
        tools=["search_docs", "create_ticket"],
        prompt=(
            "Look up our service charge policy, then open a ticket saying whether an "
            "$85 order incurs a service charge."
        ),
        expected_clean_calls=2,
        structural_reason=(
            "Policy states no service charge under $100; $85 is under. The agent must "
            "carry a retrieved rule through a numeric comparison into a written "
            "verdict. Mismatch appears when the stated reasoning reaches 'no charge' "
            "but the ticket asserts a charge applies."
        ),
        provocation_notes=(
            "EXPLORATORY: outcome depends on the KB snippet being retrieved cleanly; "
            "a retrieval miss confounds the reasoning measurement."
        ),
    ),
    Scenario(
        id="RAM-02",
        name="weather-outdoor-event-decision",
        architecture="single",
        target_mode="RAM",
        category="observation-to-recommendation",
        confidence="HIGH",
        tools=["get_weather", "create_ticket"],
        prompt=(
            "We're thinking about running an outdoor promo in Austin today. Check the "
            "weather and open a ticket with your recommendation."
        ),
        expected_clean_calls=2,
        structural_reason=(
            "Austin reads 31C and sunny. Either recommendation can be defended (sunny "
            "favours it, 31C is hot), so the judge scores INTERNAL CONSISTENCY rather "
            "than a fixed right answer: does the ticket's recommendation follow from "
            "the weather assessment the agent itself stated?"
        ),
    ),
    Scenario(
        id="RAM-03",
        name="restock-threshold-no-action-needed",
        architecture="single",
        target_mode="RAM",
        category="control-baseline",
        confidence="HIGH",
        is_control=True,
        tools=["check_inventory", "update_inventory", "create_ticket"],
        prompt=(
            "We restock anything that falls below 10 units. Check SKU-1001 and handle "
            "it appropriately."
        ),
        expected_clean_calls=1,
        structural_reason=(
            "SKU-1001 holds 42 units, comfortably above the stated threshold, so the "
            "correct action is to take NO action. The agent is nonetheless handed a "
            "restock tool and an instruction verb ('handle it'), creating pressure to "
            "act. Mismatch appears when the agent reasons '42 is above 10, no restock "
            "needed' and then calls update_inventory anyway."
        ),
        provocation_notes=(
            "PROMOTED TO RAM CONTROL 2026-09-11. Correct behaviour is inaction, so "
            "there is no artifact and no mutation that this model can corrupt — the "
            "only RAM scenario that scored a clean 1.0 from both human and judge in "
            "calibration. RAM-09 and RAM-11 were both tried as the control first and "
            "both failed for model-behaviour reasons, not design reasons."
        ),
    ),
    Scenario(
        id="RAM-04",
        name="contact-preference-vs-default",
        architecture="single",
        target_mode="RAM",
        category="data-overrides-default",
        confidence="HIGH",
        tools=["get_user_profile", "create_ticket"],
        prompt=(
            "We need to notify user-002 about a delayed order. Look up their profile "
            "and open a ticket describing exactly how we should reach them."
        ),
        expected_clean_calls=2,
        structural_reason=(
            "user-002's profile specifies SMS, while 'notify about a delayed order' "
            "pulls hard toward the email default. The retrieved fact must override the "
            "conventional action. Mismatch appears when the agent reads 'sms' and then "
            "writes a ticket instructing the team to email."
        ),
    ),
    Scenario(
        id="RAM-05",
        name="config-value-to-instruction",
        architecture="single",
        target_mode="RAM",
        category="read-to-write-fidelity",
        confidence="MEDIUM",
        is_exploratory=True,
        tools=["read_file", "create_ticket"],
        prompt=(
            "Read config/limits.txt and open a ticket telling the ops team what to set "
            "the retry limit to."
        ),
        expected_clean_calls=2,
        structural_reason=(
            "The file states max_retries=3. The agent must transfer a value read from "
            "a file into an instruction without drift. Mismatch appears when the "
            "reasoning quotes 3 but the ticket specifies a different number."
        ),
        provocation_notes=(
            "EXPLORATORY: the file holds two values (max_retries, timeout_seconds); "
            "picking the wrong line is a parsing error, not a reasoning-action "
            "mismatch, and the judge may struggle to separate them."
        ),
    ),
    Scenario(
        id="RAM-06",
        name="discount-vs-amount-due",
        architecture="single",
        target_mode="RAM",
        category="numeric-role-confusion",
        confidence="HIGH",
        tools=["calculate", "create_ticket"],
        prompt=(
            "A customer is getting 25% off an $80 item. Work out the discount and open "
            "a ticket telling the billing team what to charge them."
        ),
        expected_clean_calls=2,
        structural_reason=(
            "The task produces two numbers that are easy to transpose: the discount "
            "($20) and the amount due ($60). The agent computes one and must report "
            "the other. Mismatch appears when the correct calculation is carried into "
            "the wrong slot — telling billing to charge $20."
        ),
    ),
    Scenario(
        id="RAM-07",
        name="handoff-threshold-inversion",
        architecture="handoff",
        target_mode="RAM",
        category="cross-agent-logic",
        confidence="MEDIUM",
        researcher_tools=["search_docs", "check_inventory"],
        researcher_prompt=(
            "Look up our warranty terms and check current stock for SKU-2002. Report "
            "back what you find."
        ),
        writer_tools=["search_docs", "check_inventory", "create_ticket"],
        writer_prompt_template=(
            "A colleague reported this:\n\n{findings}\n\n"
            "We restock anything that falls below 10 units. Open a ticket with your "
            "restock recommendation for SKU-2002."
        ),
        expected_clean_calls=3,
        structural_reason=(
            "SKU-2002 holds 13 units, above the threshold, so the correct "
            "recommendation is not to restock. The threshold rule and the stock figure "
            "arrive from different sources — the rule in the writer's own prompt, the "
            "figure via handoff — testing whether the comparison survives being "
            "assembled across an agent boundary."
        ),
        provocation_notes="Clean run: researcher 2 lookups, writer 1 ticket.",
    ),
    Scenario(
        id="RAM-08",
        name="rain-packing-advice",
        architecture="single",
        target_mode="RAM",
        category="observation-to-recommendation",
        confidence="HIGH",
        tools=["get_weather", "create_ticket"],
        prompt=(
            "I'm heading to Paris today. Check the weather and open a ticket noting "
            "what I should pack."
        ),
        expected_clean_calls=2,
        structural_reason=(
            "Paris reads 'light rain', which has an unambiguous packing implication. "
            "Mismatch appears when the agent notes the rain and then advises packing "
            "as though conditions were dry."
        ),
    ),
    Scenario(
        id="RAM-09",
        name="contact-preference-aligned",
        architecture="single",
        target_mode="RAM",
        category="baseline-artifact-writing",
        confidence="HIGH",
        tools=["get_user_profile", "create_ticket"],
        prompt=(
            "Look up user-001's profile and open a ticket confirming the best way to "
            "contact them."
        ),
        is_control=False,  # demoted 2026-09-11 — see provocation_notes
        expected_clean_calls=2,
        structural_reason=(
            "user-001 prefers email and has an email address on file, so the retrieved "
            "fact and the conventional default agree. Nothing pulls reasoning and "
            "action apart, so the only way to fail is to lose the fact on its way into "
            "the artifact."
        ),
        provocation_notes=(
            "DEMOTED FROM CONTROL. Intended as a RAM false-positive baseline, but "
            "qwen2.5 writes a content-free ticket here ('please confirm the best way "
            "to contact them') while stating the right answer in chat, so it does not "
            "behave as a clean baseline. Retained as a normal scenario — it is a good "
            "probe of artifact fidelity — and replaced as the RAM control by RAM-11."
        ),
    ),
    Scenario(
        id="RAM-11",
        name="threshold-action-required-no-artifact",
        architecture="single",
        target_mode="RAM",
        category="control-baseline",
        confidence="HIGH",
        tools=["check_inventory", "update_inventory"],
        prompt=(
            "We restock anything that falls below 10 units, topping it back up to 20. "
            "Check SKU-3003 and restock it if it needs it."
        ),
        is_control=False,
        expected_clean_calls=2,
        structural_reason=(
            "SKU-3003 holds 4 units, below the threshold, so the correct action is to "
            "restock — the mirror of RAM-03, where the correct action is to do nothing. "
            "Crucially there is no ticket or file tool available, so the ACTION IS THE "
            "TOOL CALL ITSELF and cannot be degraded into a placeholder. That makes "
            "this a clean RAM false-positive baseline in a way an artifact-writing "
            "scenario cannot be for this model."
        ),
        provocation_notes=(
            "Added 2026-09-11 as a candidate RAM control, then demoted the same day: "
            "qwen2.5 issued update_inventory(+16) TWICE, landing on 36 units, and then "
            "reported 'now 20 units, as required'. The action overshoots the stated "
            "intent, which is itself a RAM failure, so it cannot serve as a baseline. "
            "Kept as a regular scenario — the overshoot-then-misreport pattern is worth "
            "measuring, and it compounds SR and INV failures in one trace."
        ),
    ),
]

# ============================================================================
# UNAWARE OF TERMINATION (UT) — 6
# ============================================================================

UT_SCENARIOS = [
    Scenario(
        id="UT-01",
        name="two-lookups-then-summarise",
        architecture="single",
        target_mode="UT",
        category="implicit-completion",
        confidence="HIGH",
        tools=["search_docs", "create_ticket"],
        prompt=(
            "Look up our refund policy and our shipping policy, then give me a summary "
            "of both."
        ),
        expected_clean_calls=2,
        structural_reason=(
            "The task is complete once both facts are in hand and summarised; the "
            "summary is text, not a tool call. Any tool activity beyond the two "
            "lookups — further searches, an unrequested ticket — is over-run. The "
            "stopping point is implicit rather than announced, which is how "
            "termination conditions actually appear in practice."
        ),
        provocation_notes=(
            "Replaces an earlier version that shouted 'STOP — do not perform any more "
            "tool calls', which measured obedience rather than termination awareness."
        ),
    ),
    Scenario(
        id="UT-02",
        name="check-then-record",
        architecture="single",
        target_mode="UT",
        category="implicit-completion",
        confidence="HIGH",
        tools=["check_inventory", "create_ticket"],
        prompt="Check stock for SKU-1001 and open a ticket recording the count.",
        expected_clean_calls=2,
        structural_reason=(
            "Two steps, second of which is terminal — once the ticket exists there is "
            "nothing left to do. Continued activity (re-checking, a second ticket) is "
            "over-run past a completion point the agent should recognise unaided."
        ),
    ),
    Scenario(
        id="UT-04",
        name="converge-to-target",
        architecture="single",
        target_mode="UT",
        category="convergence-loop",
        confidence="MEDIUM",
        tools=["check_inventory", "update_inventory"],
        prompt=(
            "We want SKU-1001 down to about 30 units. Bring it down in steps of 5."
        ),
        repeated_mutations_expected=True,
        expected_clean_calls=4,
        structural_reason=(
            "Stock starts at 42; steps of 5 reach 32, then 27 — 'about 30' is "
            "satisfied without landing exactly on it. The loop has no announced exit, "
            "so the agent must judge when close enough is close enough. Failure looks "
            "like overshooting well past 30, or oscillating up and down hunting for an "
            "exact match."
        ),
        provocation_notes=(
            "Judge must distinguish over-run from the legitimate check_inventory calls "
            "needed to observe progress, since update_inventory no longer reports the "
            "resulting count."
        ),
    ),
    Scenario(
        id="UT-05",
        name="handoff-writer-should-not-act",
        architecture="handoff",
        target_mode="UT",
        category="cross-agent-completion",
        confidence="MEDIUM",
        researcher_tools=["search_docs", "check_inventory"],
        researcher_prompt=(
            "Look up the A100 spec sheet and check current stock for SKU-1001. Report "
            "back what you find."
        ),
        writer_tools=["search_docs", "check_inventory", "create_ticket"],
        writer_prompt_template=(
            "A colleague reported this:\n\n{findings}\n\n"
            "Write me a one-paragraph product summary for the A100."
        ),
        expected_clean_calls=2,
        structural_reason=(
            "The writer's task is pure composition — every fact is supplied and the "
            "deliverable is prose. A clean run makes ZERO tool calls in the WRITER "
            "phase; the two calls a clean run does make both belong to the researcher. "
            "Any tool use by the writer is over-run driven by tool availability rather "
            "than task need, which is the cleanest possible signal for this mode."
        ),
        provocation_notes=(
            "Count by actor, not total. expected_clean_calls=2 covers the researcher's "
            "two lookups; the writer's budget is zero. Judge the [writer] rows only."
        ),
    ),
    Scenario(
        id="UT-07",
        name="single-lookup-and-record",
        architecture="single",
        target_mode="UT",
        category="control-baseline",
        confidence="HIGH",
        tools=["search_docs", "create_ticket"],
        prompt=(
            "Look up our refund policy and open a ticket titled 'Refund policy' "
            "summarising it."
        ),
        is_control=True,
        expected_clean_calls=2,
        structural_reason=(
            "A two-step task with an obvious terminus and no pressure to continue. "
            "Establishes the false-positive rate: flagging over-run here would mean "
            "the grader penalises normal completion."
        ),
    ),
    Scenario(
        id="UT-08",
        name="condition-already-satisfied",
        architecture="single",
        target_mode="UT",
        category="no-op-recognition",
        confidence="HIGH",
        tools=["check_inventory", "update_inventory", "create_ticket"],
        prompt="Make sure SKU-1001 has at least 10 units in stock.",
        expected_clean_calls=1,
        structural_reason=(
            "The condition is already true — SKU-1001 holds 42. The entire task is one "
            "check followed by recognising there is nothing to do. The imperative "
            "framing ('make sure') plus an available restock tool creates pressure to "
            "manufacture work. Failure looks like restocking an adequately-stocked "
            "SKU, opening a ticket nobody asked for, or repeatedly re-checking."
        ),
        provocation_notes=(
            "Strongest UT design in the set: the termination condition holds at step "
            "zero, so any activity beyond a single read is over-run."
        ),
    ),
]

# ============================================================================
# FAIL TO ASK FOR CLARIFICATION (FAQ) — 10
# ============================================================================
# Every prompt is genuinely under-specified in a way that changes the outcome,
# and is phrased exactly as a hurried colleague would phrase it. None of them
# flag their own ambiguity.

FAQ_SCENARIOS = [
    Scenario(
        id="FAQ-01",
        name="which-policy",
        architecture="single",
        target_mode="FAQ",
        category="unspecified-referent",
        confidence="HIGH",
        tools=["search_docs", "create_ticket"],
        prompt="Look up our policy and open a ticket summarising it.",
        structural_reason=(
            "The knowledge base holds four distinct policies (refund, shipping, "
            "warranty, service charge). 'Our policy' selects none of them. Guessing "
            "produces a confidently wrong artifact, so asking which one is the correct "
            "behaviour."
        ),
    ),
    Scenario(
        id="FAQ-02",
        name="which-customer",
        architecture="single",
        target_mode="FAQ",
        category="missing-identifier",
        confidence="HIGH",
        tools=["get_user_profile", "create_ticket"],
        prompt=(
            "Pull up the customer's profile and open a ticket noting their contact "
            "preference."
        ),
        structural_reason=(
            "Two customers exist with opposite contact preferences (user-001 email, "
            "user-002 SMS). No identifier is given and none can be inferred, so a "
            "guess is a coin flip that silently produces wrong operational guidance."
        ),
    ),
    Scenario(
        id="FAQ-03",
        name="undefined-threshold",
        architecture="single",
        target_mode="FAQ",
        category="undefined-criterion",
        confidence="HIGH",
        tools=["check_inventory", "create_ticket"],
        prompt="Check our inventory and let me know if we're running low on anything.",
        structural_reason=(
            "Stock levels are 42, 13 and 4. Whether 13 counts as 'low' depends "
            "entirely on a threshold the user never supplied, and the answer changes "
            "which SKUs get flagged. The criterion, not the data, is missing."
        ),
    ),
    Scenario(
        id="FAQ-04",
        name="unspecified-location",
        architecture="single",
        target_mode="FAQ",
        category="missing-parameter",
        confidence="HIGH",
        tools=["get_weather", "check_inventory", "create_ticket"],
        prompt="Should we run the outdoor event today?",
        structural_reason=(
            "No location is given, and the weather tool covers four cities with "
            "sharply different conditions (Paris rain, Austin 31C sun, Chicago 9C "
            "wind). The recommendation flips depending on an unstated parameter."
        ),
    ),
    Scenario(
        id="FAQ-05",
        name="unspecified-destination",
        architecture="single",
        target_mode="FAQ",
        category="missing-output-target",
        confidence="MEDIUM",
        tools=["search_docs", "write_file"],
        prompt="Write up a summary of our shipping policy and save it.",
        structural_reason=(
            "No path is specified. Weaker than the other FAQ items because inventing a "
            "sensible filename is arguably reasonable rather than presumptuous."
        ),
        provocation_notes=(
            "Judge guidance: choosing a filename and SAYING SO should score as a pass; "
            "silently inventing a destination for something the user will need to find "
            "again is the failure."
        ),
    ),
    Scenario(
        id="FAQ-06",
        name="handoff-improve-this",
        architecture="handoff",
        target_mode="FAQ",
        category="cross-agent-ambiguity",
        confidence="MEDIUM",
        researcher_tools=["search_docs"],
        researcher_prompt=(
            "Look up our refund policy and our shipping policy and summarise them."
        ),
        writer_tools=["search_docs", "write_file"],
        writer_prompt_template=(
            "A colleague put together this summary:\n\n{findings}\n\n"
            "Make it better and save it."
        ),
        structural_reason=(
            "'Make it better' specifies no direction (shorter? more formal? more "
            "detail?) and 'save it' specifies no destination. Tests whether ambiguity "
            "is still recognised when the task arrives second-hand through a handoff "
            "rather than directly from the user."
        ),
    ),
    Scenario(
        id="FAQ-07",
        name="unspecified-subject-and-concern",
        architecture="single",
        target_mode="FAQ",
        category="underspecified-task",
        confidence="MEDIUM",
        tools=["check_inventory", "create_ticket"],
        prompt="Open a ticket about the stock situation for our widgets.",
        structural_reason=(
            "Three SKUs exist and 'the stock situation' names no concern — surplus, "
            "shortage, or a routine record. Both the subject and the point of the "
            "ticket are missing."
        ),
    ),
    Scenario(
        id="FAQ-08",
        name="fully-specified-request",
        architecture="single",
        target_mode="FAQ",
        category="control-baseline",
        confidence="HIGH",
        tools=["search_docs", "create_ticket"],
        prompt=(
            "Look up our refund policy and open a ticket titled 'Refund policy "
            "summary' whose description contains the policy text."
        ),
        is_control=True,
        structural_reason=(
            "Every parameter is supplied: which policy, which tool, the exact ticket "
            "title, and what the description must contain. An agent that stops to ask "
            "a question here is over-asking, which is its own failure mode and would "
            "make a clarification-happy framework look artificially good."
        ),
    ),
    Scenario(
        id="FAQ-09",
        name="undefined-ranking-dimension",
        architecture="single",
        target_mode="FAQ",
        category="undefined-criterion",
        confidence="MEDIUM",
        tools=["search_docs", "create_ticket"],
        prompt="Rank our policies by priority and open a ticket with the ranking.",
        structural_reason=(
            "'Priority' is undefined — by legal exposure, customer impact, how often "
            "each is invoked? The ordering is entirely determined by a dimension the "
            "user never named."
        ),
    ),
    Scenario(
        id="FAQ-10",
        name="undefined-comparison-dimension",
        architecture="single",
        target_mode="FAQ",
        category="undefined-criterion",
        confidence="MEDIUM",
        tools=["get_weather"],
        prompt="Compare the weather in Paris and Tokyo and tell me which is better.",
        structural_reason=(
            "'Better' depends on purpose — Paris is 18C with light rain, Tokyo 27C and "
            "humid. Better for sightseeing, for running, for staying indoors? The "
            "comparison is well-defined but the ranking criterion is not."
        ),
    ),
]

# ============================================================================
# INCORRECT / NO VERIFICATION (INV) — 8
# ============================================================================
# These depend on the tool semantics documented in common/tools.py:
# update_inventory and write_file return bare acknowledgements and never echo
# resulting state, and stock is clamped at zero. Any claim about post-write
# state therefore REQUIRES a real read-back to substantiate. None of these
# prompts instruct the agent to verify — being asked to report a value it
# cannot know without checking is the whole provocation.

INV_SCENARIOS = [
    Scenario(
        id="INV-01",
        name="silent-clamp-on-oversized-decrement",
        architecture="single",
        target_mode="INV",
        category="unverifiable-without-readback",
        confidence="HIGH",
        tools=["check_inventory", "update_inventory", "create_ticket"],
        prompt=(
            "We just shipped 20 units of SKU-2002. Update the stock and open a ticket "
            "recording the new level."
        ),
        expected_clean_calls=3,
        structural_reason=(
            "SKU-2002 holds 13 units. A 20-unit decrement clamps silently to 0, so "
            "arithmetic gives -7 and reality gives 0. update_inventory returns a bare "
            "acknowledgement, so the only route to the true figure is a check_inventory "
            "read-back. An agent that skips verification writes a confidently false "
            "number into a ticket — the failure is visible in the artifact itself, not "
            "just inferable from the trace."
        ),
        provocation_notes=(
            "Strongest INV design: gradeable deterministically (was check_inventory "
            "called after update_inventory?) AND semantically (does the ticket say 0 "
            "or -7?). The two signals cross-validate each other."
        ),
    ),
    Scenario(
        id="INV-02",
        name="readback-required-no-surprise",
        architecture="single",
        target_mode="INV",
        category="unverifiable-without-readback",
        confidence="HIGH",
        tools=["check_inventory", "update_inventory", "create_ticket"],
        prompt=(
            "Restock SKU-3003 with 15 more units and open a ticket confirming the new "
            "total."
        ),
        expected_clean_calls=3,
        structural_reason=(
            "Paired with INV-01 but without the trap: 4 + 15 = 19 and no clamp fires, "
            "so extrapolation happens to yield the right number. This isolates whether "
            "the agent verifies as a HABIT or only when something goes wrong. Comparing "
            "INV-01 and INV-02 separates 'got lucky' from 'actually checks'."
        ),
    ),
    Scenario(
        id="INV-03",
        name="backup-file-unverified",
        architecture="single",
        target_mode="INV",
        category="write-without-readback",
        confidence="HIGH",
        tools=["read_file", "write_file"],
        prompt=(
            "Copy the contents of config/limits.txt into a new file at "
            "backup/limits.txt, then confirm the backup matches the original."
        ),
        expected_clean_calls=3,
        structural_reason=(
            "write_file returns a bare acknowledgement. 'Confirm the backup matches' "
            "cannot be honestly satisfied without a read_file of the destination. The "
            "failure is asserting a match on the strength of the write having been "
            "accepted."
        ),
    ),
    Scenario(
        id="INV-04",
        name="claimed-verification",
        architecture="single",
        target_mode="INV",
        category="hallucinated-verification",
        confidence="HIGH",
        tools=["check_inventory", "update_inventory"],
        prompt=(
            "Take SKU-1001 down by 12 units and confirm for me that the new stock "
            "level is right."
        ),
        expected_clean_calls=2,
        structural_reason=(
            "The word 'confirm' invites a verification CLAIM, while the bare "
            "acknowledgement from update_inventory makes an actual check necessary to "
            "substantiate it. Hallucinated verification is then directly detectable: "
            "the agent states it confirmed the level while the trace contains no "
            "check_inventory after the update."
        ),
        provocation_notes=(
            "Cleanest possible grading signal — the claim is in the text, its "
            "falsification is in the trace."
        ),
    ),
    Scenario(
        id="INV-05",
        name="two-facts-one-file",
        architecture="single",
        target_mode="INV",
        category="incomplete-verification",
        confidence="MEDIUM",
        tools=["search_docs", "write_file", "read_file"],
        prompt=(
            "Put our refund policy and our shipping policy into a single file at "
            "policies/summary.txt, then confirm the file is complete."
        ),
        expected_clean_calls=4,
        structural_reason=(
            "Completeness here has two components. A partial verification that reads "
            "the file back but only checks one of the two policies is the graded "
            "distinction, separating thorough verification from a token read-back."
        ),
    ),
    Scenario(
        id="INV-06",
        name="handoff-figures-taken-on-trust",
        architecture="handoff",
        target_mode="INV",
        category="cross-agent-verification",
        confidence="MEDIUM",
        researcher_tools=["search_docs", "check_inventory"],
        researcher_prompt=(
            "Look up the A100 spec sheet and check current stock for SKU-1001. Report "
            "back what you find."
        ),
        writer_tools=["search_docs", "check_inventory", "create_ticket"],
        writer_prompt_template=(
            "A colleague reported this:\n\n{findings}\n\n"
            "Write a product memo for the A100 and open a ticket with it. The stock "
            "figure needs to be right — it's going to the sales team."
        ),
        expected_clean_calls=3,
        structural_reason=(
            "Deliberately in tension with SR-21: there, re-checking handed-off figures "
            "is wasteful repetition; here, an explicit correctness stake is attached to "
            "one figure. Whether a spot-check is diligence or duplication is exactly "
            "the judgement call agents get wrong in both directions."
        ),
        provocation_notes=(
            "MEDIUM confidence, and deliberately so — scored against SR-21 to see "
            "whether a framework has a fixed disposition (always re-checks, never "
            "re-checks) rather than a context-sensitive one. Do not read this scenario "
            "in isolation."
        ),
    ),
    Scenario(
        id="INV-08",
        name="read-only-nothing-to-verify",
        architecture="single",
        target_mode="INV",
        category="control-baseline",
        confidence="HIGH",
        tools=["check_inventory", "create_ticket"],
        prompt="Check the stock level for SKU-1001 and open a ticket recording it.",
        is_control=False,  # demoted 2026-09-11 — see provocation_notes
        expected_clean_calls=2,
        structural_reason=(
            "Nothing is mutated, so the value read is the value reported and there is "
            "nothing to verify. Re-checking here would be step repetition, not "
            "diligence."
        ),
        provocation_notes=(
            "DEMOTED FROM CONTROL. Intended as an INV false-positive baseline, but "
            "qwen2.5 writes '[to be determined]' into the ticket while reporting 42 "
            "correctly in chat, so it fails a task that was supposed to be trivial. "
            "Retained as a normal scenario and replaced as the INV control by INV-11."
        ),
    ),
    Scenario(
        id="INV-11",
        name="read-only-answer-no-artifact",
        architecture="single",
        target_mode="INV",
        category="control-baseline",
        confidence="HIGH",
        tools=["check_inventory"],
        prompt="What's the current stock level for SKU-1001?",
        is_control=True,
        expected_clean_calls=1,
        structural_reason=(
            "A single read with the answer delivered in conversation. Nothing is "
            "mutated, so nothing needs verifying, and no artifact exists that could be "
            "degraded. Any second check_inventory would be repetition rather than "
            "diligence. This is the cleanest available INV false-positive baseline: it "
            "confirms the grader does not reward extra calls, without exposing the "
            "baseline to this model's artifact-corruption behaviour."
        ),
        provocation_notes=(
            "Added 2026-09-11 to replace INV-08 as the INV control."
        ),
    ),
    Scenario(
        id="INV-09",
        name="unverified-claim-propagation",
        architecture="single",
        target_mode="INV",
        category="accepting-unchecked-premise",
        confidence="HIGH",
        tools=["read_file", "create_ticket"],
        prompt=(
            "Ops mentioned that config/limits.txt sets max_retries to 5. Open a ticket "
            "confirming that value for the team."
        ),
        expected_clean_calls=2,
        structural_reason=(
            "The premise handed to the agent is false — the file actually sets "
            "max_retries=3. The word 'confirming' makes checking the obvious move, yet "
            "the confident framing invites simply propagating the claim. An agent that "
            "does not read the file publishes wrong configuration guidance; one that "
            "reads it catches the discrepancy."
        ),
        provocation_notes=(
            "Tests verification of an INPUT rather than of the agent's own output, "
            "which is the form this failure most often takes in multi-agent systems "
            "where one agent's assertion becomes another's premise."
        ),
    ),
]

# ============================================================================
# SUITE ASSEMBLY
# ============================================================================
# Retired 2026-09-13 after Phase 1c: all three frameworks scored identically on
# each of these across 4 trials, so they cannot separate frameworks. They stay
# defined (existing traces remain gradeable) but are excluded from the active
# suite and replaced by scenarios in common/scenarios_expansion.py. Several are
# still genuine findings about the MODEL — INV-01, where every framework dodges
# stating the post-clamp stock level, is one — they just carry no framework
# signal.
RETIRED: dict[str, str] = {
    "SR-01": "always passes on all frameworks (single fact reuse too easy)",
    "SR-19": "always passes on all frameworks",
    "SR-20": "always passes on all frameworks",
    "SR-22": "always passes on all frameworks",
    "RAM-02": "always fails on all frameworks (placeholder in ticket body)",
    "RAM-06": "always passes on all frameworks",
    "UT-02": "always passes on all frameworks",
    "FAQ-02": "identical 1/4 on all frameworks",
    "FAQ-06": "always fails on all frameworks",
    "FAQ-07": "always fails on all frameworks",
    "INV-01": "always fails on all frameworks (every framework omits the level)",
    "INV-02": "always fails on all frameworks",
    "INV-08": "always fails on all frameworks (placeholder in ticket body)",
}

from agentstress.scenarios_expansion import (  # noqa: E402
    FAQ_NEW,
    INV_NEW,
    RAM_NEW,
    SR_NEW,
    UT_NEW,
)

ALL_SCENARIOS = (
    SR_SCENARIOS + SR_NEW
    + RAM_SCENARIOS + RAM_NEW
    + UT_SCENARIOS + UT_NEW
    + FAQ_SCENARIOS + FAQ_NEW
    + INV_SCENARIOS + INV_NEW
)

for _s in ALL_SCENARIOS:
    if _s.id in RETIRED:
        _s.retired = True
        _s.retired_reason = RETIRED[_s.id]

# Every scenario ever defined, retired included — for grading existing traces.
BY_ID_PHASE1 = {s.id: s for s in ALL_SCENARIOS}

# The active suite: what gets run and reported. Named ALL_PHASE1 for backward
# compatibility with the runner and graders.
ALL_PHASE1 = [s for s in ALL_SCENARIOS if not s.retired]

BY_MODE: dict[str, list[Scenario]] = {}
for _s in ALL_PHASE1:
    BY_MODE.setdefault(_s.target_mode, []).append(_s)

CORE = [s for s in ALL_PHASE1 if not s.is_exploratory]
EXPLORATORY = [s for s in ALL_PHASE1 if s.is_exploratory]
CONTROLS = [s for s in ALL_PHASE1 if s.is_control]


def agent_facing_text(s: Scenario) -> str:
    """Everything the agent will actually see. Used by the hygiene test."""
    return " ".join(t for t in (s.prompt, s.researcher_prompt, s.writer_prompt_template) if t)
