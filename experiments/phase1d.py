"""Phase 1d — frontier cross-check on gpt-5.4-mini.

Asks the two Phase 1 questions again on a stronger model:
  1. Does CrewAI still show more SR / UT / FAQ failures than the other two?
  2. Is that still the prompt scaffolding rather than the orchestration?

Six setups, same as Phase 1 + the prompt ablation, all on gpt-5.4-mini:
  langgraph, crewai, openai_agents            harnesses exactly as in Phase 1
  lg_crewprompt, oai_crewprompt, crew_neutral  experiments/prompt_ablation.py
60 scenarios (all core SR, UT, FAQ) x 6 setups x 2 trials = 720 runs.

Agents are GPT, the judge stays Claude (different model families, as the
method requires). Temperature 0.3 and Chat Completions for every framework.

Cost control: all model traffic passes through a local metering proxy
(experiments/usage_proxy.py). The run stops before starting a job once agent
spend reaches --cap. Trial 1 of every scenario x setup runs before any trial 2,
so a stop leaves a balanced dataset.

Run:  python -m experiments.phase1d --pilot     # 1 scenario x 6 setups, prompt check, ~1 cent
      python -m experiments.phase1d             # full run, resumable
"""
from __future__ import annotations

import os
import sys

PORT = 11600
os.environ["AGENT_PROVIDER"] = "openai"
os.environ["AGENT_OPENAI_BASE_URL"] = f"http://127.0.0.1:{PORT}/v1"
os.environ.setdefault("CREWAI_TELEMETRY_OPT_OUT", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

from dotenv import dotenv_values  # noqa: E402

_key = dotenv_values(".env").get("OPENAI_API_KEY")
if not _key:
    sys.exit("OPENAI_API_KEY missing from .env")
os.environ["OPENAI_API_KEY"] = _key.strip()

import argparse  # noqa: E402
import importlib  # noqa: E402
import json  # noqa: E402
import time  # noqa: E402
from pathlib import Path  # noqa: E402

import agentstress.run_config as rc  # noqa: E402
from agentstress.tools import default_world  # noqa: E402
from agentstress.trace import Trace, set_run_context  # noqa: E402
from experiments import prompt_ablation as abl  # noqa: E402
from experiments import usage_proxy as proxy  # noqa: E402

assert rc.PROVIDER == "openai" and rc.OPENAI_BASE_URL.startswith("http://127.0.0.1")

OUT = Path("results/phase1d/traces")
TRIALS = 2
BASE = {
    "langgraph": "harnesses.langgraph_runner",
    "crewai": "harnesses.crewai_runner",
    "openai_agents": "harnesses.openai_runner",
}
SETUPS = list(BASE) + abl.CONDITIONS


def run_one(setup: str, sc) -> Trace:
    tr = Trace(scenario_id=sc.id, framework=setup, architecture=sc.architecture)
    set_run_context(tr, default_world())
    if setup in BASE:
        try:
            importlib.import_module(BASE[setup]).run_scenario(sc, tr)
        except Exception as e:  # harness blew up outside its own try
            tr.error = f"{type(e).__name__}: {e}"
    else:
        abl.run_scenario(setup, sc, tr)
    return tr


def payload(sc, setup, trial, tr, used):
    return {
        "scenario_id": sc.id, "scenario_name": sc.name, "target_mode": sc.target_mode,
        "architecture": sc.architecture, "is_control": sc.is_control,
        "is_exploratory": sc.is_exploratory, "framework": setup, "trial": trial,
        "model": rc.OPENAI_MODEL, "temperature": rc.TEMPERATURE,
        "expected_clean_calls": sc.expected_clean_calls,
        "agent_output": tr.final_answer, "agent_error": tr.error,
        "wall_seconds": round(tr.wall_seconds, 2),
        "usage": {**used, "cost_usd": round(proxy.cost(used), 6)},
        "trace": tr.to_json(),
    }


def delta(before: dict, after: dict) -> dict:
    return {k: after[k] - before[k] for k in after}


def pilot() -> int:
    """FAQ-12 once per setup: checks every setup runs on GPT, that the swapped
    setups send CrewAI's exact first messages as captured on GPT, and measures
    real cost per run. Traces go to results/phase1d/_pilot and are not used."""
    from agentstress.scenarios_phase1 import BY_ID_PHASE1

    out = Path("results/phase1d/_pilot")
    out.mkdir(parents=True, exist_ok=True)
    sc = BY_ID_PHASE1["FAQ-12"]
    proxy.KEEP_BODIES["on"] = True
    first_msgs, costs = {}, []
    for setup in SETUPS:
        start = len(proxy.CAPTURE)
        before = proxy.snapshot()
        tr = run_one(setup, sc)
        used = delta(before, proxy.snapshot())
        costs.append(proxy.cost(used))
        (out / f"{sc.id}__{setup}.json").write_text(json.dumps(payload(sc, setup, 1, tr, used), indent=2))
        reqs = proxy.CAPTURE[start:]
        first_msgs[setup] = [(m["role"], m["content"]) for m in reqs[0]["body"]["messages"][:2]] if reqs else None
        print(f"{setup:15s} requests {used['requests']} tokens {used['input']}/{used['output']} "
              f"${proxy.cost(used):.5f} calls={[c.tool for c in tr.calls]} error={tr.error}")
    (out / "captured_requests.json").write_text(json.dumps(proxy.CAPTURE, indent=2))

    ok = True
    crew = first_msgs["crewai"]
    for setup in ("lg_crewprompt", "oai_crewprompt"):
        match = bool(crew) and first_msgs[setup] == crew
        ok &= match
        print(f"{setup:15s} first messages identical to CrewAI's on GPT: {match}")
        if not match:
            print("   crewai:", json.dumps(crew)[:500])
            print("   setup :", json.dumps(first_msgs[setup])[:500])
    neutral = first_msgs["crew_neutral"]
    nm = bool(neutral) and abl.NEUTRAL_GOAL in neutral[0][1] and abl.CREW_GOAL not in neutral[0][1]
    ok &= nm
    print(f"{'crew_neutral':15s} neutral wording in system prompt: {nm}")
    t = proxy.snapshot()
    print(f"pilot total ${proxy.cost(t):.4f} | mean per run ${sum(costs)/len(costs):.5f} | "
          f"requests without usage: {t['no_usage']} | http errors: {t['http_errors']}")
    print(f"projected agent cost for 720 runs: ~${720 * sum(costs) / len(costs):.2f} (FAQ-12 is a short scenario)")
    return 0 if ok else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--cap", type=float, default=3.00, help="stop before a new run once agent spend reaches this ($)")
    args = ap.parse_args()
    proxy.start(PORT)
    if args.pilot:
        return pilot()

    OUT.mkdir(parents=True, exist_ok=True)
    spent_before = sum(json.loads(p.read_text())["usage"]["cost_usd"] for p in OUT.glob("*.json"))
    jobs = [(sc, s, t) for t in range(1, TRIALS + 1) for sc in abl.scenarios() for s in SETUPS]
    todo = [j for j in jobs if not (OUT / f"{j[0].id}__{j[1]}__t{j[2]}.json").exists()]
    print(f"phase 1d on {rc.OPENAI_MODEL}: {len(abl.scenarios())} scenarios x {len(SETUPS)} setups x "
          f"{TRIALS} trials = {len(jobs)} runs | to run {len(todo)} | spent so far ${spent_before:.2f} "
          f"| cap ${args.cap:.2f}", flush=True)
    started, errors = time.time(), 0
    for n, (sc, setup, trial) in enumerate(todo, 1):
        spent = spent_before + proxy.cost(proxy.snapshot())
        if spent >= args.cap:
            print(f"STOPPED at spending cap: ${spent:.2f} >= ${args.cap:.2f} "
                  f"({n - 1} of {len(todo)} runs done this session)")
            return 2
        before = proxy.snapshot()
        tr = run_one(setup, sc)
        used = delta(before, proxy.snapshot())
        (OUT / f"{sc.id}__{setup}__t{trial}.json").write_text(json.dumps(payload(sc, setup, trial, tr, used), indent=2))
        errors += bool(tr.error)
        eta = (time.time() - started) / n * (len(todo) - n)
        print(f"[{n:4d}/{len(todo)}] {'ERR' if tr.error else 'ok '} {sc.id:8s} {setup:15s} t{trial} "
              f"{len(tr.calls):2d} calls {tr.wall_seconds:5.1f}s ${proxy.cost(used):.4f} "
              f"total ${spent_before + proxy.cost(proxy.snapshot()):.2f}  eta {eta/60:5.1f}m", flush=True)
    t = proxy.snapshot()
    print(f"done in {(time.time() - started)/60:.1f} min — {len(todo)} runs, {errors} harness error(s), "
          f"agent spend ${spent_before + proxy.cost(t):.2f}, requests without usage {t['no_usage']}, "
          f"http errors {t['http_errors']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
