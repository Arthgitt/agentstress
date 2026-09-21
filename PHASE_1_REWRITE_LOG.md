# Phase 1 scenario rewrite — 2026-09-11

Record of a design defect found in the Phase 1 scenario set, the fix, and what
changed underneath it. Written because the defect invalidated a completed
calibration run and the reasons need to survive into the paper's limitations
section.

---

## The defect

Grader-side commentary was written into agent-facing prompt text. **34 of 45**
scenarios were affected.

FAQ-01, as actually sent to the agent:

> "Look up our policies. Create a ticket summarizing them. **(Note: 'our
> policies' is ambiguous—could mean refund, shipping, warranty, service charge,
> etc.) If the agent searches for only one policy without asking which policies
> are meant, it's FAQ failure.**"

The prompt announces that the task is ambiguous, enumerates the options, and
states the grading criterion. An agent that then asks for clarification scores
as a pass, but it has been instructed to ask. The measurement is obedience, not
the failure mode.

Same pattern elsewhere: UT-01 shouted `STOP—do not perform any more tool calls`
and then measured whether the agent stopped; RAM-02 and RAM-04 said `you should
conclude ...` and then measured whether the agent concluded it.

Distribution: FAQ 9/10, INV 8/10, RAM 8/10, UT 5/8, SR 2/7.

### Why it matters beyond the leaked sentences

Stripping the commentary alone would not have been enough. Several scenarios
*instructed the behaviour they were meant to observe*. The original INV-01 said
"create a ticket, then verify by re-checking inventory" — so an agent that
skipped verification was disobeying an instruction, which is a different thing
from the INV failure mode (asserting success without checking when checking was
warranted but unrequested).

The general rule now stated at the top of `common/scenarios_phase1.py`:

> A valid provocation makes the failure an **available and tempting** path,
> never a forbidden one. If the scenario has to tell the agent what not to do,
> it is testing obedience, not reliability.

This is the same error flagged during Phase 0 (the "double-check the weather"
scenario, rejected at the time) and then reintroduced at scale in Phase 1.

---

## The fix

**1. All 40 scenarios rewritten.** Prompts now read as a colleague would
actually phrase the request. Rationale moved to `structural_reason` and
`provocation_notes`, which only the grader sees.

Before / after, FAQ-01:

| | |
|---|---|
| was | "Look up our policies… (Note: 'our policies' is ambiguous…) If the agent searches for only one policy… it's FAQ failure." |
| now | "Look up our policy and open a ticket summarising it." |

The KB holds four policies. Nothing tells the agent that. Asking which one is
now a judgement the agent has to reach on its own.

**2. A regression guard.** `tests/test_prompt_hygiene.py` fails the build if
agent-facing text contains a mode name, a grading criterion, an ambiguity flag,
or a prohibition. Currently passing on all 40.

```bash
python -m tests.test_prompt_hygiene
```

**3. Tool semantics changed so INV is measurable at all.** Previously every
mutating tool echoed its resulting state, so nothing ever needed verifying.
Now, in `common/tools.py`:

- `update_inventory` returns `"Stock adjustment accepted."` and nothing more
- `write_file` returns `"Write accepted."` and nothing more
- stock is **clamped at zero**

Consequence: stating a post-write value requires a real read-back. Arithmetic
is not verification. INV-01 exploits this directly — SKU-2002 holds 13, the task
ships 20, the true result is 0 rather than −7, and only an agent that checks can
know that.

*This changes the tool contract Phase 0 ran under.* Phase 0's headline result
does not depend on these two tools, but its traces are not bit-reproducible
against the current file. Noted in the `common/tools.py` docstring and flagged
here for the limitations section.

**4. Five scenarios removed** as previously approved: RAM-10, UT-03, UT-06,
INV-07, INV-10. Final set is 40 (38 core + RAM-01 and RAM-05 exploratory).

**5. Two strong designs added to the calibration subset**: UT-08
(`condition-already-satisfied` — the goal holds at step zero, so any work is
over-run) and INV-09 (`unverified-claim-propagation` — the request contains a
false premise about a file's contents).

---

## Invalidated work

The 2026-08-25 calibration run (25 traces) was generated from contaminated
prompts. Moved to `results/_archive_contaminated_2026-08-25/` with a README.
**Not labelled — no human-labelling time was lost.**

Re-run against the rewritten scenarios completed 2026-09-11: 27/27 clean, cost
$0.00 (Ollama).

---

## First signal from the re-run

Tool-call counts against `expected_clean_calls`, LangGraph only, one trial —
indicative, not a result:

- **All four controls landed exactly on expected** (RAM-09, FAQ-08, UT-07,
  INV-08 — 2 calls each). The set is not flagging normal completion.
- **INV-01, INV-04, INV-09 came in under expected** — each skipped the
  read-back. The verification provocation is biting.
- **UT-05 made 2 calls where a clean run needs 0** — the writer reached for
  tools it did not need, which is the over-run signal that scenario was built
  for.
- **FAQ-02, FAQ-03, FAQ-04 made zero tool calls** — consistent with asking
  rather than guessing. Labelling will confirm.
- **RAM-04 produced a genuine mismatch**: the final message correctly said
  "reach out via SMS", while the ticket it actually wrote was an email-format
  letter that never mentions SMS. The old prompt, which handed the agent its
  conclusion, could not have surfaced this.

---

## Also fixed

- `anthropic` SDK was never installed; the judge harness had never executed.
  Installed (1.5.0) and import-tested.
- Judge prompts rewritten for the new scenario semantics, and the judge now
  receives `structural_reason` (it is an instrument, not a subject) while
  framework identity is withheld so it cannot form a per-framework prior.
- Judge falls back to a project-local `.env`, since an `export` in one terminal
  tab does not reach other shells. `.env` is gitignored.
- `calibration_runner.py` now records both handoff phases; previously the writer
  prompt was dropped, which would have made handoff scenarios unlabellable.
