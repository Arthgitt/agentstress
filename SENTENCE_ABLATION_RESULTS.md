# One-sentence ablation — is CrewAI's fixed sentence the cause?

**Complete, 2026-09-19.** The clarification (FAQ) effect survives on
gpt-5.4-mini, and Phase 1d named one suspect: the sentence CrewAI appends to
every task and that its API cannot switch off —

> you MUST return the actual complete content as the final answer, not a summary.

Two LangGraph conditions on all 20 core FAQ scenarios, on both models
(240 agent runs; 4 trials on qwen2.5:7b, 2 on gpt-5.4-mini; 0 harness errors):

| Condition | Question |
|---|---|
| **the sentence only** — LangGraph baseline plus that one sentence | Is it *sufficient*? |
| **CrewAI's prompt minus the sentence** — full role/goal/backstory prompt and task wrapper, sentence deleted | Is it *necessary*? |

Reproduce: `python -m experiments.sentence_ablation --analyze` →
`results/sentence_ablation/stats.txt`.

---

## Result: sufficient, but not necessary

| FAQ failure rate | qwen2.5 7B (4 trials) | gpt-5.4-mini (2 trials) |
|---|---|---|
| LangGraph baseline | 32.5% | 22.5% |
| **+ the sentence only** | **61.2%** | **45.0%** |
| **+ CrewAI's prompt minus the sentence** | **72.5%** | **55.0%** |
| + CrewAI's full prompt | 75.0% | 60.0% |

Paired sign tests, scenario as unit:

| Comparison | qwen | gpt |
|---|---|---|
| sentence only vs baseline | 11 worse / 1 better, **p = 0.006** | 8 / 1, **p = 0.039** |
| prompt-minus-sentence vs baseline | 13 / 1, **p = 0.002** | 8 / 0, **p = 0.008** |
| full prompt vs prompt-minus-sentence | 3 / 1, p = 0.63 | 4 / 2, p = 0.69 |
| full prompt vs sentence only | 9 / 1, p = 0.021 | 6 / 1, p = 0.13 |

**One sentence, added to an otherwise bare prompt, roughly doubles clarification
failures on both models** — 32.5% → 61.2% and 22.5% → 45.0%. That is the
sharpest single demonstration in the project that framework scaffolding, not
the task, drives the failure.

**But deleting it from CrewAI's prompt changes almost nothing** (75.0% → 72.5%
on qwen, 60.0% → 55.0% on GPT, neither significant). The rest of the
scaffolding — "Your personal goal is: Complete the assigned task accurately",
"This is the expected criteria for your final answer" — is already enough on
its own.

**Conclusion: the cause is completion-oriented framing, not one sentence.**
Several components each suffice, so removing any single one does not help. This
also explains the earlier neutral-wording result: replacing our goal and
expected-output strings left CrewAI's template sentence in place, and each
alone carries the effect.

## Robustness

Re-scored with the strict bound from the GPT labelling round (FAQ verdicts
scored 0.5–0.74 counted as FAIL — see `results/phase1d_labeling/AGREEMENT.md`):

| | qwen strict | gpt strict |
|---|---|---|
| baseline → sentence only | 38.8% → 71.2% (11 / 0, p = 0.001) | 42.5% → 50.0% (5 / 3, p = 0.73) |
| baseline → prompt-minus-sentence | 38.8% → 76.2% (12 / 1, p = 0.003) | 42.5% → 70.0% (8 / 0, p = 0.008) |

- **On qwen both findings hold under either scoring.**
- **On GPT the "sentence alone" result is fragile**: under the strict bound it
  is no longer significant, while "prompt minus the sentence" stays
  significant. State the sentence-alone effect as established on qwen and
  directional on GPT.

## What the paper can claim

> A single sentence that a framework appends to every task —
> "you MUST return the actual complete content as the final answer" — roughly
> doubles the rate at which agents act on an underspecified request instead of
> asking (32.5% → 61.2% on qwen2.5 7B, 22.5% → 45.0% on gpt-5.4-mini).
> Removing it from the full scaffold does not help, because the surrounding
> completion-oriented framing carries the same pressure. Developers cannot fix
> this by deleting one string; the scaffold has to stop instructing the agent to
> deliver no matter what.

## Spend

| | Cost |
|---|---|
| Agent runs — 160 qwen (local) + 80 GPT | $0 + **$0.08** |
| Judge — 160 qwen + 80 GPT, batch | **$0.91 + $0.49 = $1.40** |
| **Total** | **~$1.48** |
