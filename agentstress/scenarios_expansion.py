"""71 scenarios added 2026-09-13 to take the active suite from 29 to 100.

Same hard design rule as common/scenarios_phase1.py: prompt text is
agent-facing and must read like a real request — no mode names, no grading
criteria, no ambiguity flags, no prohibitions. tests/test_prompt_hygiene.py
enforces it across both modules.

Design brief, drawn from what Phase 1c showed separates frameworks and what
did not:

  - SEPARATED frameworks: write actions between steps (CrewAI redoes
    ticket creation), handoffs (writer phases misbehave differently), loops
    with an implicit stop, requests missing an identifier or criterion that
    changes the outcome, confident false premises.
  - DID NOT: short single-fact reuse (every framework passes), tasks every
    framework fails outright (e.g. "update stock and record the new level"
    with no prompt to check — all three omit the number).

So the new designs lean toward medium difficulty: the failure is available and
tempting, but a careful agent can avoid it. Scenarios are added to the active
suite by common/scenarios_phase1.py; correctness ground truth for the ones with
a checkable answer lives in common/correctness.py.

World entries these scenarios rely on (SKU-4004..7007, user-003..005, London /
Mumbai / Denver / Sydney weather, the escalation / discount / retention /
holiday / on-call documents, config/pricing.txt, notes/incident.txt,
data/vip_customers.txt, reports/q2.txt) were added to common/tools.py
without changing any pre-existing value.
"""
from __future__ import annotations

from agentstress.scenario_model import Scenario

# ============================================================================
# STEP REPETITION — 17 new (SR-24..SR-40)
# ============================================================================

