"""Minimal CrewAI agent harness: runs a Scenario, returns a filled-in Trace.

Two architectures, both built from single-agent CrewAI Crews (Process.sequential,
one Agent, one Task) invoked with .kickoff():
  - "single":  one crew handles the whole task.
  - "handoff": two crews run in sequence — a "researcher" crew (restricted,
      read-only tools) whose final text output is spliced into the "writer"
      crew's task description, mirroring a two-agent handoff.

To keep the LangGraph vs. CrewAI comparison matched, "handoff" is
operationalized identically in both harnesses: run phase 1, take its literal
text output, substitute it into phase 2's prompt template, run phase 2. This
is a deliberate simplification of CrewAI's native context-object passing,
chosen so the two frameworks receive the exact same prompt text and only
their internal tool-calling/orchestration machinery differs.
"""
from __future__ import annotations

import os

# Must be set before crewai is imported. CrewAI exports OpenTelemetry spans to
# telemetry.crewai.com; on a machine without outbound access to that host each
# export blocks for a 30s timeout. The Phase 1c stage-1 run logged 526 such
# timeouts, which inflated CrewAI's measured wall time and stretched a ~1 hour
# run to over 6 hours. Opting out costs nothing and removes a confound from any
# latency comparison.
os.environ.setdefault("CREWAI_TELEMETRY_OPT_OUT", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

import time

from crewai import Agent, Crew, Process, Task

from agentstress.harnesses.crewai_tools_impl import get_tools
from agentstress.scenarios import Scenario
from agentstress.trace import Trace, set_actor

from agentstress.run_config import MAX_ITERATIONS
from agentstress.harnesses.models import crewai_llm

MAX_ITER = MAX_ITERATIONS


def _make_llm():
    return crewai_llm()


def _run_agent(prompt: str, tool_names: list[str], actor: str, role: str) -> str:
    set_actor(actor)
    agent = Agent(
        role=role,
        goal="Complete the assigned task accurately using the available tools.",
        backstory="A focused operational assistant with access to internal company tools.",
        tools=get_tools(tool_names),
        llm=_make_llm(),
        verbose=False,
        max_iter=MAX_ITER,
        allow_delegation=False,
    )
    task = Task(
        description=prompt,
        expected_output="A final answer that completes the task exactly as instructed.",
        agent=agent,
    )
    crew = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False)
    result = crew.kickoff()
    return str(result.raw) if hasattr(result, "raw") else str(result)


def run_scenario(scenario: Scenario, trace: Trace) -> None:
    start = time.time()
    try:
        if scenario.architecture == "single":
            answer = _run_agent(scenario.prompt, scenario.tools, "agent", "Task Agent")
            trace.final_answer = answer
        elif scenario.architecture == "handoff":
            findings = _run_agent(
                scenario.researcher_prompt, scenario.researcher_tools, "researcher", "Researcher"
            )
            writer_prompt = scenario.writer_prompt_template.format(findings=findings)
            answer = _run_agent(writer_prompt, scenario.writer_tools, "writer", "Writer")
            trace.final_answer = answer
        else:
            raise ValueError(f"Unknown architecture: {scenario.architecture}")
    except Exception as e:
        trace.error = f"{type(e).__name__}: {e}"
    trace.wall_seconds = time.time() - start
