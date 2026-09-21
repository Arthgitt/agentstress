#!/usr/bin/env python3
"""Build every figure and number the paper cites, straight from the results.

Nothing in the paper is retyped by hand: this writes paper/figures/*.pdf and
paper/numbers.tex (LaTeX macros), so a re-run after new data updates the draft.

Run:  python paper/make_figures.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # run from anywhere

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from agentstress.scenarios_phase1 import ALL_PHASE1, BY_ID_PHASE1  # noqa: E402

ROOT = Path(__file__).resolve().parent
FIG = ROOT / "figures"
FIG.mkdir(parents=True, exist_ok=True)

MODES = ["SR", "RAM", "UT", "FAQ", "INV"]
MODE_LABEL = {"SR": "Step\nrepetition", "RAM": "Reasoning-action\nmismatch",
              "UT": "Unaware of\ntermination", "FAQ": "Fail to ask for\nclarification",
              "INV": "Incorrect / no\nverification"}
FW = ["langgraph", "crewai", "openai_agents"]
FW_LABEL = {"langgraph": "LangGraph", "crewai": "CrewAI", "openai_agents": "OpenAI Agents"}
COLOR = {"langgraph": "#4C72B0", "crewai": "#C44E52", "openai_agents": "#55A868",
         "other": "#8172B2", "grey": "#999999"}

plt.rcParams.update({"font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
                     "figure.dpi": 150, "savefig.bbox": "tight", "axes.grid": True,
                     "grid.alpha": 0.25, "grid.linestyle": ":", "axes.axisbelow": True})


def save(fig, name):
    for ext in ("pdf", "png"):
        fig.savefig(FIG / f"{name}.{ext}")
    plt.close(fig)
    print("wrote", FIG / f"{name}.pdf")


def graded_rows():
    return json.loads(Path("results/phase1c/graded.json").read_text())


def counts(root: str, series: list[str], modes=("SR", "UT", "FAQ"), strict=False):
    """scenario -> series -> failures, using each run set's own judge cache."""
    from agentstress.grader import grade_trace

    fails, n = defaultdict(lambda: defaultdict(int)), defaultdict(lambda: defaultdict(int))
    cache_path = Path(root) / "judge_cache.json"
    cache = json.loads(cache_path.read_text()) if cache_path.exists() else {}
    for f in (Path(root) / "traces").glob("*.json"):
        d = json.loads(f.read_text())
        sc = BY_ID_PHASE1[d["scenario_id"]]
        if d["framework"] not in series or sc.target_mode not in modes or sc.retired or sc.is_exploratory:
            continue
        if sc.target_mode == "SR":
            bad = bool(d.get("agent_error")) or grade_trace(d["trace"], sc.repeated_mutations_expected)["extended_verdict"] == "FAIL"
        else:
            v = cache.get(f"{sc.id}|{d['framework']}|{d['trial']}")
            if v is None:
                continue
            bad = bool(d.get("agent_error")) or v["verdict"] == "FAIL"
            if strict and sc.target_mode == "FAQ":
                bad = bad or 0.5 <= v["score"] < 0.75
        fails[sc.id][d["framework"]] += bad
        n[sc.id][d["framework"]] += 1
    return fails, n


def rate(fails, n, ids, series):
    den = sum(n[s][series] for s in ids)
    return 100 * sum(fails[s][series] for s in ids) / den if den else float("nan")


# --- Figure 1: failure rate by mode and framework (Phase 1, 100 scenarios) ---
def fig_modes(macros):
    rows = graded_rows()
    tally = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for r in rows:
        if r["is_exploratory"]:
            continue
        t = tally[r["target_mode"]][r["framework"]]
        t[0] += r["outcome"] in ("FAIL", "ERROR")
        t[1] += 1
    fig, ax = plt.subplots(figsize=(6.6, 2.9))
    width = 0.26
    for i, fw in enumerate(FW):
        vals = [100 * tally[m][fw][0] / tally[m][fw][1] for m in MODES]
        ax.bar([x + (i - 1) * width for x in range(len(MODES))], vals, width,
               label=FW_LABEL[fw], color=COLOR[fw])
        for m, v in zip(MODES, vals):
            macros[f"rate{m}{fw[:2].upper()}"] = f"{v:.1f}"
    ax.set_xticks(range(len(MODES)))
    ax.set_xticklabels([MODE_LABEL[m] for m in MODES])
    ax.set_ylabel("failure rate (\\%)" if False else "failure rate (%)")
    ax.set_ylim(0, 85)
    ax.legend(frameon=False, ncol=3, loc="upper center", bbox_to_anchor=(0.5, 1.18))
    save(fig, "fig1_modes")


