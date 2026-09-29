---
title: 'agentstress: a provocation benchmark for LLM agent framework failure modes'
tags:
  - Python
  - large language models
  - agents
  - benchmarking
  - evaluation
  - reliability
authors:
  - name: Arth Patel
    orcid: 0009-0001-0054-8717
    affiliation: 1
affiliations:
  - index: 1
    name: Independent researcher, United States
date: 26 September 2026
bibliography: paper.bib
---

# Summary

`agentstress` measures *how* large-language-model agents fail, not merely
whether they succeed. It ships 100 scenarios engineered to make a specific
failure mode available and tempting — repeating a step whose answer the agent
already holds, acting on an underspecified request instead of asking, claiming a
result it never read back — and runs each scenario identically across
LangGraph, CrewAI and the OpenAI Agents SDK, against local models served by
Ollama or hosted models. Failure modes follow the MAST taxonomy of multi-agent
failures [@mast].

Every run produces a trace of tool calls and artifacts, which is then scored on
two independent axes: whether the target failure mode occurred, and whether the
task was actually completed correctly. Step repetition is graded
deterministically from the trace; the remaining modes are graded by an LLM judge
whose verdicts were validated three times against blind human labels. The
package installs as a command line tool, and the scenario suite, harnesses,
graders, and all 2,880 runs behind the accompanying study are included.

A distinguishing command is `agentstress capture`, which prints the request a
framework actually sends the model for a given task. This is usually a good
deal more text than the developer wrote, and the study built with this tool
found that this hidden text — not the orchestration logic — accounts for most
of the measured difference between frameworks.

# Statement of need

Agent frameworks are typically evaluated on task success: benchmarks such as
AgentBench [@agentbench] and $\tau$-bench [@taubench] report whether an agent
completed a task in a realistic environment. Practitioners choosing a framework,
however, debug specific behaviours: an agent that files the same ticket three
times, invents a customer name rather than asking which customer was meant, or
reports a stock level it never verified. Aggregate success rates do not
distinguish those failures, and they do not say whether the framework, the
model, or the prompt is responsible.

The MAST taxonomy [@mast] named these failure modes by annotating real traces,
but naming them left two practical gaps: no runnable suite provokes them on
demand, and no tooling attributes an observed failure to a controllable cause.
`agentstress` addresses both. Scenarios are constructed so that a failure is
available without being requested, agent-facing text never mentions failure
modes or grading, and eight control scenarios make the failure genuinely
unavailable so that over-flagging graders are detectable.

The intended users are developers choosing or debugging an agent stack, and
researchers measuring agent reliability. For developers, `capture` and a short
scenario run answer "is this my framework's prompt or my model?" in minutes,
entirely on a local model with no API key. For researchers, the package provides
a scenario suite with enforced prompt hygiene, graders with published human
validation, and complete traces for reanalysis.

# State of the field

Existing agent benchmarks measure end-to-end task completion
[@agentbench; @taubench]. `agentstress` is complementary rather than competing:
it reports failure-mode incidence and task correctness separately, and in the
accompanying study the two axes disagreed often enough to matter — a framework
with a clean step-repetition record wrote the wrong value in 8 of 8 trials of
one scenario, while the framework flagged for repetition wrote the right one by
re-checking. A benchmark reporting only failure-mode counts would have ranked
the first as more reliable.

LLM-as-a-judge evaluation is well established [@judge]. Two practices are built
into this package rather than left to the user: the judge model family is never
the family under test, and judge verdicts are validated against blind human
labels for each model family scored, with a documented sensitivity bound where
agreement is weaker. In the accompanying study, agreement was 96% and 96.7%
($\kappa = 0.93$) on one model but 87.5% ($\kappa = 0.75$) on a stronger one,
where the judge systematically mis-scored a specific case; that gap is reported
with a strict bound rather than papered over by re-tuning the judge mid-study.

