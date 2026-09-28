"""Check whether Crew(prompt_file=...) actually reaches the task prompt.

CrewAI documents `prompt_file` as the way to override prompt slices, including
`slices.expected_output`, which carries the sentence measured in
SENTENCE_ABLATION_RESULTS.md. This script writes a custom prompt file with a
marker in that slice, runs one scenario through a logging proxy, and reports
whether the marker or the default sentence reached the model.

Against crewai 1.15.17 the marker never arrives: task.py resolves the slice from
the global I18N_DEFAULT rather than the crew's prompt_file. Reported upstream as
crewAIInc/crewAI#7766.

Needs Ollama running. Run:  python -m experiments.verify_prompt_file_override
"""
from __future__ import annotations

import json
import os

os.environ.setdefault("CREWAI_TELEMETRY_OPT_OUT", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

import sys  # noqa: E402
import tempfile  # noqa: E402
from pathlib import Path  # noqa: E402

import crewai  # noqa: E402

import agentstress.run_config as rc  # noqa: E402
from agentstress import proxy  # noqa: E402
from agentstress.harnesses.crewai_tools_impl import get_tools  # noqa: E402
from agentstress.harnesses.models import crewai_llm  # noqa: E402
from agentstress.scenarios_phase1 import BY_ID_PHASE1  # noqa: E402
from agentstress.tools import default_world  # noqa: E402
from agentstress.trace import Trace, set_actor, set_run_context  # noqa: E402

SENTENCE = "you MUST return the actual complete content as the final answer, not a summary."
MARKER = "CUSTOM-PROMPT-FILE-MARKER"


def main(scenario_id: str = "FAQ-12") -> int:
    src = Path(crewai.__file__).parent / "translations" / "en.json"
    custom = json.loads(src.read_text())
    custom["slices"]["expected_output"] = (
        "\nThis is the expected criteria for your final answer: {expected_output}\n"
        f"{MARKER}: return the complete content, or state clearly what information is missing."
    )
    cf = Path(tempfile.mkdtemp()) / "custom_prompts.json"
    cf.write_text(json.dumps(custom))

    upstream = rc.OLLAMA_BASE_URL
    srv = proxy.start()
    proxy.upstream = lambda: upstream
    rc.OLLAMA_BASE_URL = f"http://127.0.0.1:{proxy.PORT}"

    sc = BY_ID_PHASE1[scenario_id]
    set_run_context(Trace(scenario_id=sc.id, framework="crewai", architecture="single"), default_world())
    set_actor("agent")
    agent = crewai.Agent(
        role="Task Agent",
        goal="Complete the assigned task accurately using the available tools.",
        backstory="A focused operational assistant with access to internal company tools.",
        tools=get_tools(sc.tools), llm=crewai_llm(), verbose=False, max_iter=3, allow_delegation=False,
    )
    task = crewai.Task(description=sc.prompt,
                       expected_output="A final answer that completes the task exactly as instructed.",
                       agent=agent)
    crew = crewai.Crew(agents=[agent], tasks=[task], process=crewai.Process.sequential,
                       verbose=False, prompt_file=str(cf))
    print(f"crewai {crewai.__version__} | scenario {sc.id} | prompt_file={cf}")
    try:
        crew.kickoff()
    except Exception as e:  # the request is what matters, not the completion
        print(f"(run ended early: {type(e).__name__} — the captured request is still valid)")
    srv.shutdown()

    sent = "\n".join(m.get("content") or "" for r in proxy.LOG for m in r["body"].get("messages", []))
    marker, default = MARKER in sent, SENTENCE in sent
    print(f"  custom slice reached the model : {marker}")
    print(f"  default sentence reached model : {default}")
    if not marker and default:
        print("\nprompt_file was silently ignored for the task prompt (crewAIInc/crewAI#7766).")
        return 1
    print("\nprompt_file reached the task prompt — the upstream fix appears to be in place.")
    return 0


if __name__ == "__main__":
    sys.exit(main(*sys.argv[1:]))
