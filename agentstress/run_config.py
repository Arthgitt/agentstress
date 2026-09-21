"""Single source of truth for the model configuration every harness uses.

The Phase 1 claim is that measured differences come from framework
orchestration. That only holds if all three frameworks drive identical weights
with identical decoding settings, so those settings live here rather than being
repeated (and drifting) in three harness files.

TEMPERATURE — why it is not 0
-----------------------------
Phase 0 ran at temperature 0. Measured on 2026-09-12, that is fully
deterministic for this model: three runs of INV-01 produced byte-identical tool
sequences. Four trials at temperature 0 would therefore produce four identical
traces, and every scenario's failure rate would come out as exactly 0.0 or 1.0
— which is single-sample data wearing a rate's clothing, and defeats the reason
repeated trials were added to the plan.

At 0.3, three runs produced three distinct traces while the call count stayed
stable at 2 — genuine sampling variation without tipping the model into noise.
0.7 also varied but deviates further from the pilot's greedy decoding, so 0.3 is
the conservative choice that keeps Phase 1c comparable to Phase 0.

Phase 0 traces were produced at temperature 0 and are not reproducible under
this setting. That is expected and is recorded in the Phase 1c report.
"""
from __future__ import annotations

import os

# Which backend drives the agents. "ollama" (default) is the Phase 1 setup.
# "openai" is the Phase 1d frontier cross-check: all three frameworks move to the
# hosted model together, never one alone. Set AGENT_PROVIDER before importing
# any harness; experiments/phase1d.py does this.
PROVIDER = os.environ.get("AGENT_PROVIDER", "ollama")
OPENAI_MODEL = "gpt-5.4-mini"
OPENAI_BASE_URL = os.environ.get("AGENT_OPENAI_BASE_URL", "https://api.openai.com/v1")

OLLAMA_MODEL = "qwen2.5:7b-instruct"
OLLAMA_BASE_URL = "http://localhost:11434"
OLLAMA_OPENAI_BASE_URL = "http://localhost:11434/v1"  # OpenAI-compatible endpoint

TEMPERATURE = 0.3

# Upper bound on agent loop length. Generous relative to the most demanding
# scenario (a clean run never needs more than ~5 calls), so a hit indicates
# looping rather than a task that legitimately needed the headroom.
MAX_ITERATIONS = 15
RECURSION_LIMIT = 30

TRIALS = 4