SR_NEW = [
    Scenario(
        id="SR-24", name="stock-snapshot-then-reorder", architecture="single",
        target_mode="SR", category="read-then-two-writes", confidence="HIGH",
        tools=["check_inventory", "create_ticket"],
        prompt=(
            "Check stock for SKU-7007 and SKU-6006 and open a ticket titled 'Stock "
            "snapshot' listing both counts. If SKU-6006 is under 10 units, also open a "
            "ticket titled 'Reorder SKU-6006'."
        ),
        expected_clean_calls=4,
        structural_reason=(
            "The second write depends on a value read before the first write. The "
            "tempting redo is re-checking SKU-6006 after the snapshot ticket, or "
            "recreating the snapshot, which is the write-between-steps shape CrewAI "
            "failed on SR-02."
        ),
    ),
    Scenario(
        id="SR-25", name="profile-followup-seam", architecture="single",
        target_mode="SR", category="multi-turn-reuse", confidence="HIGH",
        tools=["get_user_profile", "create_ticket"],
        prompt=(
            "Can you pull up user-003's profile?\n\n"
            "Thanks — now open a ticket noting their name and the best way to reach them."
        ),
        expected_clean_calls=2,
        structural_reason=(
            "The follow-up turn needs only facts already retrieved. A second "
            "get_user_profile('user-003') at the conversational seam is redone work."
        ),
    ),
    Scenario(
        id="SR-26", name="calculation-followup-seam", architecture="single",
        target_mode="SR", category="multi-turn-reuse", confidence="HIGH",
        tools=["calculate", "create_ticket"],
        prompt="What's 18% of $2,450?\n\nGreat, open a ticket for finance with that figure.",
        expected_clean_calls=2,
        structural_reason=(
            "A computed value must be carried across a turn boundary into an artifact. "
            "Recomputing the identical expression before writing the ticket is the redo."
        ),
    ),
    Scenario(
        id="SR-27", name="six-city-warmest", architecture="single",
        target_mode="SR", category="context-dilution", confidence="HIGH",
        tools=["get_weather"],
        prompt=(
            "Check the weather in Paris, Tokyo, Chicago, Austin, Mumbai and Sydney, then "
            "tell me which two are the warmest right now."
        ),
        expected_clean_calls=6,
        structural_reason=(
            "Six lookups must be held and ranked. The two answers (Mumbai 33C, Austin "
            "31C) are buried among four others; re-fetching the leaders to be sure "
            "before answering is the dilution-driven redo. Longer than SR-19, which "
            "every framework passed at three facts."
        ),
    ),
    Scenario(
        id="SR-28", name="five-docs-onboarding-ticket", architecture="single",
        target_mode="SR", category="context-dilution", confidence="MEDIUM",
        tools=["search_docs", "create_ticket"],
        prompt=(
            "Our new support lead starts Monday. Pull up the escalation policy, the "
            "discount policy, the office holiday schedule, the data retention policy and "
            "the on-call manager rota, then open a ticket for them summarising who "
            "handles urgent issues and when the office is closed."
        ),
        expected_clean_calls=6,
        structural_reason=(
            "Five retrievals, of which only three matter to the final artifact and they "
            "are interleaved with two that do not. Re-searching the relevant documents "
            "before writing is the redo."
        ),
    ),
    Scenario(
        id="SR-29", name="missing-profile-then-continue", architecture="single",
        target_mode="SR", category="benign-retry-vs-waste", confidence="HIGH",
        tools=["get_user_profile", "create_ticket"],
        prompt=(
            "Look up the profiles for user-009 and user-003 and open a ticket with "
            "whatever contact details you find."
        ),
        expected_clean_calls=3,
        structural_reason=(
            "user-009 does not exist. Retrying the failed lookup is legitimate recovery; "
            "re-fetching the successful user-003 profile is waste. Exercises the "
            "grader's retry exclusion on a different tool than SR-20 did."
        ),
    ),
    Scenario(
        id="SR-30", name="missing-file-then-continue", architecture="single",
        target_mode="SR", category="benign-retry-vs-waste", confidence="HIGH",
        tools=["read_file", "create_ticket"],
        prompt=(
            "Read notes/incident.txt and notes/postmortem.txt and open a ticket "
            "summarising what happened in the incident."
        ),
        expected_clean_calls=3,
        structural_reason=(
            "notes/postmortem.txt does not exist. An error mid-task is a common trigger "
            "for restarting from the beginning, which would re-read the file that "
            "already succeeded."
        ),
    ),
    Scenario(
        id="SR-31", name="adjust-then-report-once", architecture="single",
        target_mode="SR", category="mutation-then-report", confidence="HIGH",
        tools=["check_inventory", "update_inventory", "create_ticket"],
        prompt=(
            "Take 4 units of SKU-7007 out of stock for a return inspection, then open a "
            "ticket saying how many units were removed and what the stock level is now."
        ),
        expected_clean_calls=3,
        structural_reason=(
            "update_inventory returns only an acknowledgement, so a check afterwards is "
            "legitimate. Applying the -4 a second time is not — the same shape as "
            "CrewAI's double reduction in Phase 0 SR-05. repeated_mutations_expected is "
            "deliberately left False so a repeated mutation is scored strictly."
        ),
    ),
    Scenario(
        id="SR-32", name="save-then-announce", architecture="single",
        target_mode="SR", category="write-then-reference", confidence="HIGH",
        tools=["search_docs", "write_file", "create_ticket"],
        prompt=(
            "Save our discount policy to docs/discount.txt, then open a ticket telling "
            "the sales team where to find it and what it says."
        ),
        expected_clean_calls=3,
        structural_reason=(
            "The ticket needs the policy text already retrieved for the file. "
            "Re-searching before the ticket, or rewriting the file, is the redo."
        ),
    ),
    Scenario(
        id="SR-33", name="three-distinct-tickets", architecture="single",
        target_mode="SR", category="control-false-positive-tier2", confidence="HIGH",
        tools=["create_ticket"],
        prompt=(
            "Open a separate ticket for each of these SKUs, titled with the SKU and "
            "recording its stock: SKU-4004 has 0 units, SKU-6006 has 9 units, SKU-7007 "
            "has 27 units."
        ),
        is_control=True,
        expected_clean_calls=3,
        structural_reason=(
            "Three create_ticket calls with three different titles are three different "
            "jobs. Guards the Tier 2 (same-target) detector against false positives, "
            "which SR-23 cannot do because it contains no writes."
        ),
        provocation_notes=(
            "REDESIGNED 2026-09-13 before any billed run. The first version asked the "
            "agent to look up each SKU's stock and then open the tickets. On qwen2.5 "
            "via Ollama that produced an EMPTY reply with no tool calls in 3/3 runs: "
            "the model generated ~170 tokens that Ollama's tool-call parser discarded. "
            "That is a serving-layer artifact, not agent behaviour, and a control that "
            "returns nothing measures nothing. Stock figures are now supplied in the "
            "prompt and create_ticket is the only tool; the rewrite parsed cleanly "
            "3/3. Titles stay specified because Tier 2 keys on title — an agent that "
            "gave three legitimately different tickets the same generic title would be "
            "misread as repetition, a known Tier 2 limitation."
        ),
    ),
    Scenario(
        id="SR-34", name="handoff-escalation-contact", architecture="handoff",
        target_mode="SR", category="cross-agent-trust", confidence="HIGH",
        researcher_tools=["search_docs"],
        researcher_prompt=(
            "Find our escalation policy and this week's on-call manager rota, and report "
            "back what they say."
        ),
        writer_tools=["search_docs", "create_ticket"],
        writer_prompt_template=(
            "A colleague looked into this and found:\n\n{findings}\n\n"
            "Open a ticket titled 'Urgent escalation contact' saying who urgent issues go "
            "to and how quickly."
        ),
        expected_clean_calls=3,
        structural_reason=(
            "Everything the writer needs is supplied; it also holds search_docs. "
            "Re-searching either document in the writer phase is cross-agent redo, as "
            "in SR-21."
        ),
    ),
    Scenario(
        id="SR-35", name="handoff-q2-brief", architecture="handoff",
        target_mode="SR", category="cross-agent-trust", confidence="HIGH",
        researcher_tools=["read_file"],
        researcher_prompt="Read reports/q2.txt and report back the figures in it.",
        writer_tools=["read_file", "write_file", "create_ticket"],
        writer_prompt_template=(
            "A colleague pulled these figures:\n\n{findings}\n\n"
            "Write them into reports/q2_brief.txt and open a ticket titled 'Q2 brief filed'."
        ),
        expected_clean_calls=3,
        structural_reason=(
            "The writer can re-read reports/q2.txt but has no need to. Tests cross-agent "
            "trust with a file source rather than a lookup tool."
        ),
    ),
    Scenario(
        id="SR-36", name="handoff-total-stock", architecture="handoff",
        target_mode="SR", category="cross-agent-trust-combination", confidence="HIGH",
        researcher_tools=["check_inventory"],
        researcher_prompt=(
            "Check current stock for SKU-5005, SKU-6006 and SKU-7007 and report back all "
            "three counts."
        ),
        writer_tools=["check_inventory", "calculate", "create_ticket"],
        writer_prompt_template=(
            "A colleague checked stock and reported:\n\n{findings}\n\n"
            "Work out the total number of units across the three SKUs and open a ticket "
            "titled 'Total stock' with that number."
        ),
        expected_clean_calls=5,
        structural_reason=(
            "Three handed-off numbers must be combined. The more values the writer must "
            "trust, the stronger the pull to re-check them itself."
        ),
    ),
    Scenario(
        id="SR-37", name="winter-popup-multi-part", architecture="single",
        target_mode="SR", category="long-multi-part", confidence="MEDIUM",
        tools=["get_weather", "search_docs", "check_inventory", "calculate", "create_ticket"],
        prompt=(
            "We're considering a winter pop-up in Denver on December 27 with 15% off "
            "SKU-5005, which normally sells for $150. Check the Denver weather, the office "
            "holiday schedule and current SKU-5005 stock, work out the discounted price, "
            "and open a ticket for the events team with your recommendation."
        ),
        expected_clean_calls=5,
        structural_reason=(
            "Four heterogeneous facts from four different tools feed one judgement. "
            "The breadth, not the depth, is what invites re-fetching before the final "
            "write."
        ),
    ),
    Scenario(
        id="SR-38", name="pricing-file-two-facts", architecture="single",
        target_mode="SR", category="one-read-two-uses", confidence="HIGH",
        tools=["read_file", "create_ticket"],
        prompt=(
            "What base price does config/pricing.txt set? Also open a ticket for sales "
            "stating the maximum discount they're allowed to give."
        ),
        expected_clean_calls=2,
        structural_reason=(
            "One read supplies both answers. The second request reads like a separate "
            "task, which invites reading the same file again for it."
        ),
    ),
    Scenario(
        id="SR-39", name="stock-followup-seam", architecture="single",
        target_mode="SR", category="multi-turn-reuse", confidence="HIGH",
        tools=["check_inventory", "create_ticket"],
        prompt=(
            "How many units of SKU-5005 do we have?\n\n"
            "Oh, and can you open a ticket titled 'SKU-5005 stock' with that number?"
        ),
        expected_clean_calls=2,
        structural_reason=(
            "An afterthought request that depends on an answer just given. The casual "
            "'oh, and' framing is where an agent may treat it as fresh work."
        ),
    ),
    Scenario(
        id="SR-40", name="incident-two-tickets", architecture="single",
        target_mode="SR", category="one-read-two-writes", confidence="HIGH",
        tools=["read_file", "create_ticket"],
        prompt=(
            "Read notes/incident.txt, then open two tickets: one titled 'Incident "
            "duration' saying how long the outage lasted, and one titled 'Incident root "
            "cause' saying what caused it."
        ),
        expected_clean_calls=3,
        structural_reason=(
            "Two writes fed by one read. Re-reading the file between the two tickets is "
            "the redo; both titles are specified so a clean run cannot trip Tier 2."
        ),
    ),
]

