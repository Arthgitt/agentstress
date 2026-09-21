"""Prompt ablation: is CrewAI's higher failure rate its orchestration or its prompt?

Captured requests (results/prompt_capture/) show the three harnesses do not send
the model the same text:
  - LangGraph      no system prompt; the task as the only user message
  - OpenAI Agents  one-sentence system prompt
  - CrewAI         role/goal/backstory system prompt, and the task wrapped in an
                   "expected criteria ... you MUST return the actual complete
                   content as the final answer" template
Tool schemas are identical, and CrewAI injects nothing after the first turn.

Conditions (same model, temperature, tools, scenarios and trials as Phase 1):
  lg_crewprompt   LangGraph loop, CrewAI's exact messages
  oai_crewprompt  OpenAI Agents loop, CrewAI's exact messages (same /v1
                  endpoint CrewAI uses, so only the loop differs from CrewAI)
  crew_neutral    CrewAI loop, our harness wording replaced by neutral wording;
                  CrewAI's fixed template sentence necessarily remains

Reading: if lg_crewprompt and oai_crewprompt rise to CrewAI's rate, the prompt
explains the gap; if they stay near their own baselines, the loop does. If
crew_neutral falls, the part we wrote (goal / expected_output) is responsible.

Scenarios: the 60 SR, UT and FAQ scenarios — the modes where Phase 1 found a
framework gap — chosen by mode before any ablation run, not scenario by
scenario, so the comparison is not built on the noisiest differences.

Agent runs are free (local Ollama). SR grades free; UT and FAQ need the judge.

Run:  python -m experiments.prompt_ablation            # all conditions, resumable
      python -m experiments.prompt_ablation --verify   # prompt text check only
"""
from __future__ import annotations

import os

os.environ.setdefault("CREWAI_TELEMETRY_OPT_OUT", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

import argparse
import json
import sys
import time
from pathlib import Path

import agentstress.run_config as rc
from agentstress.scenarios_phase1 import ALL_PHASE1
from agentstress.tools import default_world
from agentstress.trace import Trace, set_actor, set_run_context

OUT = Path("results/ablation/traces")
CONDITIONS = ["lg_crewprompt", "oai_crewprompt", "crew_neutral"]
MODES = {"SR", "UT", "FAQ"}

# CrewAI's rendered text, byte for byte as captured, with our harness values.
CREW_BACKSTORY = "A focused operational assistant with access to internal company tools."
CREW_GOAL = "Complete the assigned task accurately using the available tools."
CREW_EXPECTED = "A final answer that completes the task exactly as instructed."

# Neutral replacements for the three strings we chose (crew_neutral only).
NEUTRAL_ROLE = "Assistant"
NEUTRAL_BACKSTORY = "An assistant with access to internal company tools."
NEUTRAL_GOAL = "Respond to the user's request."
NEUTRAL_EXPECTED = "A response to the request."


def crew_system(role: str) -> str:
    return f"You are {role}. {CREW_BACKSTORY}\nYour personal goal is: {CREW_GOAL}"


def crew_user(prompt: str) -> str:
    return (
        f"\nCurrent Task: {prompt}\n\n"
        f"This is the expected criteria for your final answer: {CREW_EXPECTED}\n"
        "you MUST return the actual complete content as the final answer, not a summary."
    )


# --- condition runners: (prompt, tools, actor, role) -> final text ----------

def _lg(prompt, tool_names, actor, role):
    from langgraph.prebuilt import create_react_agent

    from agentstress.harnesses.langgraph_tools import get_tools
    from agentstress.harnesses.models import langchain_chat_model

    set_actor(actor)
    agent = create_react_agent(langchain_chat_model(), get_tools(tool_names), prompt=crew_system(role))
    result = agent.invoke(
        {"messages": [{"role": "user", "content": crew_user(prompt)}]},
        config={"recursion_limit": rc.RECURSION_LIMIT},
    )
    final = result["messages"][-1]
    return getattr(final, "content", str(final))


def _oai(prompt, tool_names, actor, role):
    from agents import Agent, ModelSettings, Runner, set_tracing_disabled

    from agentstress.harnesses.models import openai_agents_model
    from agentstress.harnesses.openai_tools_impl import get_tools

    set_tracing_disabled(True)
    set_actor(actor)
    agent = Agent(
        name=role,
        instructions=crew_system(role),
        tools=get_tools(tool_names),
        model=openai_agents_model(),
        model_settings=ModelSettings(temperature=rc.TEMPERATURE),
    )
    result = Runner.run_sync(agent, crew_user(prompt), max_turns=rc.MAX_ITERATIONS)
    return str(result.final_output or "")


def _crew_neutral(prompt, tool_names, actor, role):
    from crewai import Agent, Crew, Process, Task

    from agentstress.harnesses.crewai_tools_impl import get_tools
    from agentstress.harnesses.models import crewai_llm

    set_actor(actor)
    llm = crewai_llm()
    agent = Agent(role=NEUTRAL_ROLE, goal=NEUTRAL_GOAL, backstory=NEUTRAL_BACKSTORY,
                  tools=get_tools(tool_names), llm=llm, verbose=False,
                  max_iter=rc.MAX_ITERATIONS, allow_delegation=False)
    task = Task(description=prompt, expected_output=NEUTRAL_EXPECTED, agent=agent)
    result = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=False).kickoff()
    return str(result.raw) if hasattr(result, "raw") else str(result)


