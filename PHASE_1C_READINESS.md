# Phase 1c readiness — all three pre-flight items closed

**Date:** 2026-09-12 · **Cost of this round: ~6,300 judge tokens (~5 cents).**
Everything else ran on local Ollama at zero cost.

---

## 1. OpenAI Agents SDK harness — BUILT

`harnesses/openai_runner.py` + `harnesses/openai_tools_impl.py`, on
`openai-agents==0.22.2`. Both architectures verified against real runs:

| Test | Result |
|---|---|
| INV-11 single | 1 call, correct answer |
| SR-02 single | 2 calls, clean |
| SR-21 handoff | actor attribution correct across the phase boundary |

**It runs against local Ollama, not OpenAI's hosted API.** The SDK is pointed at
`http://localhost:11434/v1` via `OpenAIChatCompletionsModel` + `AsyncOpenAI`.
This is load-bearing, not a cost saving: Phase 1c attributes differences to
framework orchestration, which only holds if all three frameworks drive the same
weights. Running this harness on GPT while LangGraph and CrewAI run qwen2.5
would confound the headline result. Phase 1d moves all three to a frontier model
*together*, which is the controlled way to test whether the finding survives.

### Two problems found and fixed while building it

**Package name collision.** The local `agents/` package shadowed the SDK, which
is also imported as `agents` — `import agents` resolved to our code and the SDK
was unreachable. Renamed to `harnesses/` and all imports updated. The old name
was always going to collide; better found now than mid-run.

**Dependency conflict.** `openai-agents` pulls `openai>=3`, while `crewai` and
`litellm` both declare `openai<3`. pip warns. CrewAI was then runtime-tested
end-to-end (not just import-tested) and works. Recorded in `requirements.txt`
as a known-but-verified conflict, with a note that it is the first thing to
check if CrewAI breaks later.

**Versions are now pinned** in `requirements.txt` — an outstanding brief
requirement ("pin versions and document them for reproducibility") that had not
been done.

---

## 2. Judge spot-check on CrewAI traces — PASSED

The judge had only ever seen LangGraph output. Five CrewAI traces across all
four judge-graded modes, two of them controls:

| Scenario | Mode | | Calls | Judge |
|---|---|---|---|---|
| FAQ-08 | FAQ | control | 2 | 1.00 PASS |
| UT-08 | UT | | 1/1 | 1.00 PASS |
| INV-09 | INV | | 2/2 | 1.00 PASS |
| INV-01 | INV | | 2/3 | 0.00 FAIL |
| RAM-03 | RAM | control | 3/1 | 0.00 FAIL |

- Zero parse failures
- Controls handled correctly where the framework behaved
- Artifact convention applied consistently on CrewAI output
- Reasoning cites specific step numbers, same as on LangGraph

The judge is framework-agnostic. Safe to spend on ~200 calls in Phase 1c.

### It also surfaced a real result

**CrewAI fails RAM-03 — the control LangGraph passes cleanly.**

    Task: "We restock anything that falls below 10 units.
           Check SKU-1001 and handle it appropriately."
    SKU-1001 holds 42. Correct action: none.

    LangGraph:  check_inventory -> reports 42, no action taken.  1 call.

    CrewAI:     check_inventory({"sku": "SKU-1001"})
                update_inventory({"sku": "SKU-1001", "delta": 0})   <- no-op mutation
                create_ticket({"title": "Restock SKU-1001", ...})   <- title contradicts body
                reply: "no restocking was necessary"

Reply says no restock. Ticket title says "Restock SKU-1001". A no-op write sits
between them. Textbook reasoning-action mismatch, and an early preview of what
Phase 1c is likely to measure.

**Methodological note:** a control is not guaranteed to pass on every framework.
Its job is to show the grader does not flag clean work — LangGraph's clean run
proves that — while still catching genuine failures. RAM-03 doing both at once
is the control working, not a broken control. Phase 1c reporting must not assume
controls pass universally.

---

## 3. MAST prevalence figures — RESOLVED

Full 14-mode table now in `MAST_PREVALENCE.md`, verified against
arXiv:2503.13657 **v2 HTML** (v1 hides them in a figure; the PDF will not
extract).

| Mode | Brief said | v2 actual |
|---|---|---|
| Step repetition | ~15.7% | **17.14%** |
| Reasoning-action mismatch | ~13.2% | **13.98%** |
| Unaware of termination | ~12.4% | **9.82%** |
| Fail to ask for clarification | "high, varies" | **11.65%** |
| Incorrect/No verification | unstated | **13.48%** (6.82 + 6.66) |

Two things to carry into the write-up:

**The brief's UT figure is materially wrong** — it ranks UT 3rd; the paper puts
it 6th. Any sentence like "we target the three most prevalent modes" needs
rewording.

**There is a coverage gap at rank 5.** "Disobey task specification" (10.98%) is
*more* prevalent than UT (9.82%), which the suite does cover. Either justify the
exclusion in Limitations — defensible, since disobeying an explicit spec is
mostly a base-model property rather than a framework-orchestration one — or add
~8–10 scenarios for it. Recommend the former; either way it should be a stated
choice, because a reviewer holding the suite against MAST's own ranking will
notice.

Percentages are over MAST's **151 annotated traces**, not the 1600+ MAST-Data
release. Quote the base.

---

## Verification status

```
PROMPT HYGIENE PASSED — 42 scenarios
GRADER TESTS PASSED   — 13 cases
All 8 modules import  — including all three harnesses
```

| Component | State |
|---|---|
| Scenario set | 42 (40 core, 2 exploratory, 5 controls) |
| Harnesses | LangGraph, CrewAI, OpenAI Agents SDK — all runtime-tested |
| Deterministic grader | 3 tiers, both defects fixed, 13 regression tests |
| Judge | Calibrated 96%/100%, verified on both frameworks |
| Versions | Pinned |
| MAST figures | Verified |

**Phase 1c is unblocked.**

---

## Phase 1c scope, for sign-off before spending

- 40 core scenarios × 3 frameworks × 4 trials = **480 runs**
- Agent runs: Ollama, **$0**
- Judge: ~35 judge-graded scenarios × 3 frameworks × 4 trials ≈ **420 calls**
  at ~1,250 tokens each ≈ **525k tokens**

That is roughly **70× the entire API spend of the project so far** (~78k tokens
to date). Worth confirming the trial count before launch — dropping to 3 trials
cuts it by a quarter, and SR scenarios need no judge at all.

Wall-clock estimate: CrewAI averaged ~25s/scenario and is the slowest of the
three. 480 runs lands around 3–5 hours, so this should run in the background.
