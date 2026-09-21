"""18 Step-Repetition provocation scenarios for the Phase 0 pilot.

Each scenario is either:
  - "single": one agent/node with a tool subset, single task prompt
      (mirrors LangGraph create_react_agent vs. a one-agent CrewAI crew)
  - "handoff": two phases — "researcher" (read-only tools) gathers info,
      "writer" (full tools) is handed the researcher's output and must act
      on it (mirrors a two-node LangGraph graph vs. a two-agent sequential
      CrewAI crew). This architecture specifically targets repetition that
      crosses an agent/node boundary, which single-agent traces cannot
      exhibit by construction.

Three scenarios (marked is_control=True) are NOT meant to provoke wasteful
repetition — they establish baseline/false-positive behavior and validate
that the grader doesn't over-flag legitimate repeated calls.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Scenario:
    id: str
    name: str
    architecture: str  # "single" | "handoff"
    category: str
    rationale: str
    tools: list[str] = field(default_factory=list)          # for "single"
    prompt: str = ""                                          # for "single"
    researcher_tools: list[str] = field(default_factory=list)  # for "handoff"
    researcher_prompt: str = ""                                # for "handoff"
    writer_tools: list[str] = field(default_factory=list)      # for "handoff"
    writer_prompt_template: str = ""  # "{findings}" is substituted with phase-1 output
    is_control: bool = False


ALL = [
    Scenario(
        id="SR-01",
        name="weather-then-followup",
        architecture="single",
        category="multi-turn reuse",
        tools=["get_weather"],
        prompt=(
            "Turn 1 — user: What's the current weather in Tokyo?\n"
            "Turn 2 — user: Great — given that weather, would you recommend I bring an "
            "umbrella? Answer using only what you already found in Turn 1, do not look "
            "up the weather again."
        ),
        rationale=(
            "A single fact is fetched once and must be reused for a follow-up judgment "
            "in the same conversation. There is zero new information need in turn 2, so "
            "any second get_weather('Tokyo') call is unambiguous wasted work."
        ),
    ),
    Scenario(
        id="SR-02",
        name="inventory-ticket",
        architecture="single",
        category="reuse in downstream action",
        tools=["check_inventory", "create_ticket"],
        prompt=(
            "Check the stock level for SKU-1001, then create a support ticket titled "
            "'Low stock review' whose description states the exact current stock count "
            "for SKU-1001 that you just retrieved."
        ),
        rationale=(
            "The number needed for the ticket description is already in context from "
            "the first call. A repetition-prone agent re-checks inventory immediately "
            "before writing the ticket instead of citing the value it already has."
        ),
    ),
    Scenario(
        id="SR-03",
        name="profile-notify",
        architecture="single",
        category="reuse in downstream action",
        tools=["get_user_profile", "create_ticket"],
        prompt=(
            "Look up the profile for user-001, then create a ticket titled "
            "'Preference confirmed' whose description restates their name and "
            "preferred contact method."
        ),
        rationale=(
            "Structurally identical to SR-02 with a different tool pair, to check "
            "whether the reuse-in-downstream-action trap is tool-specific or general."
        ),
    ),
    Scenario(
        id="SR-04",
        name="context-crowding-five-topics",
        architecture="single",
        category="context dilution",
        tools=["search_docs", "create_ticket"],
        prompt=(
            "Look up our documentation on each of these five topics, one search_docs "
            "call per topic: 'refund policy', 'shipping policy', 'warranty terms', "
            "'product spec sheet a100', 'product spec sheet b200'. Then, using ONLY "
            "what you already retrieved, write a one-paragraph summary comparing the "
            "warranty terms to the A100 spec sheet, and create a ticket titled "
            "'Warranty comparison' with that summary as the description."
        ),
        rationale=(
            "The two facts needed for the final step ('warranty terms', 'a100 spec') "
            "are the 3rd and 4th of five lookups, buried under later, irrelevant ones "
            "by the time they're needed again. Tests whether context volume alone "
            "(not ambiguity) causes re-lookup instead of recall."
        ),
    ),
    Scenario(
        id="SR-05",
        name="post-mutation-recheck-legitimate",
        architecture="single",
        category="control: legitimate re-check",
        tools=["check_inventory", "update_inventory", "create_ticket"],
        prompt=(
            "Check inventory for SKU-2002. Then reduce it by 5 units. Then check "
            "inventory for SKU-2002 again to confirm the new count before creating a "
            "ticket titled 'Inventory adjusted' with the confirmed new count."
        ),
        rationale=(
            "The second check_inventory('SKU-2002') call has identical tool+args to "
            "the first, but a mutating update_inventory call happened in between, so "
            "the world state genuinely changed. This is NOT wasteful repetition — it's "
            "included to validate that the grader's mutation-aware classifier correctly "
            "declines to flag it, unlike a naive raw-duplicate count."
        ),
        is_control=True,
    ),
    Scenario(
        id="SR-06",
        name="ambiguous-freshness-hedge",
        architecture="single",
        category="hedge-language priming",
        tools=["get_weather", "check_inventory"],
        prompt=(
            "Get the weather in Chicago and the current inventory for SKU-3003. Note "
            "that data can sometimes go stale, so use your best judgment about whether "
            "the information you have is still trustworthy before giving your final "
            "recommendation on whether to run an outdoor pop-up shop today."
        ),
        rationale=(
            "Primes uncertainty about data freshness without ever explicitly "
            "instructing a re-check. Tests whether hedge language alone is enough to "
            "nudge a model into re-fetching 'just in case', a softer and more "
            "realistic trap than an explicit repeat instruction."
        ),
    ),
    Scenario(
        id="SR-07",
        name="researcher-writer-handoff-spec",
        architecture="handoff",
        category="cross-agent handoff",
        researcher_tools=["search_docs", "check_inventory"],
        researcher_prompt=(
            "Research the A100 widget: search our docs for its spec sheet and check "
            "current inventory for SKU-1001. Report back a concise summary of what you "
            "found."
        ),
        writer_tools=["search_docs", "check_inventory", "create_ticket"],
        writer_prompt_template=(
            "A colleague already researched the A100 widget and reported these "
            "findings:\n\n{findings}\n\n"
            "Using ONLY those findings — do not repeat any research — write a "
            "one-paragraph product blurb for the A100 and create a ticket titled "
            "'A100 blurb ready' with the blurb as the description."
        ),
        rationale=(
            "The writer phase has full tool access (including the same tools the "
            "researcher used) but is explicitly told not to repeat research. This is "
            "the canonical inter-agent trust failure: does the second agent/node act "
            "on the handed-off summary, or independently re-derive it because it *can*?"
        ),
    ),
    Scenario(
        id="SR-08",
        name="researcher-writer-handoff-refund-faq",
        architecture="handoff",
        category="cross-agent handoff",
        researcher_tools=["search_docs"],
        researcher_prompt=(
            "Look up our refund policy and our shipping policy (two separate "
            "search_docs calls) and report back what each says."
        ),
        writer_tools=["search_docs", "write_file"],
        writer_prompt_template=(
            "A colleague already looked up our refund and shipping policies:\n\n"
            "{findings}\n\n"
            "Using only that research, draft a one-paragraph customer-facing FAQ "
            "answer covering both policies and write it to the file "
            "'faq/refunds.txt'."
        ),
        rationale=(
            "Same handoff trap as SR-07 with different content and a different final "
            "tool (write_file instead of create_ticket), to check whether the effect "
            "is domain/tool-specific or a general property of the handoff boundary."
        ),
    ),
    Scenario(
        id="SR-09",
        name="handoff-combine-two-numbers",
        architecture="handoff",
        category="cross-agent handoff + combination",
        researcher_tools=["check_inventory"],
        researcher_prompt=(
            "Check current inventory for both SKU-1001 and SKU-2002 and report back "
            "both counts."
        ),
        writer_tools=["check_inventory", "calculate", "create_ticket"],
        writer_prompt_template=(
            "A colleague already checked inventory and reported:\n\n{findings}\n\n"
            "Using only those two numbers, calculate their combined total and create "
            "a ticket titled 'Combined stock' with the total in the description. Do "
            "not re-check inventory."
        ),
        rationale=(
            "The writer must combine two specific numbers gathered by someone else "
            "rather than checking a single fact. Tests whether needing *two* handed-off "
            "values (vs. one, as in SR-07/08) increases the odds the writer falls back "
            "to re-deriving them itself."
        ),
    ),
    Scenario(
        id="SR-10",
        name="explicit-no-recheck-multi-clause",
        architecture="single",
        category="explicit prohibition (long)",
        tools=["search_docs", "calculate", "write_file"],
        prompt=(
            "First, look up the shipping policy. Second, look up the refund policy. "
            "Third, calculate 15% of $84.50 (write the expression as 0.15*84.50). "
            "Fourth, write a file 'summary.txt' containing all three pieces of "
            "information you already gathered in steps one through three — the "
            "shipping policy text, the refund policy text, and the calculated value. "
            "Do not look anything up or calculate anything again for step four."
        ),
        rationale=(
            "A direct, explicit, multi-clause 'do not repeat' instruction. Tests "
            "whether repetition still occurs even when directly forbidden — if so, "
            "that points to a structural memory/state-tracking failure rather than "
            "an instruction-following gap, which is the more interesting finding."
        ),
    ),
    Scenario(
        id="SR-11",
        name="conditional-branch-recheck",
        architecture="single",
        category="branch-then-reuse",
        tools=["check_inventory", "calculate", "create_ticket"],
        prompt=(
            "Check inventory for SKU-3003. If it's below 5 units, calculate how many "
            "more are needed to reach 20, and create a ticket requesting that many "
            "more units, with the description referencing the current count you found."
        ),
        rationale=(
            "SKU-3003 starts at 4 units (below the threshold), forcing the branch to "
            "be taken. Tests whether, after branching, the agent re-checks inventory "
            "'to be sure' before writing the ticket instead of reusing the count=4 it "
            "already has."
        ),
    ),
    Scenario(
        id="SR-12",
        name="self-doubt-calc-redo",
        architecture="single",
        category="reuse across intervening step",
        tools=["calculate", "search_docs"],
        prompt=(
            "Calculate a 15% tip on $84.50 (write the expression as 0.15*84.50). Then "
            "look up the service charge policy. Then, taking the service charge policy "
            "into account, state the final total the customer owes, showing your work "
            "using the tip amount you already calculated."
        ),
        rationale=(
            "The calculation result from step 1 must be reused in step 3's reasoning "
            "after an intervening, unrelated tool call. Tests whether 'showing your "
            "work' language nudges the agent into recomputing the identical expression "
            "instead of citing the earlier result."
        ),
    ),
    Scenario(
        id="SR-13",
        name="explicit-no-recheck-short",
        architecture="single",
        category="explicit prohibition (short)",
        tools=["get_user_profile", "create_ticket"],
        prompt=(
            "Look up user-002's profile once. Then create a ticket titled 'Contact "
            "preference logged' whose description states their name and preferred "
            "contact method, without looking up their profile again."
        ),
        rationale=(
            "A short, single-clause counterpart to SR-10's longer prohibition, on a "
            "shorter task. Comparing SR-10 vs SR-13 checks whether prohibition "
            "violations correlate with task/instruction length and complexity."
        ),
    ),
    Scenario(
        id="SR-14",
        name="file-read-then-combine",
        architecture="single",
        category="combine two prior reads",
        tools=["read_file", "create_ticket"],
        prompt=(
            "Read the file 'notes/meeting.txt'. Then read the file "
            "'config/limits.txt'. Then create a ticket titled 'Q3 checklist' whose "
            "description combines the Q3 priorities from the meeting notes with the "
            "max_retries value from the config file — both of which you already read "
            "above."
        ),
        rationale=(
            "Two distinct, unrelated prior reads must both be recalled and combined "
            "into one new artifact — a higher combination load than the single-fact "
            "reuse scenarios (SR-02/03), which tests whether recall failures scale "
            "with how many distinct earlier results must be held at once."
        ),
    ),
    Scenario(
        id="SR-15",
        name="handoff-file-no-reread",
        architecture="handoff",
        category="cross-agent handoff + explicit prohibition",
        researcher_tools=["read_file"],
        researcher_prompt=(
            "Read the file 'notes/meeting.txt' and summarize the Q3 priorities you "
            "find in it."
        ),
        writer_tools=["read_file", "write_file", "create_ticket"],
        writer_prompt_template=(
            "A colleague already read the meeting notes and summarized the Q3 "
            "priorities:\n\n{findings}\n\n"
            "Using that summary — do not re-read the file — write the Q3 priorities "
            "to a new file 'reports/q3_summary.txt' and create a ticket titled 'Q3 "
            "report filed'."
        ),
        rationale=(
            "Combines the handoff trap (SR-07/08/09) with an explicit prohibition "
            "(SR-10/13) in one scenario, crossing an agent/node boundary. Checks "
            "whether explicit prohibitions hold up worse once they must survive being "
            "handed from one agent/node to another rather than staying within one "
            "agent's own context."
        ),
    ),
    Scenario(
        id="SR-16",
        name="compound-no-recheck-decision",
        architecture="single",
        category="explicit prohibition + combination",
        tools=["get_weather", "check_inventory"],
        prompt=(
            "Get the weather in Austin and check inventory for SKU-1001. Based on "
            "both, and without checking either again, write one sentence recommending "
            "whether to run an outdoor promotional event today, referencing the "
            "specific weather and stock numbers you found."
        ),
        rationale=(
            "A compound version of SR-01/SR-02/SR-14: two different facts, an "
            "explicit no-recheck instruction, and a judgment call that must cite both "
            "specific values from memory rather than re-deriving them."
        ),
    ),
    Scenario(
        id="SR-17",
        name="control-trivial-single-call",
        architecture="single",
        category="control: baseline / false-positive rate",
        tools=["calculate"],
        prompt="What is 12 * 7? Use the calculate tool to get the answer, then state it.",
        rationale=(
            "Trivial single-tool-call task with no legitimate reason for any "
            "repetition whatsoever. Establishes each framework's noise floor — if a "
            "framework redundantly repeats even this, the issue is not "
            "scenario-specific priming but a base tool-calling instability."
        ),
        is_control=True,
    ),
    Scenario(
        id="SR-18",
        name="control-two-independent-facts",
        architecture="single",
        category="control: baseline / false-positive rate",
        tools=["get_weather"],
        prompt=(
            "Look up the weather in Paris and the weather in Chicago (two different "
            "cities, two separate calls), then state both."
        ),
        rationale=(
            "Two DIFFERENT tool calls (different args) that must each legitimately "
            "happen exactly once — no reuse pressure, no ambiguity, no 'already "
            "gathered' framing. A second baseline distinct from SR-17's pure-arithmetic "
            "control, isolating whether making multiple calls in one task alone (with "
            "no repetition demand at all) introduces noise."
        ),
        is_control=True,
    ),
]

BY_ID = {s.id: s for s in ALL}
