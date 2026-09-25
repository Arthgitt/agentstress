# agentstress

[![PyPI](https://img.shields.io/pypi/v/agentstress.svg)](https://pypi.org/project/agentstress/)
[![Python](https://img.shields.io/pypi/pyversions/agentstress.svg)](https://pypi.org/project/agentstress/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

A stress-test benchmark for LLM agent frameworks. 100 scenarios engineered to
provoke five failure modes from the [MAST](https://arxiv.org/abs/2503.13657)
taxonomy, with graders that say *which* failure happened and whether the task
was actually done correctly — two separate questions that often disagree.

It exists because of what it found: **most of the difference between agent
frameworks is the prompt scaffolding they wrap around your task, not their
orchestration.**

| Same scenarios, same model (qwen2.5 7B), same tools | Failure rate |
|---|---|
| LangGraph | 14.6% |
| OpenAI Agents SDK | 24.2% |
| CrewAI | 47.1% |
| **LangGraph given CrewAI's prompt** | **45.4%** |
| **CrewAI given neutral wording** | **29.2%** |

A single sentence CrewAI appends to every task — *"you MUST return the actual
complete content as the final answer, not a summary"* — roughly doubles how
often an agent acts on an underspecified request instead of asking, on both a
7B model and gpt-5.4-mini. Full results: [`docs`](#results-and-data) below.

## Install

```bash
pip install agentstress                 # scenarios, graders, CLI
pip install "agentstress[langgraph]"    # + the framework you want to test
pip install "agentstress[all]"          # + crewai, openai-agents, judge
```

Runs against a local model through [Ollama](https://ollama.com) by default, so
you can use the whole benchmark without an API key.

## Start here: what is your framework actually sending?

```bash
agentstress capture --framework crewai --scenario FAQ-12
```

prints the exact first request, separating your task text from everything the
framework added. Most developers have never seen it.

## Run the benchmark

```bash
ollama pull qwen2.5:7b-instruct

agentstress list --mode FAQ                       # see what is provoked
agentstress run  --framework langgraph --mode FAQ --trials 2 --out runs/
agentstress grade --runs runs/                    # step repetition: free, deterministic
agentstress grade --runs runs/ --judge            # all modes: billed LLM judge
agentstress report --runs runs/
```

Use a hosted model with `--model openai:gpt-5.4-mini` (needs `OPENAI_API_KEY`).
The judge needs `ANTHROPIC_API_KEY`; it is never from the same model family as
the agent under test.

## What the suite measures

| Mode | What it provokes |
|---|---|
| **SR** step repetition | Re-fetching a value the agent already holds |
| **RAM** reasoning-action mismatch | The ticket contradicts the agent's own conclusion |
| **UT** unaware of termination | Carrying on after the job is done, or stopping short |
| **FAQ** fail to ask for clarification | Guessing instead of asking when something is missing |
| **INV** incorrect / no verification | Claiming a result without reading it back |

Design rules that make the numbers mean something:

- **Provocation, not instruction.** No scenario mentions failure modes,
  grading, or prohibitions. A test enforces this across all 100 scenarios.
- **The artifact is the action.** When the chat reply and the ticket disagree,
  the ticket is graded. Small models often say the right thing and write
  `[placeholder]` into the artifact.
- **Controls.** 8 scenarios where the failure is *not* available. A grader that
  flags them is over-flagging.
- **Two axes.** Failure mode and task correctness are scored separately, and
  they disagree often enough to matter.
- **Scenario, not trial, is the unit.** Trials of a scenario agree 81% of the
  time; treating them as independent inflates significance roughly fourfold.

## Grading

Step repetition is graded deterministically from the trace (three tiers, with
exemptions for legitimate retries). The other four modes use an LLM judge
(claude-opus-5), validated three times against blind human labels: 96% and
96.7% (κ=0.93) on qwen traces, 87.5% (κ=0.75) on GPT traces, where a known
leniency is documented and bounded.

## Results and data

| Document | Contents |
|---|---|
| [`PHASE_1_RESULTS_100.md`](PHASE_1_RESULTS_100.md) | Main study: 100 scenarios × 3 frameworks × 4 trials |
| [`PROMPT_ABLATION_RESULTS.md`](PROMPT_ABLATION_RESULTS.md) | Prompt transplant: the cause |
| [`PHASE_1D_RESULTS.md`](PHASE_1D_RESULTS.md) | gpt-5.4-mini cross-check |
| [`SENTENCE_ABLATION_RESULTS.md`](SENTENCE_ABLATION_RESULTS.md) | The one-sentence experiment |
| [`paper/`](paper/) | Paper draft; figures regenerate from the data |
| `results/` | Every trace, judge verdict and graded row from all 2,880 runs |

Older documents in the repository root record how the study developed,
including a discarded run whose prompts leaked grader rationale
([`PHASE_1_REWRITE_LOG.md`](PHASE_1_REWRITE_LOG.md)).

## Reproduce

```bash
pip install -e ".[all,dev]"
python -m tests.test_prompt_hygiene   # scenario prompts stay agent-facing
python -m tests.test_grader           # deterministic grader
python -m tests.test_correctness      # ground-truth checks
python -m tests.test_world            # mock world is pinned
python analyze_100.py                 # main statistics, no API calls
python paper/make_figures.py          # figures + numbers for the paper
```

Grading everything again costs money; every graded verdict is cached in
`results/*/judge_cache.json`, so the statistics above re-run for free.

## Limitations

- Measured with **LangGraph 1.2.11, CrewAI 1.15.17, openai-agents 0.22.2** in
  September 2026. Framework defaults change; re-run `capture` on your versions.
- Two models (qwen2.5 7B, gpt-5.4-mini). On the stronger model the repetition
  and termination effects mostly disappear; the clarification effect does not.
- Part of CrewAI's scaffolding is wording this harness supplied for fields
  CrewAI requires; the ablations separate the two, and both carry the effect.
- One synthetic mock environment with nine tools.
- Only 15 of 100 scenarios involve an agent-to-agent handoff, and they show no
  framework difference. MAST's inter-agent failure modes are not covered.

## Citation

```bibtex
@misc{agentstress2026,
  title  = {The Prompt Is the Framework: Agent Framework Scaffolding,
            Not Orchestration, Drives Failure Rates},
  author = {Patel, Arth},
  year   = {2026},
  note   = {Preprint}
}
```

## License

MIT — see [LICENSE](LICENSE).
