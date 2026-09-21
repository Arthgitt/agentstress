"""Command line for agentstress.

    agentstress list                       what the suite provokes
    agentstress capture  --framework crewai --scenario FAQ-12
    agentstress run      --framework langgraph --model ollama:qwen2.5:7b-instruct
    agentstress grade    --runs runs/            (step repetition: free)
    agentstress grade    --runs runs/ --judge    (all modes: billed)
    agentstress report   --runs runs/

`capture` is the one to try first: it prints the prompt your framework actually
sends the model, which is what the study found drives failure rates.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import agentstress.run_config as rc
from agentstress.scenarios_phase1 import ALL_PHASE1, BY_ID_PHASE1

FRAMEWORKS = {
    "langgraph": "agentstress.harnesses.langgraph_runner",
    "crewai": "agentstress.harnesses.crewai_runner",
    "openai_agents": "agentstress.harnesses.openai_runner",
}
MODE_NAMES = {
    "SR": "step repetition", "RAM": "reasoning-action mismatch",
    "UT": "unaware of termination", "FAQ": "fail to ask for clarification",
    "INV": "incorrect / no verification",
}


def _select(args) -> list:
    picked = [s for s in ALL_PHASE1 if not s.retired]
    if getattr(args, "mode", None):
        picked = [s for s in picked if s.target_mode in args.mode]
    if getattr(args, "scenario", None):
        want = set(args.scenario)
        missing = want - {s.id for s in picked}
        if missing:
            sys.exit(f"unknown scenario id(s): {', '.join(sorted(missing))}")
        picked = [s for s in picked if s.id in want]
    if not picked:
        sys.exit("no scenarios selected")
    return picked


def _apply_model(spec: str) -> str:
    """'ollama:qwen2.5:7b-instruct' or 'openai:gpt-5.4-mini'."""
    provider, _, name = spec.partition(":")
    if provider not in ("ollama", "openai") or not name:
        sys.exit("--model must be ollama:<name> or openai:<name>")
    rc.PROVIDER = provider
    if provider == "ollama":
        rc.OLLAMA_MODEL = name
    else:
        rc.OPENAI_MODEL = name
        import os

        if not os.environ.get("OPENAI_API_KEY"):
            from dotenv import dotenv_values

            key = dotenv_values(".env").get("OPENAI_API_KEY")
            if not key:
                sys.exit("set OPENAI_API_KEY (environment or .env) to use an openai model")
            os.environ["OPENAI_API_KEY"] = key.strip()
    return name


def cmd_list(args) -> int:
    rows = _select(args)
    by_mode: dict[str, list] = {}
    for s in rows:
        by_mode.setdefault(s.target_mode, []).append(s)
    for mode, items in by_mode.items():
        print(f"\n{mode} — {MODE_NAMES[mode]} ({len(items)} scenarios)")
        for s in items:
            tags = []
            if s.is_control:
                tags.append("control")
            if s.architecture == "handoff":
                tags.append("handoff")
            if s.is_exploratory:
                tags.append("exploratory")
            tag = f"  [{', '.join(tags)}]" if tags else ""
            prompt = (s.prompt or s.researcher_prompt or "").strip().replace("\n", " ")
            print(f"  {s.id:8s} {s.name:34s}{tag}")
            if args.verbose:
                print(f"           {prompt[:100]}")
    print(f"\n{len(rows)} scenarios. Controls are scenarios where the failure is not "
          f"available; a grader that flags them is over-flagging.")
    return 0


def cmd_capture(args) -> int:
    """Print the requests a framework actually sends for one scenario."""
    from agentstress import proxy as cp

    sc = BY_ID_PHASE1[args.scenario[0]] if args.scenario else ALL_PHASE1[0]
    _apply_model(args.model)
    if rc.PROVIDER != "ollama":
        sys.exit("capture currently proxies the local Ollama endpoint; use --model ollama:<name>")
    upstream = rc.OLLAMA_BASE_URL
    srv = cp.start()
    cp.upstream = lambda: upstream
    rc.OLLAMA_BASE_URL = f"http://127.0.0.1:{cp.PORT}"
    rc.OLLAMA_OPENAI_BASE_URL = f"http://127.0.0.1:{cp.PORT}/v1"
    cp.CURRENT["fw"] = args.framework

    import importlib

    from agentstress.tools import default_world
    from agentstress.trace import Trace, set_run_context

    tr = Trace(scenario_id=sc.id, framework=args.framework, architecture=sc.architecture)
    set_run_context(tr, default_world())
    importlib.import_module(FRAMEWORKS[args.framework]).run_scenario(sc, tr)
    srv.shutdown()

    if not cp.LOG:
        print("no requests captured")
        return 1
    body = cp.LOG[0]["body"]
    print(f"=== {args.framework} · {sc.id} · first request to the model ===")
    for m in body.get("messages", [{"role": "user", "content": sc.prompt}]):
        print(f"\n--- {m.get('role')} ---\n{m.get('content')}")
    print(f"\n--- tools offered: {[t.get('function', {}).get('name') for t in body.get('tools', [])]}")
    print(f"--- your task text was: {(sc.prompt or sc.researcher_prompt or '').strip()!r}")
    print("\nEverything above that you did not write is scaffolding the framework added.")
    return 0


def cmd_run(args) -> int:
    import importlib

    from agentstress.tools import default_world
    from agentstress.trace import Trace, set_run_context

    model = _apply_model(args.model)
    rc.TEMPERATURE = args.temperature
    scenarios = _select(args)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    runner = importlib.import_module(FRAMEWORKS[args.framework]).run_scenario

    jobs = [(s, t) for t in range(1, args.trials + 1) for s in scenarios]
    todo = [j for j in jobs if not (out / f"{j[0].id}__{args.framework}__t{j[1]}.json").exists()]
    print(f"{len(scenarios)} scenarios x {args.trials} trials on {args.framework} / {model} "
          f"= {len(jobs)} runs | to run {len(todo)} | out: {out}", flush=True)
    started, errors = time.time(), 0
    for n, (sc, trial) in enumerate(todo, 1):
        tr = Trace(scenario_id=sc.id, framework=args.framework, architecture=sc.architecture)
        set_run_context(tr, default_world())
        try:
            runner(sc, tr)
        except Exception as e:
            tr.error = f"{type(e).__name__}: {e}"
        (out / f"{sc.id}__{args.framework}__t{trial}.json").write_text(json.dumps({
            "scenario_id": sc.id, "scenario_name": sc.name, "target_mode": sc.target_mode,
            "architecture": sc.architecture, "is_control": sc.is_control,
            "is_exploratory": sc.is_exploratory, "framework": args.framework, "trial": trial,
            "model": model, "temperature": rc.TEMPERATURE,
            "expected_clean_calls": sc.expected_clean_calls,
            "agent_output": tr.final_answer, "agent_error": tr.error,
            "wall_seconds": round(tr.wall_seconds, 2), "trace": tr.to_json(),
        }, indent=2))
        errors += bool(tr.error)
        eta = (time.time() - started) / n * (len(todo) - n)
        print(f"[{n:4d}/{len(todo)}] {'ERR' if tr.error else 'ok '} {sc.id:8s} t{trial} "
              f"{len(tr.calls):2d} calls {tr.wall_seconds:6.1f}s  eta {eta/60:5.1f}m", flush=True)
    print(f"done — {len(todo)} runs, {errors} harness error(s). Next: agentstress grade --runs {out}")
    return 0


def _grade_dir(runs: Path, use_judge: bool):
    """-> rows [{scenario_id, framework, trial, mode, outcome, detail}]"""
    from agentstress.correctness import check
    from agentstress.grader import grade_trace

    judge = None
    if use_judge:
        from agentstress.grading.claude_judge import judge_scenario

        judge = judge_scenario
    rows = []
    for f in sorted(runs.glob("*.json")):
        d = json.loads(f.read_text())
        sc = BY_ID_PHASE1.get(d["scenario_id"])
        if sc is None:
            continue
        if d.get("agent_error"):
            outcome, detail = "ERROR", d["agent_error"][:80]
        elif sc.target_mode == "SR":
            g = grade_trace(d["trace"], sc.repeated_mutations_expected)
            outcome = "FAIL" if g["extended_verdict"] == "FAIL" else "PASS"
            detail = g["detail"] if isinstance(g.get("detail"), str) else ""
        elif judge is None:
            outcome, detail = "UNGRADED", "needs --judge"
        else:
            from agentstress.grading.claude_judge import agent_prompt_shown_to_judge

            v = judge(sc.id, sc.target_mode, d["framework"], d.get("agent_output") or "",
                      agent_prompt_shown_to_judge(sc),
                      structural_reason=sc.structural_reason,
                      tool_calls=d["trace"]["calls"],
                      expected_clean_calls=sc.expected_clean_calls)
            outcome, detail = v["verdict"], f"score {v['score']}"
        corr = check(sc.id, d["trace"], d.get("agent_output") or "")
        rows.append({"scenario_id": sc.id, "framework": d["framework"], "trial": d["trial"],
                     "mode": sc.target_mode, "outcome": outcome, "detail": detail,
                     "correct": None if corr is None else corr["correct"]})
    return rows


def cmd_grade(args) -> int:
    runs = Path(args.runs)
    if not runs.exists():
        sys.exit(f"no such directory: {runs}")
    modes = [BY_ID_PHASE1[d["scenario_id"]].target_mode
             for d in (json.loads(f.read_text()) for f in runs.glob("*.json"))
             if d["scenario_id"] in BY_ID_PHASE1]
    n_judge = sum(m != "SR" for m in modes)
    if args.judge:
        print(f"judging {n_judge} runs with {rc_judge_model()} — this is billed", flush=True)
    elif n_judge:
        print(f"note: {n_judge} runs need the LLM judge (--judge); grading step repetition only")
    rows = _grade_dir(runs, args.judge)
    (runs / "graded.json").write_text(json.dumps(rows, indent=2))
    print(f"wrote {runs / 'graded.json'} ({len(rows)} rows)")
    return cmd_report(args)


def rc_judge_model() -> str:
    from agentstress.grading.claude_judge import JUDGE_MODEL

    return JUDGE_MODEL


def cmd_report(args) -> int:
    runs = Path(args.runs)
    path = runs / "graded.json"
    if not path.exists():
        sys.exit(f"no graded.json in {runs} — run: agentstress grade --runs {runs}")
    rows = json.loads(path.read_text())
    by: dict[tuple, list] = {}
    for r in rows:
        by.setdefault((r["mode"], r["framework"]), []).append(r)
    print(f"\n{'mode':6s} {'framework':16s} {'runs':>5} {'failure rate':>13} {'correct':>9}")
    for (mode, fw), items in sorted(by.items()):
        bad = sum(i["outcome"] in ("FAIL", "ERROR") for i in items)
        graded = [i for i in items if i["outcome"] != "UNGRADED"]
        checked = [i for i in items if i["correct"] is not None]
        rate = f"{100 * bad / len(graded):.0f}%" if graded else "ungraded"
        corr = f"{100 * sum(bool(i['correct']) for i in checked) / len(checked):.0f}%" if checked else "-"
        print(f"{mode:6s} {fw:16s} {len(items):5d} {rate:>13} {corr:>9}")
    worst = sorted({r["scenario_id"] for r in rows if r["outcome"] in ("FAIL", "ERROR")})
    if worst:
        print(f"\nscenarios with at least one failure ({len(worst)}): {', '.join(worst[:24])}"
              + (" ..." if len(worst) > 24 else ""))
    print("\nFailure rate and correctness are separate axes: a run can avoid the failure "
          "mode and still answer wrongly.")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="agentstress", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add_select(p):
        p.add_argument("--mode", nargs="+", choices=list(MODE_NAMES), help="limit to these failure modes")
        p.add_argument("--scenario", nargs="+", help="scenario ids, e.g. FAQ-12 SR-02")

    p = sub.add_parser("list", help="list scenarios")
    add_select(p)
    p.add_argument("--verbose", action="store_true", help="show the task text")
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("capture", help="print what your framework sends the model")
    p.add_argument("--framework", choices=list(FRAMEWORKS), required=True)
    p.add_argument("--scenario", nargs=1, required=True)
    p.add_argument("--model", default="ollama:qwen2.5:7b-instruct")
    p.set_defaults(func=cmd_capture)

    p = sub.add_parser("run", help="run scenarios against a framework")
    p.add_argument("--framework", choices=list(FRAMEWORKS), required=True)
    p.add_argument("--model", default="ollama:qwen2.5:7b-instruct",
                   help="ollama:<name> or openai:<name>")
    p.add_argument("--trials", type=int, default=2)
    p.add_argument("--temperature", type=float, default=rc.TEMPERATURE)
    p.add_argument("--out", default="runs")
    add_select(p)
    p.set_defaults(func=cmd_run)

    p = sub.add_parser("grade", help="grade a runs directory")
    p.add_argument("--runs", default="runs")
    p.add_argument("--judge", action="store_true",
                   help="use the LLM judge for RAM/UT/FAQ/INV (billed; needs ANTHROPIC_API_KEY)")
    p.set_defaults(func=cmd_grade)

    p = sub.add_parser("report", help="summarise graded runs")
    p.add_argument("--runs", default="runs")
    p.set_defaults(func=cmd_report)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