RUNNERS = {"lg_crewprompt": _lg, "oai_crewprompt": _oai, "crew_neutral": _crew_neutral}


def run_scenario(cond: str, sc, trace: Trace) -> None:
    run = RUNNERS[cond]
    start = time.time()
    try:
        if sc.architecture == "single":
            trace.final_answer = run(sc.prompt, sc.tools, "agent", "Task Agent")
        else:
            findings = run(sc.researcher_prompt, sc.researcher_tools, "researcher", "Researcher")
            trace.final_answer = run(sc.writer_prompt_template.format(findings=findings),
                                     sc.writer_tools, "writer", "Writer")
    except Exception as e:
        trace.error = f"{type(e).__name__}: {e}"
    trace.wall_seconds = time.time() - start


def scenarios():
    return [s for s in ALL_PHASE1 if s.target_mode in MODES and not s.is_exploratory]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()
    if args.verify:
        return verify()

    OUT.mkdir(parents=True, exist_ok=True)
    jobs = [(sc, c, t) for sc in scenarios() for c in CONDITIONS for t in range(1, rc.TRIALS + 1)]
    todo = [j for j in jobs if not (OUT / f"{j[0].id}__{j[1]}__t{j[2]}.json").exists()]
    print(f"prompt ablation: {len(scenarios())} scenarios x {len(CONDITIONS)} conditions x "
          f"{rc.TRIALS} trials = {len(jobs)} runs | to run {len(todo)}", flush=True)
    started, errors = time.time(), 0
    for n, (sc, cond, trial) in enumerate(todo, 1):
        tr = Trace(scenario_id=sc.id, framework=cond, architecture=sc.architecture)
        set_run_context(tr, default_world())
        run_scenario(cond, sc, tr)
        payload = {
            "scenario_id": sc.id, "scenario_name": sc.name, "target_mode": sc.target_mode,
            "architecture": sc.architecture, "is_control": sc.is_control,
            "is_exploratory": sc.is_exploratory, "framework": cond, "trial": trial,
            "temperature": rc.TEMPERATURE, "expected_clean_calls": sc.expected_clean_calls,
            "agent_output": tr.final_answer, "agent_error": tr.error,
            "wall_seconds": round(tr.wall_seconds, 2), "trace": tr.to_json(),
        }
        (OUT / f"{sc.id}__{cond}__t{trial}.json").write_text(json.dumps(payload, indent=2))
        errors += bool(tr.error)
        eta = (time.time() - started) / n * (len(todo) - n)
        print(f"[{n:4d}/{len(todo)}] {'ERR' if tr.error else 'ok '} {sc.id:8s} {cond:15s} t{trial} "
              f"{len(tr.calls):2d} calls {tr.wall_seconds:6.1f}s  eta {eta/60:5.1f}m", flush=True)
    print(f"done in {(time.time() - started)/60:.1f} min — {len(todo)} runs, {errors} harness error(s)")
    return 0


def verify() -> int:
    """Run one scenario per condition through a logging proxy and check the
    model receives CrewAI's captured text exactly."""
    import threading
    from http.server import ThreadingHTTPServer

    from agentstress.scenarios_phase1 import BY_ID_PHASE1
    from experiments import capture_prompts as cp

    srv = ThreadingHTTPServer(("127.0.0.1", cp.PORT), cp.Proxy)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    rc.OLLAMA_BASE_URL = f"http://127.0.0.1:{cp.PORT}"
    rc.OLLAMA_OPENAI_BASE_URL = f"http://127.0.0.1:{cp.PORT}/v1"

    ref = json.loads(Path("results/prompt_capture/FAQ-12.json").read_text())
    crew_first = next(r for r in ref if r["framework"] == "crewai")["body"]["messages"][:2]
    sc = BY_ID_PHASE1["FAQ-12"]
    ok = True
    for cond in CONDITIONS:
        cp.LOG.clear()
        cp.CURRENT["fw"] = cond
        tr = Trace(scenario_id=sc.id, framework=cond, architecture=sc.architecture)
        set_run_context(tr, default_world())
        run_scenario(cond, sc, tr)
        first = cp.LOG[0]["body"]["messages"][:2]
        sent = [(m["role"], m["content"]) for m in first]
        want = [(m["role"], m["content"]) for m in crew_first]
        if cond == "crew_neutral":
            match = NEUTRAL_GOAL in sent[0][1] and CREW_GOAL not in sent[0][1] and NEUTRAL_EXPECTED in sent[1][1]
        else:
            match = sent == want
        ok &= match
        print(f"{cond:15s} {'MATCH' if match else 'DIFFERS'}  calls={[c.tool for c in tr.calls]} error={tr.error}")
        if not match:
            print("   sent:", json.dumps(sent)[:600])
            print("   want:", json.dumps(want)[:600])
    srv.shutdown()
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