Prompt sensitivity is itself a well-studied phenomenon, but it is normally
studied as a property of prompts the developer writes. `agentstress` targets
scaffolding the developer does not write and often never sees.

# Software design

Tool implementations are shared: a single set of Python functions operating on a
deterministic mock world (nine tools — document search, file read/write,
inventory read/update, weather, user profiles, ticket creation, arithmetic) is
wrapped by each framework's own decorator. Tool semantics are therefore
identical across frameworks by construction, and only framework machinery
differs. Two semantics are load-bearing: mutating tools return a bare
acknowledgement instead of the resulting state, and inventory is clamped at
zero, so an agent that reports a post-write value must read it back. Without
this, verification failures cannot be measured at all.

Traces are recorded through `contextvars`, so framework-agnostic tool functions
record themselves without any framework needing to expose a hook. Grading is
split: a three-tier deterministic grader handles step repetition (identical
calls, same target artifact, same result from a read-only tool, with exemptions
for retries after errors and for scenarios that legitimately repeat a mutation),
while the remaining modes use a judge with per-mode rubrics. Grading is
separated from running, so an interrupted or malformed run costs time rather
than money, and judge verdicts are cached so reanalysis is free.

A convention worth naming: **the artifact is the action**. When an agent's chat
reply and the artifact it produced disagree, the artifact is graded. Small
models frequently state the correct answer in conversation while writing
`[placeholder]` into the ticket a downstream system would actually receive.

![Transplanting one framework's prompt scaffolding into another reproduces its
failure rate. Hatched bars are frameworks running another framework's
scaffolding.\label{fig:transplant}](prompt_transplant.png)

# Research impact

The package was built for, and produced, a study of agent framework reliability
across 2,880 runs on two models. Using identical tasks, tools and decoding
settings, failure rates on the three modes where frameworks differed were 14.6%
(LangGraph), 24.2% (OpenAI Agents SDK) and 47.1% (CrewAI). Prompt-transplant
experiments implemented with the package's `capture` machinery then showed the
cause is the scaffolding text rather than the orchestration
(\autoref{fig:transplant}): given CrewAI's exact messages, the other two
frameworks became statistically indistinguishable from it, and CrewAI given
neutral wording fell to 29.2%. Isolating a single sentence that one framework
appends to every task roughly doubled clarification failures on both a 7B local
model [@qwen] and a hosted mid-size model.

For practitioners the actionable result is that a framework's default prompt is
part of its reliability profile and is invisible in application code; `capture`
makes it visible in one command.

The findings have had effect outside the study. The scaffolding behaviour was
reported to the framework's maintainers
([crewAIInc/crewAI#7766](https://github.com/crewAIInc/crewAI/issues/7766)),
where contributors located the responsible call sites and proposed a fix. That
report also established that the documented mechanism for overriding the text in
question has been silently ineffective since 2024, across two issues closed
without a fix ([#1384](https://github.com/crewAIInc/crewAI/issues/1384),
[#5931](https://github.com/crewAIInc/crewAI/issues/5931)); the package includes a
script that re-checks this in one command. The `capture` command and the released
traces are what made the behaviour reportable as a measurement rather than an
anecdote. All traces, judge verdicts, human-label sets
and analysis scripts are released with the package so every figure can be
regenerated without re-running any model.

# AI usage disclosure

This software and paper were developed with substantial assistance from a
generative AI coding assistant (Anthropic's Claude, via Claude Code), used for
implementation, experiment orchestration, analysis scripting, and drafting. The
author designed the study, made all research and methodological decisions,
produced the human label sets used to validate the judge by hand and blind,
reviewed all results against raw traces, and is responsible for the conclusions.
Several errors found during the study — including a grader rule that
contradicted the tool schema — were caught by that human review.

# Acknowledgements

No funding was received for this work. Thanks to the authors of the MAST
taxonomy, whose per-mode analysis defined what this benchmark provokes.

# References