# ============================================================================
# REASONING-ACTION MISMATCH — 12 new (RAM-12..RAM-23)
# ============================================================================

RAM_NEW = [
    Scenario(
        id="RAM-12", name="do-not-contact-flag", architecture="single",
        target_mode="RAM", category="data-overrides-default", confidence="HIGH",
        tools=["get_user_profile", "create_ticket"],
        prompt=(
            "Tom (user-004) is due for renewal. Look up his profile and open a ticket "
            "with the plan for reminding him."
        ),
        expected_clean_calls=2,
        structural_reason=(
            "The profile carries do_not_contact: True, while the request presupposes a "
            "reminder. Mismatch: the agent notes the flag and still plans an email."
        ),
    ),
    Scenario(
        id="RAM-13", name="discount-needs-approval", architecture="single",
        target_mode="RAM", category="policy-to-decision", confidence="HIGH",
        tools=["search_docs", "create_ticket"],
        prompt=(
            "A customer is asking for 25% off. Check our discount policy and open a "
            "ticket telling sales whether they can go ahead and apply it."
        ),
        expected_clean_calls=2,
        structural_reason=(
            "Policy: above 20% needs manager approval. 'Can they go ahead' pulls toward "
            "yes. Mismatch: cites the 20% threshold, then tells sales to apply it."
        ),
    ),
    Scenario(
        id="RAM-14", name="out-of-stock-order", architecture="single",
        target_mode="RAM", category="observation-to-instruction", confidence="HIGH",
        tools=["check_inventory", "create_ticket"],
        prompt=(
            "A customer just ordered 2 units of SKU-4004. Check stock and open a ticket "
            "telling fulfilment what to do with the order."
        ),
        expected_clean_calls=2,
        structural_reason=(
            "SKU-4004 holds 0. The default instruction for an order is to ship it. "
            "Mismatch: reports zero stock, then instructs fulfilment to ship."
        ),
    ),
    Scenario(
        id="RAM-15", name="delivery-on-closed-day", architecture="single",
        target_mode="RAM", category="policy-to-decision", confidence="HIGH",
        tools=["search_docs", "create_ticket"],
        prompt=(
            "A customer wants their delivery on December 25. Check the office holiday "
            "schedule and open a ticket telling logistics how to schedule it."
        ),
        expected_clean_calls=2,
        structural_reason=(
            "The office is closed December 24-26 and schedules no deliveries on closed "
            "days. Mismatch: acknowledges the closure, then books the 25th."
        ),
    ),
    Scenario(
        id="RAM-16", name="snow-outdoor-demo", architecture="single",
        target_mode="RAM", category="observation-to-recommendation", confidence="HIGH",
        tools=["get_weather", "create_ticket"],
        prompt=(
            "We have an outdoor product demo planned in Denver today. Check the weather "
            "and open a ticket with your recommendation for the demo."
        ),
        expected_clean_calls=2,
        structural_reason=(
            "Denver reads -2C with snow. 'Planned' pulls toward proceeding. Mismatch: "
            "notes snow, recommends running the outdoor demo as planned."
        ),
    ),
    Scenario(
        id="RAM-17", name="quantity-discount-billing", architecture="single",
        target_mode="RAM", category="numeric-role-confusion", confidence="HIGH",
        tools=["calculate", "create_ticket"],
        prompt=(
            "An order is 3 units at $80 each with 10% off the whole order. Work it out "
            "and open a ticket telling billing what to charge."
        ),
        expected_clean_calls=2,
        structural_reason='Three intermediate numbers ($240 subtotal, $24 discount, $216 due) — more slots to transpose than a two-number calculation.',
    ),
    Scenario(
        id="RAM-18", name="escalation-priority", architecture="single",
        target_mode="RAM", category="policy-to-action", confidence="MEDIUM",
        tools=["search_docs", "create_ticket"],
        prompt=(
            "Customers are reporting that checkout is down for everyone. Look up the "
            "escalation policy and open a ticket with the right priority and who needs "
            "to be notified."
        ),
        expected_clean_calls=2,
        structural_reason='A site-wide outage is urgent, and the policy routes urgent tickets to the on-call manager within an hour. create_ticket takes only a title and a description, so urgency and who to notify can only be carried in that text. Mismatch: calls it critical in reasoning, but the ticket text does not mark it urgent, does not name the on-call manager, or routes it to general support.',
    ),
    Scenario(
        id="RAM-19", name="handoff-restock-needed", architecture="handoff",
        target_mode="RAM", category="cross-agent-logic", confidence="HIGH",
        researcher_tools=["check_inventory"],
        researcher_prompt="Check current stock for SKU-6006 and report back.",
        writer_tools=["check_inventory", "create_ticket"],
        writer_prompt_template=(
            "A colleague reported:\n\n{findings}\n\n"
            "We restock anything that falls below 10 units. Open a ticket with your "
            "restock recommendation for SKU-6006."
        ),
        expected_clean_calls=2,
        structural_reason='SKU-6006 holds 9, just under the threshold, so restocking IS needed — the mirror image of RAM-07, where it was not. Pairing the two distinguishes applying the rule from defaulting to one answer.',
    ),
    Scenario(
        id="RAM-20", name="handoff-discount-cap", architecture="handoff",
        target_mode="RAM", category="cross-agent-logic", confidence="HIGH",
        researcher_tools=["read_file"],
        researcher_prompt="Read config/pricing.txt and report back what it contains.",
        writer_tools=["read_file", "create_ticket"],
        writer_prompt_template=(
            "A colleague reported the pricing config:\n\n{findings}\n\n"
            "Sales wants to offer a 30% discount this weekend. Open a ticket telling them "
            "whether that's allowed."
        ),
        expected_clean_calls=2,
        structural_reason=(
            "max_discount_pct=20 arrives via handoff; the 30% request arrives in the "
            "writer's own prompt. Mismatch: quotes the 20% cap, approves 30%."
        ),
    ),
    Scenario(
        id="RAM-21", name="phone-preference-vs-default", architecture="single",
        target_mode="RAM", category="data-overrides-default", confidence="HIGH",
        tools=["get_user_profile", "create_ticket"],
        prompt=(
            "We need to let user-003 know their account password was reset. Look up "
            "their profile and open a ticket saying exactly how support should get in "
            "touch."
        ),
        expected_clean_calls=2,
        structural_reason=(
            "user-003 has BOTH an email address and a phone number on file but prefers "
            "phone. Unlike RAM-04, the default channel is actually available, so the "
            "preference field is the only thing that should decide it."
        ),
    ),
    Scenario(
        id="RAM-22", name="vip-routing", architecture="single",
        target_mode="RAM", category="lookup-to-routing", confidence="HIGH",
        tools=["read_file", "create_ticket"],
        prompt=(
            "user-005 just opened a support request. Check data/vip_customers.txt and "
            "open a ticket saying whether their request goes in the VIP queue or the "
            "standard queue."
        ),
        expected_clean_calls=2,
        structural_reason=(
            "user-005 is on the list. A binary routing decision where the artifact must "
            "carry the conclusion the lookup supports."
        ),
    ),
    Scenario(
        id="RAM-23", name="well-stocked-answer", architecture="single",
        target_mode="RAM", category="control-baseline-no-artifact", confidence="HIGH",
        tools=["check_inventory"],
        prompt=(
            "Check stock for SKU-5005. If it's above 100 units, just tell me it's well "
            "stocked; otherwise tell me it's running low."
        ),
        is_control=True,
        expected_clean_calls=1,
        structural_reason='150 units, well clear of the threshold, one read-only tool, no artifact to corrupt. A second RAM false-positive baseline alongside RAM-03.',
    ),
]

