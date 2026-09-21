# Prompt ablation — why CrewAI failed more

**Complete, 2026-09-17.** 60 scenarios (all SR, UT and FAQ — the modes where
Phase 1 found a framework gap) × 3 conditions × 4 trials = 720 new agent runs,
compared against the matching 720 Phase 1 runs. Same model (qwen2.5:7b-instruct),
temperature 0.3, tools and judge. SR graded deterministically; UT and FAQ by
claude-opus-5 (480 verdicts, 0 errors).

Reproduce: `python -m experiments.analyze_ablation` → `results/ablation/stats.txt`.

---

## Headline

**The framework gap is mostly the prompt text, not the orchestration.** Give
LangGraph or OpenAI Agents CrewAI's exact prompt and they fail as often as
CrewAI; give CrewAI neutral wording and its failures fall by about 40%.

| Setup (60 scenarios) | Failure rate |
|---|---|
| LangGraph, as in Phase 1 | 14.6% |
| OpenAI Agents, as in Phase 1 | 24.2% |
| CrewAI, as in Phase 1 | **47.1%** |
| **LangGraph + CrewAI's prompt** | **45.4%** |
| **OpenAI Agents + CrewAI's prompt** | **43.3%** |
| **CrewAI + neutral wording** | **29.2%** |

Paired sign tests, scenario as unit, Bonferroni ×6:

| Comparison | worse / better / tie | p | corrected |
|---|---|---|---|
| LangGraph + CrewAI prompt vs LangGraph | 32 / 1 / 27 | < 0.001 | < 0.001 |
| OpenAI Agents + CrewAI prompt vs OpenAI Agents | 22 / 2 / 36 | < 0.001 | < 0.001 |
| CrewAI + neutral wording vs CrewAI | 1 / 22 / 37 | < 0.001 | < 0.001 |
| LangGraph + CrewAI prompt vs CrewAI | 6 / 9 / 45 | 0.61 | 1.0 |
| OpenAI Agents + CrewAI prompt vs CrewAI | 5 / 9 / 46 | 0.42 | 1.0 |
| CrewAI + neutral wording vs LangGraph | 20 / 3 / 37 | < 0.001 | 0.003 |

- With CrewAI's prompt, the other two frameworks are **indistinguishable from
  CrewAI**, and each became worse on dozens of scenarios while improving on at
  most two.
- Neutral wording removes a large part of CrewAI's excess, but **not all of it**:
  CrewAI with neutral wording is still worse than LangGraph (20 / 3). What
  remains is CrewAI's fixed template sentence, which cannot be switched off
  through its API ("you MUST return the actual complete content as the final
  answer, not a summary"), and/or its execution loop.

## By mode

| Mode | LG | LG + CrewAI prompt | OAI | OAI + CrewAI prompt | CrewAI | CrewAI neutral |
|---|---|---|---|---|---|---|
| SR — repetition | 8.8% | 36.2% | 5.0% | 31.2% | 37.5% | 16.2% |
| UT — termination | 2.5% | 25.0% | 8.8% | 23.8% | 26.2% | **6.2%** |
| FAQ — clarification | 32.5% | 75.0% | 58.8% | 75.0% | 77.5% | 65.0% |

- **SR and UT:** the prompt accounts for nearly everything. Neutral CrewAI on
  UT (6.2%) is better than OpenAI Agents' baseline.
- **FAQ:** CrewAI's prompt drives both other frameworks to CrewAI's level (LG
  14 worse / 0 better, p < 0.001), but neutral wording only partly helps
  (7 better / 1 worse, p = 0.07). Our removable wording is not the main
  anti-clarification pressure; the likely candidate is the fixed "MUST return
  the actual complete content" sentence — an instruction to deliver, not to ask.
  Tested directly in `SENTENCE_ABLATION_RESULTS.md`: that sentence alone doubles
  FAQ failures, but removing it from the full prompt does not help, so the
  pressure comes from completion-oriented framing generally.
  Consistent with this, OpenAI Agents' one-line "Complete the assigned task
  accurately" already sits between LangGraph and CrewAI on FAQ (58.8%).

## Extra work

Mean tool calls per run: LangGraph 2.28 → **2.91** with CrewAI's prompt; OpenAI
Agents 2.27 → **3.67** (one run looped 163 calls — 83 inventory checks and 80
updates on FAQ-22); CrewAI 3.04 → **2.39** with neutral wording.

## One failure that is the loop, not the prompt

SR-21's CrewAI crash (empty LLM response, 4/4 in Phase 1) reproduced **3/4 with
neutral wording**, while LangGraph and OpenAI Agents with CrewAI's prompt ran it
cleanly 8/8. This one is CrewAI's execution, not its text.

---

## What this changes in the paper

The Phase 1 finding "CrewAI shows ~19 points more failures" stands as
measured, but its **cause is now identified**: the prompt scaffolding each
framework wraps around the user's task. The defensible headline becomes:

> On identical tasks, model and tools, the prompt scaffolding an agent
> framework adds changes failure rates up to threefold — and moves
> clarification, repetition and termination failures, not reasoning–action
> mismatch or verification.

Two honest qualifications:

1. **Part of CrewAI's prompt was ours.** CrewAI requires a role, goal,
   backstory and expected output; the values the harness supplied ("Complete
   the assigned task accurately…", "A final answer that completes the task
   exactly as instructed") were completion-oriented. The neutral condition
   shows how much of the effect those strings carried; the rest comes from
   CrewAI's fixed template. Framework defaults and developer-supplied wording
   should be reported as a combined, realistic configuration — with this
   ablation separating them.
2. **Model strength — tested in Phase 1d** (`PHASE_1D_RESULTS.md`). On
   gpt-5.4-mini the SR and UT effects disappear, but the FAQ effect survives:
   CrewAI's prompt still drives LangGraph from 22.5% to 60.0% clarification
   failures. The scaffolding sensitivity is partly a small-model weakness and
   partly not.

## Method notes

- Prompt text verified byte-for-byte against captured CrewAI requests before the
  run (`python -m experiments.prompt_ablation --verify`); CrewAI injects nothing
  after the first turn and tool schemas are identical across frameworks
  (`results/prompt_capture/`).
- Scenario set fixed by mode (all SR/UT/FAQ core scenarios) before any ablation
  run, not selected per scenario.
- The Mac slept twice during the run; the frozen run was restarted, and only
  completed traces were kept (the in-flight trial was re-run from scratch).
- Judged in a separate batch from the Phase 1 baselines, with the identical
  judge model, prompt and settings.

## Spend

| | Cost |
|---|---|
| Ablation agent runs (720) | $0 (local) |
| Ablation judge batch (480 calls, 474,726 in / 117,221 out) | **$2.65** |
| **Project total** | **~$13.21** |
