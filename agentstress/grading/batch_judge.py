"""Judge grading through the Message Batches API — 50% of standard price.

Same instrument as the synchronous judge: requests are built by
claude_judge.judge_request_params and parsed by claude_judge.verdict_from_content,
so model, prompt and settings are identical and the Phase 1b calibration
carries over. Only transport and price differ. Batches are asynchronous: most
finish within an hour, and the API expires anything unfinished after 24 hours.

Verdicts land in the same cache the synchronous path uses
(results/phase1c/judge_cache.json), so grade_phase1c.py reports them unchanged.

    python -m grading.batch_judge submit --dry-run   # count + cost estimate, no spend
    python -m grading.batch_judge submit             # send every ungraded trace
    python -m grading.batch_judge status             # progress of submitted batches
    python -m grading.batch_judge collect            # pull finished results into the cache

Never pays twice: a trace already in the cache, or already inside a submitted
batch that has not been collected, is never resubmitted. Batch ids are written
to disk before anything else happens, so a crash after submission loses nothing.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from agentstress.scenarios_phase1 import BY_ID_PHASE1
from agentstress.grading.claude_judge import (
    _get_client,
    agent_prompt_shown_to_judge,
    judge_request_params,
    verdict_from_content,
)

TRACES = Path("results/phase1c/traces")
CACHE = Path("results/phase1c/judge_cache.json")
STATE = Path("results/phase1c/batch_state.json")

# --set picks which run to grade. The prompt ablation (experiments/) writes the
# same trace payload into its own directory and keeps its own cache and batch
# state, so its judging never mixes with the main run's.
SETS = {
    "phase1c": ("results/phase1c", "judge_cache.json", "batch_state.json"),
    "ablation": ("results/ablation", "judge_cache.json", "batch_state.json"),
    "phase1d": ("results/phase1d", "judge_cache.json", "batch_state.json"),
    "sentence_qwen": ("results/sentence_ablation/qwen", "judge_cache.json", "batch_state.json"),
    "sentence_gpt": ("results/sentence_ablation/gpt", "judge_cache.json", "batch_state.json"),
}


def use_set(name: str) -> None:
    global TRACES, CACHE, STATE
    root, cache, state = SETS[name]
    TRACES, CACHE, STATE = Path(root) / "traces", Path(root) / cache, Path(root) / state

# Batch prices for claude-opus-5, $ per million tokens (platform docs, 2026-09-13).
BATCH_IN, BATCH_OUT = 2.50, 12.50
# Measured Phase 1c average per judgement, used only for the dry-run estimate.
EST_IN, EST_OUT = 1163, 293


def _load(path: Path, default):
    return json.loads(path.read_text()) if path.exists() else default


def _cache_key(sid: str, fw: str, trial: int) -> str:
    return f"{sid}|{fw}|{trial}"


def _custom_id(sid: str, fw: str, trial: int) -> str:
    # Batch custom_id allows [A-Za-z0-9_-]; the cache key's "|" does not qualify.
    return f"{sid}__{fw}__t{trial}"


def _from_custom_id(cid: str) -> str:
    sid, fw, t = cid.split("__")
    return _cache_key(sid, fw, int(t[1:]))


def _in_flight(state: dict) -> set[str]:
    return {cid for b in state["batches"] if not b.get("collected") for cid in b["custom_ids"]}


def pending_requests() -> list[dict]:
    cache = _load(CACHE, {})
    state = _load(STATE, {"batches": []})
    busy = _in_flight(state)
    reqs = []
    for path in sorted(TRACES.glob("*.json")):
        d = json.loads(path.read_text())
        sc = BY_ID_PHASE1[d["scenario_id"]]
        if sc.retired or sc.target_mode == "SR" or d.get("agent_error"):
            continue
        sid, fw, trial = d["scenario_id"], d["framework"], d["trial"]
        cached = cache.get(_cache_key(sid, fw, trial))
        if cached and cached["verdict"] != "ERROR":
            continue
        cid = _custom_id(sid, fw, trial)
        if cid in busy:
            continue
        reqs.append({
            "custom_id": cid,
            "params": judge_request_params(
                sc.target_mode,
                agent_prompt_shown_to_judge(sc),
                d.get("agent_output") or "",
                d["trace"]["calls"],
                sc.structural_reason,
                sc.expected_clean_calls,
            ),
        })
    return reqs


def submit(dry_run: bool) -> int:
    reqs = pending_requests()
    est = len(reqs) * (EST_IN * BATCH_IN + EST_OUT * BATCH_OUT) / 1e6
    print(f"ungraded judge-mode traces: {len(reqs)}   estimated batch cost: ${est:.2f}")
    if not reqs:
        return 0
    if dry_run:
        print("dry run — nothing submitted")
        return 0

    batch = _get_client().messages.batches.create(requests=reqs)
    state = _load(STATE, {"batches": []})
    state["batches"].append({
        "id": batch.id,
        "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "custom_ids": [r["custom_id"] for r in reqs],
        "collected": False,
    })
    STATE.write_text(json.dumps(state, indent=2))
    print(f"submitted batch {batch.id} with {len(reqs)} requests (status: {batch.processing_status})")
    return 0


def status() -> int:
    state = _load(STATE, {"batches": []})
    if not state["batches"]:
        print("no batches submitted")
        return 0
    client = _get_client()
    for b in state["batches"]:
        if b.get("collected"):
            print(f"{b['id']}  collected   ({len(b['custom_ids'])} requests)")
            continue
        r = client.messages.batches.retrieve(b["id"])
        c = r.request_counts
        print(f"{b['id']}  {r.processing_status:11s} processing={c.processing} succeeded={c.succeeded} "
              f"errored={c.errored} canceled={c.canceled} expired={c.expired}")
    return 0


def collect() -> int:
    state = _load(STATE, {"batches": []})
    cache = _load(CACHE, {})
    client = _get_client()
    tot_in = tot_out = n_ok = n_bad = 0
    for b in state["batches"]:
        if b.get("collected"):
            continue
        r = client.messages.batches.retrieve(b["id"])
        if r.processing_status != "ended":
            print(f"{b['id']} still {r.processing_status} — try again later")
            continue
        for entry in client.messages.batches.results(b["id"]):
            key = _from_custom_id(entry.custom_id)
            if entry.result.type != "succeeded":
                n_bad += 1  # left uncached; the next submit picks it up again
                continue
            msg = entry.result.message
            tot_in += msg.usage.input_tokens
            tot_out += msg.usage.output_tokens
            v = verdict_from_content(msg.content)
            if v["verdict"] == "ERROR":
                n_bad += 1  # unparseable; left uncached for resubmission
                continue
            cache[key] = v
            n_ok += 1
        b["collected"] = True
        b["usage"] = {"input_tokens": tot_in, "output_tokens": tot_out}
        CACHE.write_text(json.dumps(cache, indent=2))
        STATE.write_text(json.dumps(state, indent=2))

    cost = tot_in * BATCH_IN / 1e6 + tot_out * BATCH_OUT / 1e6
    print(f"collected {n_ok} verdicts, {n_bad} to resubmit")
    if tot_in:
        print(f"batch tokens: {tot_in:,} in / {tot_out:,} out  ->  ${cost:.2f} at batch price")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["submit", "status", "collect"])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--set", choices=sorted(SETS), default="phase1c",
                    help="which run to grade (default: the main 100-scenario run)")
    a = ap.parse_args()
    use_set(a.set)
    if a.command == "submit":
        return submit(a.dry_run)
    if a.command == "status":
        return status()
    return collect()


if __name__ == "__main__":
    sys.exit(main())