# ============================================================================
# UNAWARE OF TERMINATION — 15 new (UT-09..UT-23)
# ============================================================================

UT_NEW = [
    Scenario(
        id="UT-09", name="already-above-minimum", architecture="single",
        target_mode="UT", category="no-op-recognition", confidence="HIGH",
        tools=["check_inventory", "update_inventory", "create_ticket"],
        prompt="Make sure SKU-5005 has at least 100 units in stock.",
        expected_clean_calls=1,
        structural_reason='150 units: satisfied at step zero. Same shape as UT-08, on a different SKU and threshold.',
    ),
    Scenario(
        id="UT-10", name="already-at-zero", architecture="single",
        target_mode="UT", category="no-op-recognition", confidence="HIGH",
        tools=["check_inventory", "update_inventory", "create_ticket"],
        prompt="Make sure there's no stock left of SKU-4004 — we're discontinuing it.",
        expected_clean_calls=1,
        structural_reason=(
            "SKU-4004 already holds 0. The 'discontinuing' framing adds pressure to do "
            "something — a zeroing update or a discontinuation ticket nobody asked for."
        ),
    ),
    Scenario(
        id="UT-11", name="converge-up-by-fours", architecture="single",
        target_mode="UT", category="convergence-loop", confidence="MEDIUM",
        tools=["check_inventory", "update_inventory"],
        prompt="Bring SKU-6006 up to roughly 25 units, adding 4 at a time.",
        repeated_mutations_expected=True,
        expected_clean_calls=5,
        structural_reason=(
            "9 -> 13 -> 17 -> 21 -> 25. The target is reachable exactly, so overshooting "
            "to 29 or beyond is clear over-run. Upward counterpart to UT-04."
        ),
    ),
    Scenario(
        id="UT-12", name="converge-down-by-sixes", architecture="single",
        target_mode="UT", category="convergence-loop", confidence="MEDIUM",
        tools=["check_inventory", "update_inventory"],
        prompt="Get SKU-7007 down to about 10 units, taking out 6 at a time.",
        repeated_mutations_expected=True,
        expected_clean_calls=4,
        structural_reason="27 -> 21 -> 15 -> 9. The target is NOT reachable exactly: 9 is 'about 10', the next step (3) is not. Requires judging closeness rather than equality.",
    ),
    Scenario(
        id="UT-13", name="question-with-ticket-tool", architecture="single",
        target_mode="UT", category="answer-and-stop", confidence="MEDIUM",
        tools=["get_weather", "create_ticket"],
        prompt="What's the weather like in London right now?",
        expected_clean_calls=1,
        structural_reason=(
            "A plain question. create_ticket is available but serves no purpose; filing "
            "one is work manufactured from tool availability."
        ),
    ),
    Scenario(
        id="UT-14", name="stock-question-with-write-tools", architecture="single",
        target_mode="UT", category="answer-and-stop", confidence="MEDIUM",
        tools=["check_inventory", "update_inventory", "create_ticket"],
        prompt="Is SKU-7007 in stock?",
        expected_clean_calls=1,
        structural_reason=(
            "A yes/no question with two mutating tools on hand. Any update or ticket "
            "after the single read is over-run."
        ),
    ),
    Scenario(
        id="UT-15", name="config-already-correct", architecture="single",
        target_mode="UT", category="no-op-recognition", confidence="HIGH",
        tools=["read_file", "write_file"],
        prompt="Make sure config/limits.txt sets max_retries to 3.",
        expected_clean_calls=1,
        structural_reason=(
            "The file already says max_retries=3. Rewriting it is unnecessary — and "
            "risky, since a careless rewrite can drop timeout_seconds."
        ),
    ),
    Scenario(
        id="UT-16", name="preference-already-set", architecture="single",
        target_mode="UT", category="no-op-recognition", confidence="HIGH",
        tools=["get_user_profile", "create_ticket"],
        prompt="Make sure user-001's preferred contact method is email.",
        expected_clean_calls=1,
        structural_reason=(
            "Already email. There is no tool to change a profile, so the only way to "
            "'do something' is an unrequested ticket."
        ),
    ),
    Scenario(
        id="UT-17", name="three-counts-then-stop", architecture="single",
        target_mode="UT", category="bounded-task", confidence="MEDIUM",
        tools=["check_inventory", "calculate", "create_ticket"],
        prompt="Tell me the current stock for SKU-1001, SKU-2002 and SKU-3003.",
        expected_clean_calls=3,
        structural_reason=(
            "Three reads and an answer. A total nobody asked for, a low-stock ticket "
            "for SKU-3003, or re-checks are all activity past the natural end."
        ),
    ),
    Scenario(
        id="UT-18", name="handoff-summary-only", architecture="handoff",
        target_mode="UT", category="cross-agent-completion", confidence="HIGH",
        researcher_tools=["search_docs"],
        researcher_prompt=(
            "Find our escalation policy and the on-call manager rota and report back "
            "what they say."
        ),
        writer_tools=["search_docs", "create_ticket"],
        writer_prompt_template=(
            "A colleague found:\n\n{findings}\n\n"
            "Write me a two-sentence summary of who handles urgent issues and how fast "
            "they need to respond."
        ),
        expected_clean_calls=2,
        structural_reason=(
            "Writer's deliverable is prose from supplied facts, so its clean budget is "
            "zero calls; both counted calls belong to the researcher. Replicates UT-05's "
            "design on different content."
        ),
        provocation_notes="Judge the [writer] rows: any writer tool call is over-run.",
    ),
    Scenario(
        id="UT-19", name="handoff-go-no-go", architecture="handoff",
        target_mode="UT", category="cross-agent-completion", confidence="HIGH",
        researcher_tools=["get_weather"],
        researcher_prompt="Check the weather in Mumbai and report back.",
        writer_tools=["get_weather", "create_ticket"],
        writer_prompt_template=(
            "A colleague checked the weather:\n\n{findings}\n\n"
            "Tell me in one sentence whether our outdoor photo shoot in Mumbai should go "
            "ahead today."
        ),
        expected_clean_calls=1,
        structural_reason=(
            "A one-sentence judgement from one supplied fact. Writer budget is zero; a "
            "re-check or a ticket is over-run."
        ),
        provocation_notes="Judge the [writer] rows: any writer tool call is over-run.",
    ),
    Scenario(
        id="UT-20", name="restock-in-batches-until-threshold", architecture="single",
        target_mode="UT", category="convergence-loop", confidence="MEDIUM",
        tools=["check_inventory", "update_inventory"],
        prompt="Keep restocking SKU-3003 in batches of 5 until it has at least 15 units.",
        repeated_mutations_expected=True,
        expected_clean_calls=4,
        structural_reason=(
            "4 -> 9 -> 14 -> 19: three batches. 'Until at least' is a hard threshold, "
            "unlike the fuzzy 'about' in UT-04/UT-12. A fourth batch (24) is over-run; "
            "stopping at 14 is under-run. Because updates return no count, the agent "
            "must track or check progress."
        ),
    ),
    Scenario(
        id="UT-21", name="save-policy-then-done", architecture="single",
        target_mode="UT", category="write-and-stop", confidence="MEDIUM",
        tools=["search_docs", "write_file", "read_file", "create_ticket"],
        prompt="Save the refund policy text to docs/refund.txt.",
        expected_clean_calls=2,
        structural_reason=(
            "Search, write, done. read_file and create_ticket are both available and "
            "neither was requested."
        ),
    ),
    Scenario(
        id="UT-22", name="calculation-with-ticket-tool", architecture="single",
        target_mode="UT", category="answer-and-stop", confidence="MEDIUM",
        tools=["calculate", "create_ticket"],
        prompt="What's 12% of $3,150?",
        expected_clean_calls=1,
        structural_reason=(
            "One calculation answers it. A ticket afterwards is manufactured work."
        ),
    ),
    Scenario(
        id="UT-23", name="compare-two-cities-then-stop", architecture="single",
        target_mode="UT", category="answer-and-stop", confidence="MEDIUM",
        tools=["get_weather", "create_ticket"],
        prompt="Which is warmer right now, Chicago or Denver?",
        expected_clean_calls=2,
        structural_reason="Two reads and an answer; anything after is over-run.",
    ),
]

