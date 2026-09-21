# 100-scenario suite — built, tested, ready for the full run

**Date:** 2026-09-13 · **Spend on this step: $0** (everything ran on local Ollama).

---

## The suite

| Mode | Kept from Phase 1c | New | Total | Controls | Handoffs |
|---|---|---|---|---|---|
| SR | 3 | 17 | 20 | SR-23, SR-33 | 4 |
| RAM | 8 | 12 | 20 | RAM-03, RAM-23 | 3 |
| UT | 5 | 15 | 20 | UT-07 | 3 |
| FAQ | 7 | 13 | 20 | FAQ-08, FAQ-23 | 2 |
| INV | 6 | 14 | 20 | INV-11 | 3 |
| **Total** | **29** | **71** | **100** | **8** | **15** |

New scenarios: `common/scenarios_expansion.py`.

**Retired, not deleted:** the 13 Phase 1c scenarios where all three frameworks
scored identically (SR-01, SR-19, SR-20, SR-22, RAM-02, RAM-06, UT-02, FAQ-02,
FAQ-06, FAQ-07, INV-01, INV-02, INV-08). Their traces stay on disk and gradeable
with `--include-retired`; they never run again and are excluded from reports.

**Two extra controls** (RAM-23, FAQ-23) and a Tier 2 control (SR-33) were added
where Phase 1c showed the existing baselines were incomplete — RAM-03 anchors
false positives on LangGraph only, FAQ-08 involves no mutation, and SR-23 has no
writes to test the same-target detector against.

**World:** four SKUs, three customers, four cities, six documents and four files
added — nothing pre-existing changed. `tests/test_world.py` pins the original
values and replays every search query from the Phase 1c traces against a frozen
copy of the old matcher.

**Correctness ground truth:** 71 of the 100 active scenarios. The FAQ scenarios
are deliberately uncovered: there, asking a question is the right answer.

---

## Smoke test — 71 new scenarios × 1 LangGraph run (free)

Not experimental data. A design check before spending money.

- 71/71 ran, **0 harness crashes**
- First pass: 23 flagged wrong. Every one was read against its raw trace.

### What it caught in the suite (fixed before any billed run)

| Problem | Cause | Fix |
|---|---|---|
| **SR-33 control returned an empty reply, 3/3 runs** | qwen generated ~170 tokens; Ollama's tool-call parser discarded them. A serving-layer artifact, not agent behaviour | Redesigned: stock figures supplied in the prompt, create_ticket only. Parses cleanly 3/3 |
| **RAM-15 impossible to complete** | Agent searched "office holid**ays**"; mock search needed 2 exact words | Plural folding in `_find_kb_match` (`holidays`→`holiday`, `policies`→`policy`); verified identical results for all 21 Phase 1c queries |
| **Correct decimal answers scored wrong** (SR-26 `441.0`, RAM-17 `$216.00`, UT-22 `$378.00`) | Number matcher rejected a decimal tail | Numbers compared by value; dates, ranges and identifier tails (`SKU-4004`) excluded |
| **`$1.2M` stopped matching 1.2** | Side effect of the above fix, caught on the re-score (SR-35, INV-24 flipped) | K/M/B magnitude suffix allowed; `12C`, `2.4kg` still rejected |
| **Priority in a ticket title not seen** (RAM-18) | Only the ticket body was checked | Ticket title is now part of the artifact |

The number-matching fix also changed exactly **one already-reported Phase 1c
trial** (SR-20 / OpenAI Agents / t1, a correct "$180.00"). `PHASE_1C_RESULTS.md`
is corrected; no conclusion changes.

### Final smoke tally

| | |
|---|---|
| Right answer | 41 |
| Wrong answer | 17 |
| No correctness check (FAQ) | 13 |

**All 17 remaining wrongs were confirmed as genuine agent behaviour**, which is
what the scenarios are built to provoke — for example:

- tickets carrying `[result of first check_inventory call]` or `[new_stock_level]`
  instead of values (SR-24, SR-31)
- noting snow in Denver and recommending the outdoor demo go ahead (RAM-16)
- planning an email reminder to a customer flagged do-not-contact (RAM-12)
- confirming five different false premises without a single lookup
  (INV-12, 13, 14, 15, 25) — the INV-09 pattern that separated frameworks in 1c
- writing the refund policy from memory without searching (UT-21)
- zeroing an already-empty SKU with `update_inventory(-100)` (UT-10)

Note this is **one framework, one trial**: it shows the scenarios bite, not that
they separate frameworks. Only the full run can show that.

---

## Tests

| Suite | Result |
|---|---|
| Correctness | 44 cases pass |
| Grader | 13 cases pass |
| Prompt hygiene | 100 scenarios pass |
| World pin | original values unchanged; 21 recorded queries resolve identically |

---

## Grading now uses the Batch API

`grading/batch_judge.py` — **50% of standard price**, same instrument:

- Requests are built by the same `judge_request_params` the synchronous judge
  uses; verified identical model, settings and prompt text on a real trace. The
  Phase 1b calibration therefore carries over.
- Never pays twice: skips anything already graded or already inside a submitted
  batch. Batch ids are saved before anything else, so a crash loses nothing.
- Results land in the same cache `grade_phase1c.py` reads.

```bash
python -m grading.batch_judge submit --dry-run   # count and cost, no spend
python -m grading.batch_judge submit
python -m grading.batch_judge status
python -m grading.batch_judge collect
```

---

## Full run — what launching costs

| Stage | Volume | Cost | Time |
|---|---|---|---|
| Agent runs (new scenarios only) | 852 = 71 × 3 frameworks × 4 trials | **$0** (Ollama) | ~4–9 h, overnight |
| Batch judge | 648 calls | **~$4.14** | usually < 1 h |
| **Total** | | **~$4.14** (+10% buffer ≈ $4.60) | |

The runner skips the 348 kept-scenario traces already on disk and never touches
retired scenarios — verified before launch.

**Spend-limit reminder:** batches can run slightly over a configured limit.
Leave about $6 of headroom.
