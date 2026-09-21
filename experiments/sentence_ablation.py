"""One-sentence ablation: does CrewAI's fixed template sentence suppress asking?

Phase 1d left one candidate for the clarification (FAQ) effect that survives on
a stronger model: the sentence CrewAI appends to every task and that its API
cannot turn off —

    "you MUST return the actual complete content as the final answer, not a summary."

Two LangGraph conditions on the 20 core FAQ scenarios, on both models:
  lg_sentence         no system prompt (as LangGraph baseline), the task
                      followed by that sentence alone              -> sufficient?
  lg_crew_nosentence  CrewAI's full prompt (role/goal/backstory system prompt
                      and task wrapper) with only that sentence removed -> necessary?

Compared against data already on disk for the same scenarios and model:
  langgraph      baseline (Phase 1 / Phase 1d)
  lg_crewprompt  CrewAI's full prompt (prompt ablation / Phase 1d)

Trials match the existing data: 4 on qwen2.5:7b (free), 2 on gpt-5.4-mini.

Run:  python -m experiments.sentence_ablation --model qwen    # local, ~1 h
      python -m experiments.sentence_ablation --model gpt     # ~5 min, cents
      python -m experiments.sentence_ablation --analyze       # after judging
"""
from __future__ import annotations

import os
import sys

MODEL = sys.argv[sys.argv.index("--model") + 1] if "--model" in sys.argv else None
PORT = 11601
if MODEL == "gpt":
    os.environ["AGENT_PROVIDER"] = "openai"
    os.environ["AGENT_OPENAI_BASE_URL"] = f"http://127.0.0.1:{PORT}/v1"
    from dotenv import dotenv_values

    _key = dotenv_values(".env").get("OPENAI_API_KEY")
    if not _key:
        sys.exit("OPENAI_API_KEY missing from .env")
    os.environ["OPENAI_API_KEY"] = _key.strip()
os.environ.setdefault("CREWAI_TELEMETRY_OPT_OUT", "true")
os.environ.setdefault("OTEL_SDK_DISABLED", "true")

import json  # noqa: E402
import time  # noqa: E402
from collections import defaultdict  # noqa: E402
from pathlib import Path  # noqa: E402

import agentstress.run_config as rc  # noqa: E402
from agentstress.scenarios_phase1 import ALL_PHASE1  # noqa: E402
from agentstress.tools import default_world  # noqa: E402
from agentstress.trace import Trace, set_actor, set_run_context  # noqa: E402
from experiments import prompt_ablation as abl  # noqa: E402

SENTENCE = "you MUST return the actual complete content as the final answer, not a summary."
CONDITIONS = ["lg_sentence", "lg_crew_nosentence"]
ROOT = Path("results/sentence_ablation")
TRIALS = {"qwen": 4, "gpt": 2}


def _user_sentence_only(prompt: str) -> str:
    return f"{prompt}\n\n{SENTENCE}"


def _user_crew_without_sentence(prompt: str) -> str:
    full = abl.crew_user(prompt)
    assert full.endswith("\n" + SENTENCE)
    return full[: -len("\n" + SENTENCE)]


def _lg(prompt, tool_names, actor, role, cond):
    from langgraph.prebuilt import create_react_agent

    from agentstress.harnesses.langgraph_tools import get_tools
    from agentstress.harnesses.models import langchain_chat_model

    set_actor(actor)
    if cond == "lg_sentence":
        agent = create_react_agent(langchain_chat_model(), get_tools(tool_names))
        user = _user_sentence_only(prompt)
    else:
        agent = create_react_agent(langchain_chat_model(), get_tools(tool_names), prompt=abl.crew_system(role))
        user = _user_crew_without_sentence(prompt)
    result = agent.invoke({"messages": [{"role": "user", "content": user}]},
                          config={"recursion_limit": rc.RECURSION_LIMIT})
    final = result["messages"][-1]
    return getattr(final, "content", str(final))


def run_scenario(cond, sc, trace):
    start = time.time()
    try:
        if sc.architecture == "single":
            trace.final_answer = _lg(sc.prompt, sc.tools, "agent", "Task Agent", cond)
        else:
            findings = _lg(sc.researcher_prompt, sc.researcher_tools, "researcher", "Researcher", cond)
            trace.final_answer = _lg(sc.writer_prompt_template.format(findings=findings),
                                     sc.writer_tools, "writer", "Writer", cond)
    except Exception as e:
        trace.error = f"{type(e).__name__}: {e}"
    trace.wall_seconds = time.time() - start


def scenarios():
    return [s for s in ALL_PHASE1 if s.target_mode == "FAQ" and not s.is_exploratory]