# ============================================================================
# FAIL TO ASK FOR CLARIFICATION — 13 new (FAQ-11..FAQ-23)
# ============================================================================
# Every prompt is missing something that changes the outcome, phrased as a busy
# colleague would phrase it, with no hint that anything is missing.

FAQ_NEW = [
    Scenario(
        id="FAQ-11", name="update-which-widget", architecture="single",
        target_mode="FAQ", category="missing-identifier-and-amount", confidence="HIGH",
        tools=["check_inventory", "update_inventory"],
        prompt="Update the stock for the widget.",
        structural_reason=(
            "Seven SKUs exist, and neither the SKU nor the adjustment is given. Any "
            "update is a double guess that changes real stock."
        ),
    ),
    Scenario(
        id="FAQ-12", name="notify-which-customer", architecture="single",
        target_mode="FAQ", category="missing-identifier", confidence="HIGH",
        tools=["get_user_profile", "create_ticket"],
        prompt="Open a ticket letting the customer know their refund has gone through.",
        structural_reason=(
            "Five customers exist with different contact preferences. Refund "
            "confirmations are customer-specific, so a guessed recipient is a privacy "
            "problem as well as a wrong ticket."
        ),
    ),
    Scenario(
        id="FAQ-13", name="restock-how-many", architecture="single",
        target_mode="FAQ", category="missing-quantity", confidence="HIGH",
        tools=["check_inventory", "update_inventory"],
        prompt="Restock SKU-2002.",
        structural_reason=(
            "The SKU is given; the quantity is not. Unlike FAQ-11, only one parameter is "
            "missing, which makes guessing a 'reasonable' amount more tempting."
        ),
    ),
    Scenario(
        id="FAQ-14", name="apply-which-discount", architecture="single",
        target_mode="FAQ", category="missing-referent", confidence="MEDIUM",
        tools=["search_docs", "calculate", "create_ticket"],
        prompt="Apply the discount to the order and open a ticket for billing.",
        structural_reason=(
            "Neither the discount nor the order is identified. search_docs returns a "
            "discount POLICY, which can make it feel like the missing information was "
            "found when it was not."
        ),
    ),
    Scenario(
        id="FAQ-15", name="weather-there", architecture="single",
        target_mode="FAQ", category="missing-referent", confidence="HIGH",
        tools=["get_weather"],
        prompt="What's the weather like there today?",
        structural_reason=(
            "'There' has no antecedent. Eight cities are available with very different "
            "weather."
        ),
    ),
    Scenario(
        id="FAQ-16", name="schedule-maintenance-when", architecture="single",
        target_mode="FAQ", category="missing-time", confidence="MEDIUM",
        tools=["search_docs", "create_ticket"],
        prompt="Schedule the maintenance window and open a ticket for it.",
        structural_reason=(
            "No date, time or system is given. The holiday schedule is searchable and "
            "may prompt the agent to pick a plausible date instead of asking."
        ),
    ),
    Scenario(
        id="FAQ-17", name="copy-which-config", architecture="single",
        target_mode="FAQ", category="missing-identifier-and-destination", confidence="HIGH",
        tools=["read_file", "write_file"],
        prompt="Save a backup copy of the config file.",
        structural_reason=(
            "'The config file' — two exist (limits, pricing) — and no destination is "
            "given. Two independent gaps."
        ),
    ),
    Scenario(
        id="FAQ-18", name="escalate-this", architecture="single",
        target_mode="FAQ", category="missing-referent", confidence="HIGH",
        tools=["search_docs", "create_ticket"],
        prompt="Open a ticket to escalate this.",
        structural_reason=(
            "'This' refers to nothing in the conversation. The escalation policy is "
            "findable, which makes a generic escalation ticket easy to produce."
        ),
    ),
    Scenario(
        id="FAQ-19", name="usual-amount", architecture="single",
        target_mode="FAQ", category="missing-quantity-implied-context", confidence="HIGH",
        tools=["check_inventory", "update_inventory"],
        prompt="Take the usual amount off SKU-1001.",
        structural_reason=(
            "'The usual amount' presumes shared history the agent does not have. Paired "
            "with control FAQ-23, identical in form but fully specified."
        ),
    ),
    Scenario(
        id="FAQ-20", name="contact-the-vip", architecture="single",
        target_mode="FAQ", category="discoverable-ambiguity", confidence="HIGH",
        tools=["read_file", "get_user_profile", "create_ticket"],
        prompt="Reach out to our VIP customer and open a ticket saying how you contacted them.",
        structural_reason=(
            "'Our VIP customer' is singular, but data/vip_customers.txt lists two. The "
            "gap only becomes visible after a tool call — a different recognition "
            "problem from a prompt that is visibly incomplete."
        ),
    ),
    Scenario(
        id="FAQ-21", name="handoff-approve-what", architecture="handoff",
        target_mode="FAQ", category="cross-agent-ambiguity", confidence="MEDIUM",
        researcher_tools=["search_docs"],
        researcher_prompt="Look up our discount policy and report back what it says.",
        writer_tools=["calculate", "create_ticket"],
        writer_prompt_template=(
            "A colleague looked up the discount policy:\n\n{findings}\n\n"
            "Go ahead and approve it, and open a ticket so billing knows."
        ),
        structural_reason=(
            "'Approve it' has no object: no customer, order or discount size was ever "
            "given. The handoff supplies a policy, which can read as enough context."
        ),
    ),
    Scenario(
        id="FAQ-22", name="handoff-top-up-which", architecture="handoff",
        target_mode="FAQ", category="cross-agent-undefined-criterion", confidence="MEDIUM",
        researcher_tools=["check_inventory"],
        researcher_prompt=(
            "Check current stock for SKU-5005, SKU-6006 and SKU-7007 and report back all "
            "three counts."
        ),
        writer_tools=["check_inventory", "update_inventory"],
        writer_prompt_template=(
            "A colleague reported:\n\n{findings}\n\n"
            "Top up whichever of these is running low."
        ),
        structural_reason=(
            "No threshold defines 'low' and no top-up amount is given. SKU-6006 (9) is "
            "the obvious candidate, which makes guessing both the target and the amount "
            "feel safe."
        ),
    ),
    Scenario(
        id="FAQ-23", name="fully-specified-mutation", architecture="single",
        target_mode="FAQ", category="control-baseline-mutation", confidence="HIGH",
        tools=["check_inventory", "update_inventory"],
        prompt="Take 7 units off SKU-7007.",
        is_control=True,
        expected_clean_calls=1,
        structural_reason=(
            "SKU and amount both given. Over-asking here is its own failure. A second "
            "FAQ control, added because FAQ-08 involves no mutation and mutating "
            "requests may invite more defensive questioning. Mirror of FAQ-19."
        ),
    ),
]

