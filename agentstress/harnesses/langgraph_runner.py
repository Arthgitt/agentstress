"""Minimal LangGraph agent harness: runs a Scenario, returns a filled-in Trace.

Two architectures, both built on langgraph.prebuilt.create_react_agent:
  - "single":  one ReAct agent/graph handles the whole task.
  - "handoff": two independently-invoked ReAct agents in sequence — a
      "researcher" (restricted, read-only tools) whose final text answer is
      spliced into the "writer" agent's prompt, mirroring a two-node graph
      where node B receives node A's output as input.
"""
from __future__ import annotations

import time

from agentstress.harnesses.langgraph_tools import get_tools
from agentstress.scenarios import Scenario
from agentstress.trace import Trace, set_actor

from agentstress.run_config import RECURSION_LIMIT
from agentstress.harnesses.models import langchain_chat_model


def _make_model():
    return langchain_chat_model()


def _run_agent(prompt: str, tool_names: list[str], actor: str) -> str:
    from langgraph.prebuilt import create_react_agent

    set_actor(actor)
    agent = create_react_agent(_make_model(), get_tools(tool_names))
    result = agent.invoke(
        {"messages": [{"role": "user", "content": prompt}]},
        config={"recursion_limit": RECURSION_LIMIT},
    )
    final = result["messages"][-1]
    return getattr(final, "content", str(final))


def run_scenario(scenario: Scenario, trace: Trace) -> None:
    start = time.time()
    try:
        if scenario.architecture == "single":
            answer = _run_agent(scenario.prompt, scenario.tools, "agent")
            trace.final_answer = answer
        elif scenario.architecture == "handoff":
            findings = _run_agent(scenario.researcher_prompt, scenario.researcher_tools, "researcher")
            writer_prompt = scenario.writer_prompt_template.format(findings=findings)
            answer = _run_agent(writer_prompt, scenario.writer_tools, "writer")
            trace.final_answer = answer
        else:
            raise ValueError(f"Unknown architecture: {scenario.architecture}")
    except Exception as e:
        trace.error = f"{type(e).__name__}: {e}"
    trace.wall_seconds = time.time() - start
