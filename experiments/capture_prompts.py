"""Record the exact requests each framework sends to the model.

Starts a logging HTTP proxy in front of Ollama, points all three harnesses at
it, runs one scenario per framework, and writes every request body to
results/prompt_capture/. Free (local Ollama only).

Run:  python -m experiments.capture_prompts FAQ-12
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import agentstress.run_config as rc
from agentstress.proxy import CURRENT, LOG, PORT, Proxy, start  # noqa: F401  (re-exported)

OUT = Path("results/prompt_capture")


def main(sid: str) -> None:
    srv = start(PORT)
    rc.OLLAMA_BASE_URL = f"http://127.0.0.1:{PORT}"
    rc.OLLAMA_OPENAI_BASE_URL = f"http://127.0.0.1:{PORT}/v1"

    import importlib
    from agentstress.scenarios_phase1 import BY_ID_PHASE1
    from agentstress.tools import default_world
    from agentstress.trace import Trace, set_run_context

    sc = BY_ID_PHASE1[sid]
    OUT.mkdir(parents=True, exist_ok=True)
    for fw, mod in (("langgraph", "harnesses.langgraph_runner"), ("crewai", "harnesses.crewai_runner"),
                    ("openai_agents", "harnesses.openai_runner")):
        CURRENT["fw"] = fw
        tr = Trace(scenario_id=sid, framework=fw, architecture=sc.architecture)
        set_run_context(tr, default_world())
        importlib.import_module(mod).run_scenario(sc, tr)
        print(fw, "calls:", [c.tool for c in tr.calls], "| error:", tr.error)
    (OUT / f"{sid}.json").write_text(json.dumps(LOG, indent=2))
    print("requests captured:", len(LOG), "->", OUT / f"{sid}.json")
    srv.shutdown()


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "FAQ-12")
