"""Minimal OpenAI Agents SDK harness: runs a Scenario, returns a filled-in Trace.

Points at the LOCAL Ollama server through its OpenAI-compatible endpoint
(`/v1`), NOT at OpenAI's hosted API. That is deliberate and load-bearing: the
Phase 1 comparison attributes differences to framework orchestration, which
only holds if every framework drives the same weights. Swapping this harness to
a hosted frontier model while LangGraph and CrewAI stay on qwen2.5 would
confound the headline result. The Phase 1d cross-check moves ALL THREE
frameworks to a frontier model together, which is the controlled way to ask
whether the finding survives a stronger model.

Two architectures, matching the other harnesses:
  - "single":  one agent handles the whole task.
  - "handoff": a researcher agent runs, and its literal text output is spliced
      into the writer agent's prompt.
"""
from __future__ import annotations

import time

from agents import Agent, ModelSettings, Runner, set_tracing_disabled

from agentstress.scenarios_phase1 import Scenario
from agentstress.trace import Trace, set_actor
from agentstress.harnesses.models import openai_agents_model
from agentstress.harnesses.openai_tools_impl import get_tools

from agentstress.run_config import MAX_ITERATIONS as MAX_TURNS, TEMPERATURE

# The SDK ships traces to OpenAI's backend by default. Kept off on both
# backends: nothing about these runs should leave the machine except the model
# calls themselves.
set_tracing_disabled(True)


def _model():
    return openai_agents_model()


def _run_agent(prompt: str, tool_names: list[str], actor: str, name: str) -> str:
    set_actor(actor)
    agent = Agent(
        name=name,
        instructions=(
            "You are a focused operational assistant with access to internal "
            "company tools. Complete the assigned task accurately."
        ),
        tools=get_tools(tool_names),
        model=_model(),
        model_settings=ModelSettings(temperature=TEMPERATURE),
    )
    result = Runner.run_sync(agent, prompt, max_turns=MAX_TURNS)
    return str(result.final_output or "")


def run_scenario(scenario: Scenario, trace: Trace) -> None:
    start = time.time()
    try:
        if scenario.architecture == "single":
            trace.final_answer = _run_agent(scenario.prompt, scenario.tools, "agent", "Task Agent")
        elif scenario.architecture == "handoff":
            findings = _run_agent(
                scenario.researcher_prompt, scenario.researcher_tools, "researcher", "Researcher"
            )
            writer_prompt = scenario.writer_prompt_template.format(findings=findings)
            trace.final_answer = _run_agent(
                writer_prompt, scenario.writer_tools, "writer", "Writer"
            )
        else:
            raise ValueError(f"Unknown architecture: {scenario.architecture}")
    except Exception as e:
        trace.error = f"{type(e).__name__}: {e}"
    trace.wall_seconds = time.time() - start