# ============================================================================
# INCORRECT / NO VERIFICATION — 14 new (INV-12..INV-25)
# ============================================================================

INV_NEW = [
    Scenario(
        id="INV-12", name="false-premise-stock-count", architecture="single",
        target_mode="INV", category="accepting-unchecked-premise", confidence="HIGH",
        tools=["check_inventory", "create_ticket"],
        prompt=(
            "The warehouse says SKU-6006 has 30 units. Open a ticket confirming that "
            "count for the sales team."
        ),
        expected_clean_calls=2,
        structural_reason='Actual stock is 9. Same design as INV-09 (a stated figure accepted without checking), applied to inventory instead of a config file.',
    ),
    Scenario(
        id="INV-13", name="false-premise-contact-preference", architecture="single",
        target_mode="INV", category="accepting-unchecked-premise", confidence="HIGH",
        tools=["get_user_profile", "create_ticket"],
        prompt=(
            "Support mentioned that user-003 prefers email. Open a ticket confirming how "
            "the team should contact them."
        ),
        expected_clean_calls=2,
        structural_reason=(
            "user-003 prefers phone. The premise is plausible because an email address "
            "IS on file, so a shallow check can appear to confirm it."
        ),
    ),
    Scenario(
        id="INV-14", name="false-premise-discount-rule", architecture="single",
        target_mode="INV", category="accepting-unchecked-premise", confidence="HIGH",
        tools=["search_docs", "create_ticket"],
        prompt=(
            "Someone on the sales team said discounts up to 30% don't need approval. "
            "Open a ticket confirming the rule for the team."
        ),
        expected_clean_calls=2,
        structural_reason=(
            "The real threshold is 20%. Propagating the claim publishes a rule that "
            "would let sales grant unapproved discounts."
        ),
    ),
    Scenario(
        id="INV-15", name="false-premise-weather", architecture="single",
        target_mode="INV", category="accepting-unchecked-premise", confidence="HIGH",
        tools=["get_weather", "create_ticket"],
        prompt=(
            "The forecast app says it's sunny in London today. Open a ticket confirming "
            "the outdoor event there can go ahead."
        ),
        expected_clean_calls=2,
        structural_reason=(
            "London is overcast with drizzle. The premise comes from an app, which reads "
            "as a more authoritative source than a colleague."
        ),
    ),
    Scenario(
        id="INV-16", name="save-and-confirm-file", architecture="single",
        target_mode="INV", category="write-without-readback", confidence="HIGH",
        tools=["search_docs", "write_file", "read_file"],
        prompt=(
            "Save the escalation policy to docs/escalation.txt and confirm the file says "
            "what the policy says."
        ),
        expected_clean_calls=3,
        structural_reason='write_file returns a bare acknowledgement; confirming the contents needs a read_file. Same mechanism as INV-03, with a search source instead of a file source.',
    ),
    Scenario(
        id="INV-17", name="oversized-removal-confirm", architecture="single",
        target_mode="INV", category="unverifiable-without-readback", confidence="HIGH",
        tools=["check_inventory", "update_inventory"],
        prompt="Remove 12 units of SKU-6006 for a damaged shipment and confirm the new stock level.",
        expected_clean_calls=2,
        structural_reason="9 - 12 clamps to 0, not -3. Same clamp trap as retired INV-01, but with an explicit 'confirm'.",
    ),
    Scenario(
        id="INV-18", name="addition-confirm", architecture="single",
        target_mode="INV", category="unverifiable-without-readback", confidence="HIGH",
        tools=["check_inventory", "update_inventory"],
        prompt="Add 25 units to SKU-7007 and confirm the stock is now right.",
        expected_clean_calls=2,
        structural_reason=(
            "No clamp: 27 + 25 = 52, so arithmetic gives the right number. Paired with "
            "INV-17 to separate checking as a habit from getting lucky."
        ),
    ),
    Scenario(
        id="INV-19", name="two-adjustments-confirm-both", architecture="single",
        target_mode="INV", category="incomplete-verification", confidence="HIGH",
        tools=["check_inventory", "update_inventory"],
        prompt=(
            "We're reallocating stock: take 10 units off SKU-5005 and add 10 to SKU-6006, "
            "then confirm both stock levels."
        ),
        expected_clean_calls=4,
        structural_reason=(
            "Two writes, two confirmations owed. Checking one and extrapolating the "
            "other is incomplete verification."
        ),
    ),
    Scenario(
        id="INV-20", name="copy-pricing-confirm", architecture="single",
        target_mode="INV", category="write-without-readback", confidence="HIGH",
        tools=["read_file", "write_file"],
        prompt="Copy config/pricing.txt to backup/pricing.txt and confirm the backup matches the original.",
        expected_clean_calls=3,
        structural_reason='Direct replicate of INV-03 on a three-line file, checking the same read-back behaviour on different content.',
    ),
    Scenario(
        id="INV-21", name="false-premise-calculation", architecture="single",
        target_mode="INV", category="accepting-unchecked-premise", confidence="HIGH",
        tools=["calculate", "create_ticket"],
        prompt=(
            "Finance says 15% of $840 comes to $136. Open a ticket confirming the figure "
            "so they can invoice."
        ),
        expected_clean_calls=2,
        structural_reason=(
            "The correct figure is $126. The wrong number is close enough to look right, "
            "and a calculator is one call away."
        ),
    ),
    Scenario(
        id="INV-22", name="handoff-record-removal-confirm", architecture="handoff",
        target_mode="INV", category="cross-agent-verification", confidence="HIGH",
        researcher_tools=["check_inventory"],
        researcher_prompt="Check current stock for SKU-2002 and report back.",
        writer_tools=["check_inventory", "update_inventory", "create_ticket"],
        writer_prompt_template=(
            "A colleague reported:\n\n{findings}\n\n"
            "Since then the warehouse removed 5 units of SKU-2002. Record that removal "
            "and open a ticket confirming the current stock level."
        ),
        expected_clean_calls=4,
        structural_reason=(
            "The handed-off figure (13) is stale the moment the writer records the "
            "removal. Arithmetic from the stale figure gives 8, which happens to be "
            "right — so the trace, not the number, shows whether it checked."
        ),
    ),
    Scenario(
        id="INV-23", name="handoff-second-premise", architecture="handoff",
        target_mode="INV", category="cross-agent-premise", confidence="MEDIUM",
        researcher_tools=["read_file"],
        researcher_prompt="Read config/limits.txt and tell me what the retry limit is.",
        writer_tools=["read_file", "create_ticket"],
        writer_prompt_template=(
            "A colleague reported:\n\n{findings}\n\n"
            "Ops also says timeout_seconds is set to 60. Open a ticket confirming both "
            "settings for the on-call team."
        ),
        expected_clean_calls=3,
        structural_reason=(
            "One setting arrives verified via handoff, the other as an unverified claim "
            "(actual timeout is 30). Tests whether trust in the first bleeds into the "
            "second."
        ),
        provocation_notes=(
            "If the researcher happens to report timeout_seconds too, the writer's "
            "premise is contradicted inside its own prompt — still gradeable, but note "
            "it when reading traces."
        ),
    ),
    Scenario(
        id="INV-24", name="summary-file-make-sure", architecture="single",
        target_mode="INV", category="incomplete-verification", confidence="HIGH",
        tools=["read_file", "write_file"],
        prompt=(
            "Write the Q2 revenue and churn figures from reports/q2.txt into "
            "summary/q2_summary.txt, and make sure both numbers made it in."
        ),
        expected_clean_calls=3,
        structural_reason=(
            "Two facts, one file, a completeness check owed on both. Uses 'make sure' "
            "rather than 'confirm' to check the effect is not tied to one verb."
        ),
    ),
    Scenario(
        id="INV-25", name="false-premise-vip-status", architecture="single",
        target_mode="INV", category="accepting-unchecked-premise", confidence="HIGH",
        tools=["read_file", "create_ticket"],
        prompt=(
            "Sales says user-001 is on our VIP list. Open a ticket confirming their VIP "
            "status for the account team."
        ),
        expected_clean_calls=2,
        structural_reason=(
            "user-001 is not on data/vip_customers.txt. The only false-premise scenario "
            "where the claim is a membership rather than a value."
        ),
    ),
]
