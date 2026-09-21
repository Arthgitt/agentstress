# MAST failure-mode prevalence — verified figures

**Source:** Cemri et al., *Why Do Multi-Agent LLM Systems Fail?*,
arXiv:2503.13657 — **version v2** (`https://arxiv.org/html/2503.13657v2`).

**Cite v2, not v1.** v1 keeps the per-mode percentages inside Figure 2 and does
not state them in text; v2 does. The PDF does not extract cleanly either. The
HTML rendering of v2 is the reliable source.

**Base:** these percentages are over the **151 hand-annotated traces** used to
build the taxonomy, not the 1600+ trace MAST-Data release. Quote the base
alongside the figure — "17.14% of failures across 151 annotated traces" — or a
reviewer will reasonably ask.

---

## Full taxonomy

### FC1 — Specification Issues (41.77%)

| Mode | | Prevalence |
|---|---|---|
| FM-1.1 | Disobey task specification | 10.98% |
| FM-1.2 | Disobey role specification | 0.50% |
| **FM-1.3** | **Step repetition** | **17.14%** |
| FM-1.4 | Loss of conversation history | 3.33% |
| **FM-1.5** | **Unaware of termination conditions** | **9.82%** |

### FC2 — Inter-Agent Misalignment (36.94%)

| Mode | | Prevalence |
|---|---|---|
| FM-2.1 | Conversation reset | 2.33% |
| **FM-2.2** | **Fail to ask for clarification** | **11.65%** |
| FM-2.3 | Task derailment | 7.15% |
| FM-2.4 | Information withholding | 1.66% |
| FM-2.5 | Ignored other agent's input | 0.17% |
| **FM-2.6** | **Reasoning-action mismatch** | **13.98%** |

### FC3 — Task Verification (21.30%)

| Mode | | Prevalence |
|---|---|---|
| FM-3.1 | Premature termination | 7.82% |
| **FM-3.2** | **No or incomplete verification** | **6.82%** |
| **FM-3.3** | **Incorrect verification** | **6.66%** |

Bold = covered by this benchmark. The paper itself groups FM-3.2 + FM-3.3 as
**13.48%**, which is how our INV mode should be quoted.

---

## Corrections to the project brief

The brief's Section 5 figures are approximations and two are materially off.
Use the table above in any write-up.

| Mode | Brief said | v2 actual | Delta |
|---|---|---|---|
| Step repetition | ~15.7% | 17.14% | +1.4 |
| Reasoning-action mismatch | ~13.2% | 13.98% | +0.8 |
| Unaware of termination | ~12.4% | **9.82%** | **−2.6** |
| Fail to ask for clarification | "high, varies" | 11.65% | resolved |
| Incorrect/No verification | unstated | 13.48% (6.82 + 6.66) | resolved |

The UT figure is the one to watch: the brief ranks it 3rd, the paper puts it
6th. Any claim built on "we target the three most prevalent modes" needs
rewording.

---

## Coverage gap worth deciding on

Ranking all modes by prevalence, with FM-3.2+3.3 combined as one verification
mode:

| Rank | Mode | Prevalence | Covered? |
|---|---|---|---|
| 1 | Step repetition | 17.14% | yes — SR |
| 2 | Reasoning-action mismatch | 13.98% | yes — RAM |
| 3 | Verification (3.2 + 3.3) | 13.48% | yes — INV |
| 4 | Fail to ask for clarification | 11.65% | yes — FAQ |
| 5 | **Disobey task specification** | **10.98%** | **NO** |
| 6 | Unaware of termination | 9.82% | yes — UT |
| 7 | Premature termination | 7.82% | no |
| 8 | Task derailment | 7.15% | no |

**The suite covers ranks 1–4 and 6, skipping rank 5.** "Disobey task
specification" at 10.98% is more prevalent than UT at 9.82%, which the suite
does cover.

Two honest options:

1. **Justify the exclusion.** Defensible: disobeying an explicit specification
   is largely an instruction-following property of the base model, so it would
   mostly measure qwen2.5 rather than framework orchestration — the opposite of
   what this benchmark isolates. State this in Limitations.
2. **Add it as a sixth mode.** Roughly 8–10 scenarios. Also deterministically
   gradeable in many cases (did the agent use the named tool? hit the stated
   title? respect the stated threshold?), so the grading cost is low.

Option 1 is the cheaper path and is genuinely defensible given the framework-
isolation goal. It should be an explicit stated choice, not a silent omission —
a reviewer comparing the suite against MAST's own ranking will notice.
