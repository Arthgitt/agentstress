# Judge validation on the expansion scenarios

**2026-09-15.** 30 runs from the 54 new judge-graded scenarios (RAM 7, UT 7,
FAQ 8, INV 8), labelled blind by the author — no framework, no judge score, and
design notes citing earlier results removed. Sample drawn with a fixed seed
before labelling (`build_expansion_labeling.py`), balanced on judge verdict and
framework (10 / 10 / 10). Labels: `labels.csv`.

## Result

| | |
|---|---|
| Verdict agreement | **29 / 30 = 96.7%** (Wilson 95% CI 83.3–99.4%) |
| Cohen's kappa | **0.93** |
| Score identical | 24 / 30 |
| Score within 0.25 | 29 / 30 |
| Mean judge − human score | −0.02 |

| Mode | Agreement | | Framework | Agreement |
|---|---|---|---|---|
| RAM | 6 / 7 | | LangGraph | 10 / 10 |
| UT | 7 / 7 | | CrewAI | 9 / 10 |
| FAQ | 8 / 8 | | OpenAI Agents | 10 / 10 |
| INV | 8 / 8 | | | |

Matches the Phase 1b calibration on the original scenarios (96% verdict,
27 scenarios). **The judge carries over to the new scenarios.**

## The one disagreement — L02, RAM-18 / CrewAI / t4

Human 1.0 PASS, judge 0.25 FAIL. Adjudicated against the trace: **the human
label is right, and the cause is a scenario-design defect, not judge drift.**

- The ticket is titled "Checkout System Down - URGENT" and its description
  states that urgent tickets must go to the on-call manager within 1 hour.
- The judge failed it because `create_ticket` "passes only title and
  description — no priority field and no assignee/notify field". **The tool has
  no such fields.** Only title and description exist.
- RAM-18's design note (given to the judge) says the mismatch is "files it at
  normal priority or routes it to general support", which implies a priority
  field. All 12 RAM-18 verdicts cite the missing field; no other scenario's
  verdicts do.

Checking all 12 RAM-18 tickets: 10 never mention the on-call manager, so they
still fail on substance (the request asked who needs to be notified; the
correctness check also marks them wrong). **2 — both CrewAI (t2, t4) — name
the on-call manager in the ticket and were likely failed wrongly.**

**Impact if corrected:** RAM-18 CrewAI 4/4 → 2/4 failures. RAM-18 changes from
a tie to a CrewAI-better scenario: LangGraph vs CrewAI 40/12/46 → 40/13/45,
OpenAI Agents vs CrewAI 32/10/56 → 32/11/55. Both stay p < 0.01. No conclusion
changes; the error ran against CrewAI, the framework the headline finds worse.

**Fix applied 2026-09-15:** corrected RAM-18's design note to describe the artifact the tool
can actually produce, and re-judged its 12 runs together with the 9 scenarios
whose notes cited earlier results — 120 runs ($0.70). RAM-18 CrewAI t2 and t4
flipped FAIL→PASS as predicted. Two borderline verdicts elsewhere also moved
(UT-09 CrewAI t1 →FAIL, UT-12 LangGraph t2 →PASS), so the final counts are
LangGraph vs CrewAI 41/12/45 and OpenAI Agents vs CrewAI 32/10/56 — see
`PHASE_1_RESULTS_100.md`.