# --- Figure 2: prompt swap, qwen and GPT side by side ---
def fig_swap(macros):
    series = ["langgraph", "openai_agents", "crewai", "lg_crewprompt", "oai_crewprompt", "crew_neutral"]
    labels = ["LangGraph", "OpenAI Agents", "CrewAI", "LangGraph + CrewAI prompt",
              "OpenAI Agents + CrewAI prompt", "CrewAI + neutral wording"]
    cols = [COLOR["langgraph"], COLOR["openai_agents"], COLOR["crewai"],
            COLOR["langgraph"], COLOR["openai_agents"], COLOR["crewai"]]
    hatch = ["", "", "", "//", "//", ".."]

    qf, qn = counts("results/phase1c", series[:3])
    af, an = counts("results/ablation", series[3:])
    for s in qf:
        qf[s].update(af[s])
        qn[s].update(an[s])
    gf, gn = counts("results/phase1d", series)

    fig, axes = plt.subplots(1, 2, figsize=(6.9, 3.4), sharey=True)
    for ax, (fails, n, title, tag) in zip(axes, [(qf, qn, "qwen2.5 7B (local)", "Q"),
                                                 (gf, gn, "gpt-5.4-mini", "G")]):
        ids = sorted(s for s in fails if all(n[s][x] for x in series))
        vals = [rate(fails, n, ids, s) for s in series]
        bars = ax.bar(range(len(series)), vals, color=cols, hatch=hatch, edgecolor="white")
        for b, v in zip(bars, vals):
            ax.text(b.get_x() + b.get_width() / 2, v + 1, f"{v:.0f}", ha="center", fontsize=8)
        ax.set_xticks(range(len(series)))
        ax.set_xticklabels(labels, fontsize=7, rotation=32, ha="right",
                           rotation_mode="anchor")
        ax.set_title(title, fontsize=9)
        ax.set_ylim(0, 58)
        for s, v in zip(series, vals):
            macros[f"swap{tag}{s.replace('_', '')}"] = f"{v:.1f}"
    axes[0].set_ylabel("failure rate, SR+UT+FAQ (%)")
    save(fig, "fig2_promptswap")


# --- Figure 3: the sentence ablation, FAQ only ---
def fig_sentence(macros):
    order = ["langgraph", "lg_sentence", "lg_crew_nosentence", "lg_crewprompt"]
    labels = ["LangGraph\nbaseline", "+ the MUST\nsentence only",
              "+ CrewAI prompt\nminus the sentence", "+ CrewAI's\nfull prompt"]
    srcs = {"Q": [("results/phase1c", ["langgraph"]), ("results/ablation", ["lg_crewprompt"]),
                  ("results/sentence_ablation/qwen", ["lg_sentence", "lg_crew_nosentence"])],
            "G": [("results/phase1d", ["langgraph", "lg_crewprompt"]),
                  ("results/sentence_ablation/gpt", ["lg_sentence", "lg_crew_nosentence"])]}
    fig, ax = plt.subplots(figsize=(6.0, 2.9))
    width = 0.38
    for i, (tag, title) in enumerate((("Q", "qwen2.5 7B"), ("G", "gpt-5.4-mini"))):
        fails, n = defaultdict(lambda: defaultdict(int)), defaultdict(lambda: defaultdict(int))
        for root, series in srcs[tag]:
            f2, n2 = counts(root, series, modes=("FAQ",))
            for s in f2:
                fails[s].update(f2[s])
                n[s].update(n2[s])
        ids = sorted(s for s in fails if all(n[s][x] for x in order))
        vals = [rate(fails, n, ids, s) for s in order]
        ax.bar([x + (i - 0.5) * width for x in range(len(order))], vals, width,
               label=title, color=[COLOR["grey"], COLOR["other"]][i])
        for s, v in zip(order, vals):
            macros[f"sent{tag}{s.replace('_', '')}"] = f"{v:.1f}"
    ax.set_xticks(range(len(order)))
    ax.set_xticklabels(labels, fontsize=7.5)
    ax.set_ylabel("FAQ failure rate (%)")
    ax.set_ylim(0, 88)
    ax.legend(frameon=False, ncol=2)
    save(fig, "fig3_sentence")


def other_macros(macros):
    rows = graded_rows()
    macros["nRunsPhaseOne"] = f"{len(rows):,}"
    core = {r["scenario_id"] for r in rows if not r["is_exploratory"]}
    macros["nScenarios"] = str(len({s.id for s in ALL_PHASE1}))
    macros["nCore"] = str(len(core))
    corr = defaultdict(lambda: [0, 0])
    for r in rows:
        if r["correct"] is None:
            continue
        corr[r["framework"]][0] += bool(r["correct"])
        corr[r["framework"]][1] += 1
    for fw in FW:
        macros[f"correct{fw[:2].upper()}"] = f"{100 * corr[fw][0] / corr[fw][1]:.1f}"
    n_abl = len(list(Path("results/ablation/traces").glob("*.json")))
    n_1d = len(list(Path("results/phase1d/traces").glob("*.json")))
    n_sent = sum(len(list(Path(f"results/sentence_ablation/{m}/traces").glob("*.json"))) for m in ("qwen", "gpt"))
    macros["nRunsAblation"] = str(n_abl)
    macros["nRunsPhaseD"] = str(n_1d)
    macros["nRunsSentence"] = str(n_sent)
    macros["nRunsTotal"] = f"{len(rows) + n_abl + n_1d + n_sent:,}"


def main():
    macros: dict[str, str] = {}
    fig_modes(macros)
    fig_swap(macros)
    fig_sentence(macros)
    other_macros(macros)
    lines = ["% Generated by paper/make_figures.py — do not edit by hand.\n"]
    for k, v in sorted(macros.items()):
        lines.append(f"\\newcommand{{\\{k}}}{{{v}}}\n")
    (ROOT / "numbers.tex").write_text("".join(lines))
    print(f"wrote {ROOT / 'numbers.tex'} with {len(macros)} macros")


if __name__ == "__main__":
    main()
