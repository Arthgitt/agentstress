# Phase 1d results — frontier cross-check on gpt-5.4-mini

**Complete, 2026-09-19.** The Phase 1 framework comparison and the prompt
ablation re-run on a stronger model. 60 scenarios (all core SR, UT, FAQ) ×
6 setups × 2 trials = **720 agent runs** on gpt-5.4-mini (temperature 0.3,
Chat Completions for every framework), 0 harness errors. SR graded
deterministically; UT and FAQ by claude-opus-5 (480 verdicts; agents GPT, judge
Claude — different model families, as the method requires).

Reproduce: `python -m experiments.analyze_ablation --set phase1d` →
`results/phase1d/stats.txt`. The qwen2.5:7b comparison figures come from
`python -m experiments.analyze_ablation` (`results/ablation/stats.txt`).

---

## Headline

**On a stronger model, the framework gap shrinks but does not vanish — and what
survives is almost entirely clarification-seeking.** Repetition and termination
failures largely disappear on every setup; the failure to ask for missing
information still tracks the prompt scaffolding, and CrewAI's scaffolding
still suppresses asking.

| Pooled SR + UT + FAQ (60 scenarios) | qwen2.5 7B | **gpt-5.4-mini** |
|---|---|---|
| LangGraph | 14.6% | **8.3%** |
| OpenAI Agents | 24.2% | **19.2%** |
| CrewAI | 47.1% | **25.0%** |
| LangGraph + CrewAI's prompt | 45.4% | **21.7%** |
| OpenAI Agents + CrewAI's prompt | 43.3% | **24.2%** |
| CrewAI + neutral wording | 29.2% | **21.7%** |

Paired sign tests on gpt-5.4-mini, scenario as unit, Bonferroni ×6:

| Comparison | worse / better / tie | p | corrected |
|---|---|---|---|
| CrewAI vs LangGraph | 13 / 1 / 46 | 0.002 | **0.011** |
| CrewAI vs OpenAI Agents | 7 / 2 / 51 | 0.18 | 1.0 |
| LangGraph + CrewAI prompt vs LangGraph | 13 / 1 / 46 | 0.002 | **0.011** |
| OpenAI Agents + CrewAI prompt vs OpenAI Agents | 6 / 2 / 52 | 0.29 | 1.0 |
| CrewAI + neutral wording vs CrewAI | 2 / 5 / 53 | 0.45 | 1.0 |

- **CrewAI is still worse than LangGraph on GPT** (13 scenarios to 1, survives
  correction as graded; 11 / 2, corrected 0.13 under the strict judge bound —
  see Limits), no longer distinguishable from OpenAI Agents.
- **Giving LangGraph CrewAI's prompt still makes it worse** (13 to 1) — the
  prompt effect replicates on a stronger model for LangGraph.
- Neutralising the wording *we* supplied no longer helps on GPT (25.0% →
  21.7%, n.s.).

## By mode — where the effect lives

| Mode | Setup | qwen2.5 7B | gpt-5.4-mini |
|---|---|---|---|
| **SR** repetition | LangGraph / OAI / CrewAI | 8.8 / 5.0 / 37.5% | 2.5 / 2.5 / 5.0% |
| | LG + CrewAI prompt / OAI + CrewAI prompt / CrewAI neutral | 36.2 / 31.2 / 16.2% | 2.5 / 2.5 / 5.0% |
| **UT** termination | LangGraph / OAI / CrewAI | 2.5 / 8.8 / 26.2% | 0.0 / 12.5 / 7.5% |
| | LG + CrewAI prompt / OAI + CrewAI prompt / CrewAI neutral | 25.0 / 23.8 / 6.2% | 2.5 / 2.5 / 5.0% |
| **FAQ** clarification | LangGraph / OAI / CrewAI | 32.5 / 58.8 / 77.5% | **22.5 / 42.5 / 62.5%** |
| | LG + CrewAI prompt / OAI + CrewAI prompt / CrewAI neutral | 75.0 / 75.0 / 65.0% | **60.0 / 67.5 / 55.0%** |

- **SR and UT: the effect is a small-model weakness.** On GPT every setup sits
  at 0–12.5%; CrewAI's prompt changes nothing (SR 0 scenarios worse, 20 ties).
  CrewAI's SR-21 crash on qwen (4/4) did not occur on GPT.
