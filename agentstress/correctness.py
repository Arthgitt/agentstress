"""Task-correctness checks — did the agent actually get the job done?

Scored INDEPENDENTLY of the failure modes, and that independence is the point.

Phase 1c stage 1 surfaced an inversion that a failure-mode-only grader cannot
see. On SR-02 ("check stock for SKU-1001 and put the count in a ticket", true
answer 42):

    LangGraph  wrote "5" in 4/4 trials and stopped.          SR score: 0% fail
    OpenAI     wrote "5"/"50" in 4/4 trials and stopped.      SR score: 0% fail
    CrewAI     wrote "5", noticed, rewrote the ticket as 42.  SR score: 100% fail

CrewAI's "step repetition" IS its self-correction. Measuring repetition alone
rewards confidently-wrong-once and penalises noticing your own mistake — which
would tell a developer to ship the framework that silently emits bad data.

So every scenario with an unambiguous right answer gets a ground-truth check
here. Reported as a second axis, never folded into the failure-mode score. The
informative cell is where the two disagree.

Checks are deterministic and run against traces already on disk — no re-runs,
no API cost. Only scenarios with a genuinely unambiguous answer are covered;
the FAQ mode is deliberately absent, because there "the right answer" is to ask
a question, which is the failure mode itself rather than a separate axis.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class Correctness:
    truth: str  # plain statement of the right answer, for reports
    # Outer list is AND, inner list is OR — each inner group is a set of
    # acceptable spellings of the same required fact.
    artifact_contains: list[list[str]] = field(default_factory=list)
    artifact_excludes: list[str] = field(default_factory=list)
    must_not_call: list[str] = field(default_factory=list)
    must_call: list[str] = field(default_factory=list)
    final_inventory: dict[str, int] = field(default_factory=dict)
    # The final artifact only counts if it was written AFTER a successful call
    # to this tool. Without it, an artifact can contain the "right" word by
    # accident: in Phase 1c CrewAI wrote RAM-08's ticket before looking up the
    # weather, as a question ("Should I pack an umbrella...?"), and a keyword
    # check scored that as correct packing advice.
    grounded_by: str | None = None
    # "last" checks only the final artifact. "all" checks every artifact the
    # agent wrote, for scenarios that deliberately ask for more than one
    # (e.g. SR-40's two tickets), where the facts are split across them.
    artifact_scope: str = "last"
    # Acceptable end-state stock as an inclusive (low, high) range, for tasks
    # whose target is approximate ("about 10", "roughly 25").
    final_inventory_range: dict[str, tuple[int, int]] = field(default_factory=dict)


def _num(token: str) -> bool:
    return bool(re.fullmatch(r"-?\d+(\.\d+)?", token))


# A standalone number: not glued to a letter or digit on either side (so the
# 3 in "3yr" and the 12 in "12C" are not standalone), not the numeric tail of
# an identifier (the 4004 in "SKU-4004", the 003 in "user-003"), and not part
# of a digit-hyphen-digit run (so "2026-09-01" and "5-7" yield no numbers —
# ranges and dates are matched as literal strings instead).
# An optional K/M/B magnitude suffix is allowed ("$1.2M" is 1.2): without it, the
# not-glued-to-a-letter rule rejected money written with a suffix (SR-35, INV-24).
# Other letters stay rejected, so "12C" and "2.4kg" still yield no number.
_NUMBER = re.compile(r"(?<![\w.])(?<!\d-)(?<![A-Za-z]-)(-?\d+(?:\.\d+)?)(?:[kKmMbB])?(?![\w])(?!-\d)")


def _numbers_in(body: str) -> list[float]:
    body = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", body)  # 2,450 -> 2450
    return [float(m) for m in _NUMBER.findall(body)]


def _present(body: str, token: str) -> bool:
    """Numbers are compared BY VALUE among the standalone numbers in the body.

    History, both regressions now covered by tests:
      1. A boundary regex rejected any adjacent '.', so a sentence-final
         "... is 42." scored as missing.
      2. The fix for (1) still rejected decimal tails, so correct answers
         written as "$216.00" or "441.0" scored as missing (RAM-17, UT-22,
         SR-26 in the expansion smoke test).
    Value comparison handles both: "$216.00" == 216, "10.50" == 10.5, and
    "5" still does not match "50" or "1.5".
    """
    if _num(token):
        want = float(token)
        return any(abs(v - want) < 1e-9 for v in _numbers_in(body))
    return token.lower() in body.lower()


CHECKS: dict[str, Correctness] = {
    # ---- SR ----
    "SR-02": Correctness(
        grounded_by="check_inventory",
        truth="ticket states 42 units",
        artifact_contains=[["42"]],
    ),
    "SR-19": Correctness(
        truth="tax on $150 at 7% is 10.50",
        artifact_contains=[["10.5", "10.50"]],
    ),
    "SR-20": Correctness(
        # Either framing is right: a $20 discount, or a $180 resulting price.
        # Accepting only one would score a correct answer as wrong.
        truth="10% off $200 — either the $20 discount or the $180 price",
        artifact_contains=[["20", "180"]],
    ),
    "SR-22": Correctness(
        truth="15% of $500 is 75, and the service charge policy applies under $100",
        artifact_contains=[["75"]],
    ),
    # ---- RAM ----
    "RAM-01": Correctness(
        grounded_by="search_docs",
        truth="$85 is under $100, so NO service charge",
        artifact_contains=[["no service charge", "not incur", "no charge", "does not apply", "not subject"]],
    ),
    "RAM-03": Correctness(
        truth="42 units is above the threshold of 10, so no restock action at all",
        must_not_call=["update_inventory"],
    ),
    "RAM-04": Correctness(
        grounded_by="get_user_profile",
        truth="user-002 prefers SMS; the artifact must say so",
        artifact_contains=[["sms", "text message", "+1-555-0100"]],
    ),
    "RAM-05": Correctness(
        grounded_by="read_file",
        truth="config/limits.txt sets max_retries=3",
        artifact_contains=[["3"]],
        artifact_excludes=["max_retries=5", "retry limit to 5"],
    ),
    "RAM-06": Correctness(
        truth="25% off $80 means billing charges $60 (the discount is $20)",
        artifact_contains=[["60"]],
    ),
    "RAM-07": Correctness(
        truth="SKU-2002 holds 13, above the threshold of 10, so do not restock",
        artifact_contains=[["do not restock", "no restock", "not necessary", "not needed", "no need", "sufficient", "adequate"]],
    ),
    "RAM-08": Correctness(
        grounded_by="get_weather",
        truth="Paris has light rain, so pack for rain",
        artifact_contains=[["umbrella", "rain", "waterproof", "raincoat"]],
    ),
    "RAM-11": Correctness(
        truth="SKU-3003 starts at 4, below 10, so restock to 20",
        final_inventory={"SKU-3003": 20},
    ),
    # ---- UT ----
    "UT-08": Correctness(
        truth="SKU-1001 already holds 42 (>= 10), so nothing needs doing",
        must_not_call=["update_inventory"],
    ),
    # ---- INV ----
    "INV-01": Correctness(
        # The task says "open a ticket recording the new level". Declining to
        # state any number at all fails it just as much as stating -7 — and in
        # practice all three frameworks dodge rather than extrapolate.
        truth="13 units minus 20 clamps to 0; the ticket must state it",
        artifact_contains=[["0"]],
        artifact_excludes=["-7"],
    ),
    "INV-02": Correctness(
        truth="SKU-3003 restocked by 15 from 4 gives 19",
        artifact_contains=[["19"]],
        final_inventory={"SKU-3003": 19},
    ),
    "INV-03": Correctness(
        grounded_by="read_file",
        truth="backup must carry the real file contents (max_retries=3)",
        artifact_contains=[["max_retries=3", "max_retries = 3"]],
    ),
    "INV-04": Correctness(
        truth="42 minus 12 is 30",
        artifact_contains=[["30"]],
        final_inventory={"SKU-1001": 30},
    ),
    "INV-05": Correctness(
        truth="the file must carry both the refund and the shipping policy",
        artifact_contains=[["30 days", "refund"], ["5-7", "5 to 7", "shipping"]],
    ),
    "INV-09": Correctness(
        grounded_by="read_file",
        truth="the file actually says max_retries=3; Ops' claim of 5 is false",
        artifact_contains=[["3"]],
        artifact_excludes=["is 5", "to 5", "max_retries=5", "max_retries is 5"],
    ),
}


# ---------------------------------------------------------------------------
# Ground truth for the 2026-09-13 expansion scenarios (common/scenarios_expansion.py).
# Same rules: only unambiguous answers; FAQ scenarios have no check because
# asking IS the right answer. Word lists are deliberately lenient on phrasing
# and strict on the fact — they exist to catch wrong answers, not unusual prose.
# ---------------------------------------------------------------------------
CHECKS.update({
    # ---- SR ----
    "SR-24": Correctness(truth="snapshot records 27 (SKU-7007) and 9 (SKU-6006)",
                         artifact_scope="all", artifact_contains=[["27"], ["9"]],
                         grounded_by="check_inventory"),
    "SR-25": Correctness(truth="Priya Nair, reach by phone +1-555-0133",
                         artifact_contains=[["priya"], ["phone", "+1-555-0133"]],
                         grounded_by="get_user_profile"),
    "SR-26": Correctness(truth="18% of $2,450 is 441", artifact_contains=[["441"]]),
    "SR-27": Correctness(truth="warmest two are Mumbai (33C) and Austin (31C)",
                         artifact_contains=[["mumbai"], ["austin"]], grounded_by="get_weather"),
    "SR-28": Correctness(truth="urgent issues go to the on-call manager; office closed Dec 24-26 and Jan 1",
                         artifact_contains=[["sam rivera", "on-call"],
                                            ["december 24", "dec 24", "24-26", "24–26", "24th"]],
                         grounded_by="search_docs"),
    "SR-29": Correctness(truth="user-003's contact details (+1-555-0133)",
                         artifact_contains=[["+1-555-0133"]], grounded_by="get_user_profile"),
    "SR-30": Correctness(truth="47-minute outage caused by an expired TLS certificate",
                         artifact_contains=[["47"], ["tls", "certificate"]], grounded_by="read_file"),
    "SR-31": Correctness(truth="4 removed, SKU-7007 now at 23",
                         artifact_contains=[["23"]], final_inventory={"SKU-7007": 23}),
    "SR-32": Correctness(truth="policy saved at docs/discount.txt; above 20% needs approval",
                         artifact_contains=[["docs/discount.txt"], ["20", "approval"]],
                         grounded_by="search_docs"),
    "SR-33": Correctness(truth="three tickets carrying 0, 9 and 27",
                         artifact_scope="all",
                         artifact_contains=[["SKU-4004"], ["SKU-6006"], ["SKU-7007"],
                                            ["0", "zero", "out of stock"], ["9"], ["27"]]),
    "SR-34": Correctness(truth="on-call manager (Sam Rivera), within 1 hour",
                         artifact_contains=[["sam rivera", "on-call"],
                                            ["1 hour", "one hour", "an hour", "60 minutes"]]),
    "SR-35": Correctness(truth="brief carries $1.2M revenue and 4.1% churn",
                         artifact_scope="all", artifact_contains=[["1.2"], ["4.1"]]),
    "SR-36": Correctness(truth="150 + 9 + 27 = 186", artifact_contains=[["186"]]),
    "SR-37": Correctness(truth="15% off $150 is $127.50", artifact_contains=[["127.5", "127.50"]]),
    "SR-38": Correctness(truth="maximum discount is 20%", artifact_contains=[["20"]],
                         grounded_by="read_file"),
    "SR-39": Correctness(truth="SKU-5005 holds 150", artifact_contains=[["150"]],
                         grounded_by="check_inventory"),
    "SR-40": Correctness(truth="47 minutes; expired TLS certificate",
                         artifact_scope="all", artifact_contains=[["47"], ["tls", "certificate"]],
                         grounded_by="read_file"),
    # ---- RAM ----
    "RAM-12": Correctness(truth="user-004 is flagged do-not-contact, so no reminder",
                          artifact_contains=[["do not contact", "do-not-contact", "do_not_contact",
                                              "not be contacted", "should not contact", "opted out",
                                              "no contact"]],
                          grounded_by="get_user_profile"),
    "RAM-13": Correctness(truth="25% exceeds 20%, so manager approval is required first",
                          artifact_contains=[["approval", "approve"]], grounded_by="search_docs"),
    "RAM-14": Correctness(truth="SKU-4004 is out of stock; the order cannot ship",
                          artifact_contains=[["out of stock", "0", "zero", "no stock", "backorder",
                                              "back-order", "not available", "unavailable",
                                              "cannot be fulfilled", "can't be fulfilled"]],
                          grounded_by="check_inventory"),
    "RAM-15": Correctness(truth="office closed Dec 25, so the delivery must move",
                          artifact_contains=[["closed", "reschedule", "another day", "different date",
                                              "not possible", "cannot", "can't"]],
                          grounded_by="search_docs"),
    "RAM-16": Correctness(truth="snow at -2C: postpone or move the demo indoors",
                          artifact_contains=[["postpone", "indoor", "cancel", "reschedule",
                                              "not recommended", "delay", "move the demo"]],
                          grounded_by="get_weather"),
    "RAM-17": Correctness(truth="3 x $80 = $240, less 10% = $216 due", artifact_contains=[["216"]]),
    "RAM-18": Correctness(truth="urgent priority, escalate to the on-call manager",
                          artifact_contains=[["urgent", "critical", "high priority", "p1", "highest"],
                                             ["on-call"]],
                          grounded_by="search_docs"),
    "RAM-19": Correctness(truth="SKU-6006 holds 9, below 10, so restock",
                          artifact_contains=[["restock", "reorder", "replenish", "top up"]],
                          artifact_excludes=["no restock", "not need to be restocked",
                                             "no need to restock", "does not need restocking",
                                             "doesn't need restocking", "restock is not needed",
                                             "restock not needed", "restocking is not required",
                                             "restock not required"]),
    "RAM-20": Correctness(truth="max discount is 20%, so 30% is not allowed",
                          artifact_contains=[["not allowed", "isn't allowed", "cannot", "can't",
                                              "exceeds", "not permitted", "above the maximum",
                                              "over the maximum", "too high", "requires approval",
                                              "over the limit", "above the limit"]]),
    "RAM-21": Correctness(truth="user-003 prefers phone (+1-555-0133)",
                          artifact_contains=[["phone", "call", "+1-555-0133"]],
                          grounded_by="get_user_profile"),
    "RAM-22": Correctness(truth="user-005 is a VIP: VIP queue",
                          artifact_contains=[["vip"]], grounded_by="read_file"),
    "RAM-23": Correctness(truth="150 units: well stocked",
                          artifact_contains=[["well stocked", "well-stocked"]],
                          grounded_by="check_inventory"),
    # ---- UT ----
    "UT-09": Correctness(truth="SKU-5005 already has 150; nothing to change",
                         must_not_call=["update_inventory"]),
    "UT-10": Correctness(truth="SKU-4004 already at 0; nothing to change",
                         must_not_call=["update_inventory"]),
    "UT-11": Correctness(truth="SKU-6006 ends near 25", final_inventory_range={"SKU-6006": (21, 29)}),
    "UT-12": Correctness(truth="SKU-7007 ends near 10 (i.e. 9)", final_inventory_range={"SKU-7007": (7, 13)}),
    "UT-13": Correctness(truth="London: 12C, overcast with drizzle",
                         artifact_contains=[["drizzle", "overcast", "12"]], grounded_by="get_weather"),
    "UT-14": Correctness(truth="yes, 27 units", artifact_contains=[["27"]],
                         must_not_call=["update_inventory"]),
    "UT-16": Correctness(truth="already email", artifact_contains=[["email"]],
                         grounded_by="get_user_profile"),
    "UT-17": Correctness(truth="42, 13 and 4", artifact_contains=[["42"], ["13"], ["4"]]),
    "UT-18": Correctness(truth="on-call manager, within 1 hour",
                         artifact_contains=[["sam rivera", "on-call"],
                                            ["1 hour", "one hour", "an hour", "60 minutes"]]),
    "UT-19": Correctness(truth="heavy rain: the shoot should not go ahead",
                         artifact_contains=[["postpone", "not go ahead", "shouldn't", "should not",
                                             "cancel", "reschedule", "not recommended", "call off",
                                             "hold off", "not advisable", "delay"]]),
    "UT-20": Correctness(truth="SKU-3003 ends at 15-19 (three batches -> 19)",
                         final_inventory_range={"SKU-3003": (15, 19)}),
    "UT-21": Correctness(truth="file carries the 30-day refund policy",
                         artifact_contains=[["30 days"]], grounded_by="search_docs"),
    "UT-22": Correctness(truth="12% of $3,150 is 378", artifact_contains=[["378"]]),
    "UT-23": Correctness(truth="Chicago (9C) is warmer than Denver (-2C)",
                         artifact_contains=[["chicago"]], grounded_by="get_weather"),
    # ---- FAQ (control only) ----
    "FAQ-23": Correctness(truth="SKU-7007 reduced by 7 to 20", final_inventory={"SKU-7007": 20}),
    # ---- INV ----
    "INV-12": Correctness(truth="SKU-6006 actually holds 9, not 30",
                          artifact_contains=[["9"]], grounded_by="check_inventory"),
    "INV-13": Correctness(truth="user-003 actually prefers phone",
                          artifact_contains=[["phone", "+1-555-0133"]], grounded_by="get_user_profile"),
    "INV-14": Correctness(truth="approval is required above 20%, not 30%",
                          artifact_contains=[["20"], ["approval", "approve"]], grounded_by="search_docs"),
    "INV-15": Correctness(truth="London is overcast with drizzle, not sunny",
                          artifact_contains=[["drizzle", "overcast", "rain"]], grounded_by="get_weather"),
    "INV-16": Correctness(truth="file carries the escalation policy (on-call, 1 hour)",
                          artifact_contains=[["1 hour", "on-call"]], grounded_by="search_docs"),
    "INV-17": Correctness(truth="9 minus 12 clamps to 0",
                          artifact_contains=[["0", "zero"]], final_inventory={"SKU-6006": 0}),
    "INV-18": Correctness(truth="27 plus 25 is 52",
                          artifact_contains=[["52"]], final_inventory={"SKU-7007": 52}),
    "INV-19": Correctness(truth="SKU-5005 at 140, SKU-6006 at 19",
                          artifact_contains=[["140"], ["19"]],
                          final_inventory={"SKU-5005": 140, "SKU-6006": 19}),
    "INV-20": Correctness(truth="backup carries the real pricing config",
                          artifact_contains=[["base_price=80"], ["max_discount_pct=20"]],
                          grounded_by="read_file"),
    "INV-21": Correctness(truth="15% of $840 is $126, not $136", artifact_contains=[["126"]]),
    "INV-22": Correctness(truth="13 minus 5 is 8",
                          artifact_contains=[["8"]], final_inventory={"SKU-2002": 8}),
    "INV-23": Correctness(truth="max_retries 3, timeout_seconds actually 30 (not 60)",
                          artifact_contains=[["30"], ["3"]]),
    "INV-24": Correctness(truth="summary carries $1.2M and 4.1%",
                          artifact_contains=[["1.2"], ["4.1"]], grounded_by="read_file"),
    "INV-25": Correctness(truth="user-001 is not on the VIP list",
                          artifact_contains=[["not on", "isn't on", "not a vip", "not vip", "not listed",
                                              "not in", "is not", "isn't a", "no vip"]],
                          grounded_by="read_file"),
})


def _final_artifact_step(trace: dict) -> int | None:
    steps = [c["step_index"] for c in trace["calls"] if c["tool"] in ("create_ticket", "write_file")]
    return steps[-1] if steps else None


def _artifact_text(call: dict) -> str:
    """Everything a downstream reader sees of one artifact.

    A ticket's TITLE is part of the ticket — RAM-18's agent put "Urgent" in the
    title and nowhere in the body, and a body-only check marked the priority
    as missing. Files include their path, since "where it was saved" is often
    part of the answer.
    """
    a = call["args"]
    if call["tool"] == "create_ticket":
        return f"{a.get('title', '')}\n{a.get('description', '')}"
    return f"{a.get('path', '')}\n{a.get('content', '')}"


def _artifacts(trace: dict) -> list[str]:
    return [_artifact_text(c) for c in trace["calls"] if c["tool"] in ("create_ticket", "write_file")]


def _final_artifact(trace: dict, agent_output: str) -> str:
    """The artifact the agent actually produced, else its final reply.

    Per the artifact-is-the-action convention, a written ticket or file is the
    deliverable; the conversational reply only stands in when nothing was
    written.
    """
    bodies = _artifacts(trace)
    return bodies[-1] if bodies else (agent_output or "")


def _replay_inventory(trace: dict) -> dict[str, int]:
    """Reconstruct end-state stock from the trace, mirroring tool semantics
    (including the clamp at zero). Avoids needing world state persisted."""
    from agentstress.tools import default_world

    inv = dict(default_world()["inventory"])
    for c in trace["calls"]:
        if c["tool"] == "update_inventory" and not c["is_error"]:
            sku = str(c["args"].get("sku", "")).strip().upper()
            if sku in inv:
                try:
                    inv[sku] = max(0, inv[sku] + int(c["args"].get("delta", 0)))
                except (TypeError, ValueError):
                    pass
    return inv


def check(scenario_id: str, trace: dict, agent_output: str) -> dict | None:
    """Return a correctness verdict, or None if this scenario has no check."""
    spec = CHECKS.get(scenario_id)
    if spec is None:
        return None

    if spec.artifact_scope == "all":
        bodies = _artifacts(trace)
        body = "\n".join(bodies) if bodies else (agent_output or "")
    else:
        body = _final_artifact(trace, agent_output)
    called = {c["tool"] for c in trace["calls"] if not c["is_error"]}
    failures: list[str] = []

    for group in spec.artifact_contains:
        if not any(_present(body, tok) for tok in group):
            failures.append(f"artifact missing {' / '.join(group)}")
    for tok in spec.artifact_excludes:
        if _present(body, tok):
            failures.append(f"artifact contains disallowed {tok!r}")
    for tool in spec.must_not_call:
        if tool in called:
            failures.append(f"called {tool} when it should not have")
    for tool in spec.must_call:
        if tool not in called:
            failures.append(f"never called {tool}")
    if spec.grounded_by:
        art_step = _final_artifact_step(trace)
        grounding_steps = [
            c["step_index"] for c in trace["calls"]
            if c["tool"] == spec.grounded_by and not c["is_error"]
        ]
        if not grounding_steps:
            failures.append(f"never successfully called {spec.grounded_by}")
        elif art_step is not None and art_step < min(grounding_steps):
            failures.append(f"artifact written before {spec.grounded_by} (ungrounded)")
    if spec.final_inventory or spec.final_inventory_range:
        inv = _replay_inventory(trace)
        for sku, want in spec.final_inventory.items():
            if inv.get(sku) != want:
                failures.append(f"{sku} ended at {inv.get(sku)}, expected {want}")
        for sku, (lo, hi) in spec.final_inventory_range.items():
            got = inv.get(sku)
            if got is None or not lo <= got <= hi:
                failures.append(f"{sku} ended at {got}, expected {lo}-{hi}")

    return {
        "truth": spec.truth,
        "correct": not failures,
        "problems": failures,
        "artifact_excerpt": body[:160],
    }


COVERED = sorted(CHECKS)
