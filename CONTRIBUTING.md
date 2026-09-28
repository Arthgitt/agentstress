# Contributing to agentstress

Contributions are welcome, especially new scenarios, support for additional
frameworks, and independent runs on models I have not tested.

## Getting help / asking questions

Open an issue with the **question** label at
<https://github.com/Arthgitt/agentstress/issues>. There is no mailing list or
chat; issues are the single channel, so answers stay searchable.

## Reporting a problem

Open an issue and include:

- what you ran (the exact `agentstress` command)
- framework and version, model, and how it was served (Ollama, hosted API)
- what you expected and what happened
- the trace JSON if a run behaved oddly — it contains every tool call and is
  usually enough to diagnose the problem

A grading result you disagree with is a legitimate issue. Include the trace and
say what you would have scored it; disagreements about the rubric are how the
graders improve.

## Development setup

```bash
git clone https://github.com/Arthgitt/agentstress
cd agentstress
python -m venv venv && source venv/bin/activate
pip install -e ".[all,dev]"
```

Run the suites that need no model and no API key:

```bash
python -m tests.test_prompt_hygiene   # scenario prompts stay agent-facing
python -m tests.test_grader           # deterministic step-repetition grader
python -m tests.test_correctness      # ground-truth answer checks
python -m tests.test_judge_parse      # judge response parsing
python -m tests.test_judge_context    # judge-facing notes carry no results
python -m tests.test_world            # the pinned mock world has not drifted
```

CI runs all of these on Python 3.10 and 3.12 for every pull request.

## Adding a scenario

Scenarios live in `agentstress/scenarios_phase1.py` and
`agentstress/scenarios_expansion.py`. Two rules are enforced by tests, and both
exist because breaking them silently invalidates results:

1. **Agent-facing text must not leak the experiment.** No scenario prompt may
   name a failure mode, describe grading, or forbid a behaviour. The failure
   should be *available and tempting*, never requested or prohibited.
   `test_prompt_hygiene` enforces this.
2. **Design notes must not cite results.** `structural_reason` is shown to the
   LLM judge, so it must not mention frameworks or earlier outcomes.
   `test_judge_context` enforces this.

If your scenario has a checkable right answer, add ground truth to
`agentstress/correctness.py` so both axes are scored. Controls — scenarios where
the failure is *not* available — are as valuable as provocations.

## Adding a framework

Add a harness in `agentstress/harnesses/` exposing `run_scenario(scenario,
trace)`, wrapping the shared tool implementations from `agentstress/tools.py` so
tool semantics stay identical across frameworks, then register it in
`FRAMEWORKS` in `agentstress/cli.py`.

Before reporting any comparison, run `agentstress capture` against the new
framework and check what it actually sends the model. Frameworks add their own
prompt scaffolding, and that scaffolding — not the orchestration — accounts for
most of the differences measured so far.

## Changing graders or the mock world

Existing published traces were produced against a pinned world and pinned
grader behaviour. If you change either, say so explicitly in the pull request
and expect `test_world` or `test_grader` to fail; those failures are the point.
Do not edit the frozen copies inside the tests.

## Pull requests

Keep changes focused, match the surrounding style (comments explain *why*, not
*what*), and add a test for anything that could silently regress. New results
should come with the traces that produced them.