- **FAQ: the effect survives.** CrewAI's prompt pushes LangGraph from 22.5% to
  60.0% (12 worse / 1 better, p = 0.003) and OpenAI Agents from 42.5% to 67.5%
  (6 / 0, p = 0.031). The stronger model asks more often in its default setup,
  but a completion-oriented scaffold still talks it out of asking.
- **Which part of the scaffold — answered by `SENTENCE_ABLATION_RESULTS.md`:**
  that sentence alone, added to a bare LangGraph prompt, roughly doubles FAQ
  failures (32.5 → 61.2% qwen, 22.5 → 45.0% GPT), but deleting it from CrewAI's
  full prompt changes almost nothing (75.0 → 72.5%, 60.0 → 55.0%). The cause is
  completion-oriented framing in general, several parts of which each suffice.
  Neutralising our goal and expected-output wording barely moves CrewAI on
  either model (FAQ 77.5 → 65.0% on qwen, 62.5 → 55.0% on GPT), consistent with
  that. The candidate sentence was CrewAI's fixed template line — "you MUST return the actual complete content as the final
  answer, not a summary" — which instructs delivery, not asking, and cannot be
  switched off through CrewAI's API. Consistent with this, OpenAI Agents' one
  line "Complete the assigned task accurately" already sits between LangGraph
  and CrewAI on FAQ on both models.

## Correction to interim reporting

After the SR half was graded I reported that on GPT "both effects disappear"
and called the prompt sensitivity "a small-model weakness". That holds for SR
and UT; **it does not hold for FAQ**, where both the framework gap and the
prompt effect persist on gpt-5.4-mini.

---

## What this adds to the paper

> Framework prompt scaffolding changes agent failure rates up to threefold on
> identical tasks. On a 7B model it drives repetition, termination and
> clarification failures; on a stronger model the first two largely disappear,
> but clarification failures remain scaffolding-driven — completion-oriented
> framework prompts suppress asking for missing information even on
> gpt-5.4-mini.

This is the most practically useful single result so far: a developer choosing
a framework cannot fix clarification failures by upgrading the model alone.

## Limits

- **2 trials per setup** (4 in Phase 1). Adequate for scenario-level sign tests
  because trials within a scenario mostly agree, but per-mode rates on GPT are
  coarser.
- **One stronger model.** gpt-5.4-mini is a mid-size hosted model, not the
  frontier maximum.
- **Judge validated on GPT outputs — weaker than on qwen.** 24 blind-labelled
  GPT runs: 87.5% agreement, kappa 0.75 (qwen: 96.7%, 0.93). All three
  disagreements are the judge scoring "asked about the wrong gap" as 0.5–0.6
  PASS where the rubric says 0.25 FAIL. Under a strict bound (FAQ scores
  0.5–0.74 counted as FAIL) the GPT pooled comparisons keep their direction but
  not correction-level significance (CrewAI vs LangGraph 11/2, corrected 0.13);
  the FAQ prompt effect survives uncorrected (9/1, p = 0.021). **Treat the GPT
  results as directional.** Details: `results/phase1d_labeling/AGREEMENT.md`.
- **Judged in two batches.** Anthropic credit ran out mid-batch; 133 requests
  were rejected unbilled and re-submitted with the identical judge model,
  prompt and settings.

## Method notes

- All three frameworks use the Chat Completions API on GPT, as they shared one
  transport on Ollama. Prompt text on GPT was verified byte-for-byte against
  CrewAI's captured request before the run (`python -m experiments.phase1d
  --pilot`).
- All model traffic went through a local metering proxy
  (`experiments/usage_proxy.py`) with a $3 automatic stop; every request's
  usage was recorded, none missing.
- The Ollama code path was re-verified after adding the OpenAI backend: all
  three frameworks send byte-identical requests to before, so Phase 1 results
  are unaffected.

## Spend

| | Cost |
|---|---|
| GPT agent runs (720 + pilot + key check) | **$0.94** (OpenAI) |
| Judge, first batch (347 graded before credit ran out) | $1.84 |
| Judge, resubmitted 133 | $0.73 |
| **Phase 1d total** | **~$3.51** |
| Sentence ablation (judge $1.40, GPT agents $0.08) | **$1.48** |
| **Project total** | **~$17.18 Anthropic + $1.02 OpenAI ≈ $18.20** |