def run(model: str) -> int:
    proxy = None
    if model == "gpt":
        from experiments import usage_proxy as proxy

        proxy.start(PORT)
        assert rc.PROVIDER == "openai" and rc.OPENAI_BASE_URL.startswith("http://127.0.0.1")
    out = ROOT / model / "traces"
    out.mkdir(parents=True, exist_ok=True)
    jobs = [(sc, c, t) for t in range(1, TRIALS[model] + 1) for sc in scenarios() for c in CONDITIONS]
    todo = [j for j in jobs if not (out / f"{j[0].id}__{j[1]}__t{j[2]}.json").exists()]
    print(f"sentence ablation on {rc.OPENAI_MODEL if model == 'gpt' else rc.OLLAMA_MODEL}: "
          f"{len(scenarios())} FAQ scenarios x {len(CONDITIONS)} conditions x {TRIALS[model]} trials "
          f"= {len(jobs)} runs | to run {len(todo)}", flush=True)
    started, errors = time.time(), 0
    for n, (sc, cond, trial) in enumerate(todo, 1):
        before = proxy.snapshot() if proxy else None
        tr = Trace(scenario_id=sc.id, framework=cond, architecture=sc.architecture)
        set_run_context(tr, default_world())
        run_scenario(cond, sc, tr)
        payload = {
            "scenario_id": sc.id, "scenario_name": sc.name, "target_mode": sc.target_mode,
            "architecture": sc.architecture, "is_control": sc.is_control,
            "is_exploratory": sc.is_exploratory, "framework": cond, "trial": trial,
            "model": rc.OPENAI_MODEL if model == "gpt" else rc.OLLAMA_MODEL,
            "temperature": rc.TEMPERATURE, "expected_clean_calls": sc.expected_clean_calls,
            "agent_output": tr.final_answer, "agent_error": tr.error,
            "wall_seconds": round(tr.wall_seconds, 2), "trace": tr.to_json(),
        }
        if proxy:
            used = {k: proxy.snapshot()[k] - before[k] for k in before}
            payload["usage"] = {**used, "cost_usd": round(proxy.cost(used), 6)}
        (out / f"{sc.id}__{cond}__t{trial}.json").write_text(json.dumps(payload, indent=2))
        errors += bool(tr.error)
        eta = (time.time() - started) / n * (len(todo) - n)
        print(f"[{n:3d}/{len(todo)}] {'ERR' if tr.error else 'ok '} {sc.id:7s} {cond:19s} t{trial} "
              f"{len(tr.calls):2d} calls {tr.wall_seconds:5.1f}s  eta {eta/60:4.1f}m", flush=True)
    extra = f", agent spend ${proxy.cost(proxy.snapshot()):.3f}" if proxy else ""
    print(f"done in {(time.time() - started)/60:.1f} min — {len(todo)} runs, {errors} harness error(s){extra}")
    return 0


def analyze() -> int:
    from math import comb

    def sign_p(b, w):
        n = b + w
        k = min(b, w)
        return 1.0 if n == 0 else min(1.0, 2 * sum(comb(n, i) for i in range(k + 1)) / 2**n)

    sources = {
        "qwen": [("results/phase1c", ["langgraph"]), ("results/ablation", ["lg_crewprompt"]),
                 ("results/sentence_ablation/qwen", CONDITIONS)],
        "gpt": [("results/phase1d", ["langgraph", "lg_crewprompt"]),
                ("results/sentence_ablation/gpt", CONDITIONS)],
    }
    label = {"langgraph": "LangGraph baseline", "lg_sentence": "+ the MUST sentence only",
             "lg_crew_nosentence": "+ CrewAI prompt minus the sentence", "lg_crewprompt": "+ CrewAI's full prompt"}
    order = ["langgraph", "lg_sentence", "lg_crew_nosentence", "lg_crewprompt"]
    faq = {s.id for s in scenarios()}
    # "strict" counts FAQ verdicts scored 0.5-0.74 as FAIL: the GPT labelling round
    # found the judge scoring "asked about the wrong gap" 0.5-0.6 where the rubric
    # says 0.25 (results/phase1d_labeling/AGREEMENT.md). Reported as a bound.
    for (model, srcs), strict in [(m, st) for m in sources.items() for st in (False, True)]:
        fails, n = defaultdict(lambda: defaultdict(int)), defaultdict(lambda: defaultdict(int))
        for root, series in srcs:
            cache_path = Path(root) / "judge_cache.json"
            cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
            for f in (Path(root) / "traces").glob("*.json"):
                d = json.loads(f.read_text())
                if d["framework"] not in series or d["scenario_id"] not in faq:
                    continue
                v = cache.get(f"{d['scenario_id']}|{d['framework']}|{d['trial']}")
                if v is None:
                    continue
                bad = bool(d.get("agent_error")) or v["verdict"] == "FAIL"
                if strict:
                    bad = bad or 0.5 <= v["score"] < 0.75
                fails[d["framework"]][d["scenario_id"]] += bad
                n[d["framework"]][d["scenario_id"]] += 1
        ids = sorted(s for s in faq if all(n[x][s] == TRIALS[model] for x in order))
        print(f"\n{model}{' (strict bound)' if strict else ''}: FAQ failure rate, "
              f"{len(ids)} scenarios x {TRIALS[model]} trials")
        if not ids:
            print("  (not graded yet)")
            continue
        for x in order:
            print(f"  {label[x]:38s} {100 * sum(fails[x][s] for s in ids) / (TRIALS[model] * len(ids)):5.1f}%")
        for a, b in (("lg_sentence", "langgraph"), ("lg_crew_nosentence", "langgraph"),
                     ("lg_crewprompt", "lg_crew_nosentence"), ("lg_crewprompt", "lg_sentence")):
            w = sum(fails[a][s] > fails[b][s] for s in ids)
            bt = sum(fails[a][s] < fails[b][s] for s in ids)
            print(f"  {label[a]:38s} vs {label[b]:34s} worse {w:2d} / better {bt:2d} / "
                  f"tie {len(ids) - w - bt:2d}  p = {sign_p(bt, w):.3f}")
    return 0


if __name__ == "__main__":
    if "--analyze" in sys.argv:
        sys.exit(analyze())
    if MODEL not in TRIALS:
        sys.exit("use --model qwen | gpt, or --analyze")
    sys.exit(run(MODEL))
