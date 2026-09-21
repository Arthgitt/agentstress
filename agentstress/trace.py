"""Shared trace recording used by both framework harnesses.

A single source of truth for "what tool was called, with what arguments,
and did it succeed" — this is what the deterministic grader consumes.
"""
from __future__ import annotations

import contextvars
import json
import time
from dataclasses import dataclass, field
from typing import Any


def canonicalize_args(args: dict[str, Any]) -> str:
    """Stable, order-independent string key for an argument dict.

    Strings are stripped of leading/trailing whitespace only — no case
    folding, no semantic normalization. Two calls only count as
    "identical" if an exact-match grader would consider them so.
    """
    normalized = {}
    for k, v in args.items():
        if isinstance(v, str):
            normalized[k] = v.strip()
        else:
            normalized[k] = v
    return json.dumps(normalized, sort_keys=True, default=str)


@dataclass
class ToolCall:
    step_index: int
    tool: str
    args: dict[str, Any]
    args_key: str
    result: str
    is_error: bool
    actor: str  # which node/agent made the call, e.g. "researcher", "writer", "agent"
    timestamp: float


@dataclass
class Trace:
    scenario_id: str
    framework: str
    architecture: str
    calls: list[ToolCall] = field(default_factory=list)
    final_answer: str = ""
    error: str | None = None
    wall_seconds: float = 0.0

    def record(self, tool: str, args: dict[str, Any], result: str, is_error: bool, actor: str) -> None:
        self.calls.append(
            ToolCall(
                step_index=len(self.calls),
                tool=tool,
                args=args,
                args_key=canonicalize_args(args),
                result=str(result)[:500],
                is_error=is_error,
                actor=actor,
                timestamp=time.time(),
            )
        )

    def to_json(self) -> dict:
        return {
            "scenario_id": self.scenario_id,
            "framework": self.framework,
            "architecture": self.architecture,
            "final_answer": self.final_answer,
            "error": self.error,
            "wall_seconds": round(self.wall_seconds, 2),
            "calls": [
                {
                    "step_index": c.step_index,
                    "tool": c.tool,
                    "args": c.args,
                    "args_key": c.args_key,
                    "result": c.result,
                    "is_error": c.is_error,
                    "actor": c.actor,
                }
                for c in self.calls
            ],
        }


# Active trace + world state for the run currently in flight. Tools read
# these via contextvars so the same tool implementation works unmodified
# under both frameworks. The pilot runner executes one scenario at a time,
# synchronously, so there is no cross-run interleaving.
CURRENT_TRACE: contextvars.ContextVar[Trace | None] = contextvars.ContextVar("CURRENT_TRACE", default=None)
CURRENT_WORLD: contextvars.ContextVar[dict | None] = contextvars.ContextVar("CURRENT_WORLD", default=None)
CURRENT_ACTOR: contextvars.ContextVar[str] = contextvars.ContextVar("CURRENT_ACTOR", default="agent")


def get_trace() -> Trace:
    t = CURRENT_TRACE.get()
    if t is None:
        raise RuntimeError("No active Trace — call set_run_context() before invoking an agent.")
    return t


def get_world() -> dict:
    w = CURRENT_WORLD.get()
    if w is None:
        raise RuntimeError("No active world state — call set_run_context() before invoking an agent.")
    return w


def set_run_context(trace: Trace, world: dict) -> None:
    CURRENT_TRACE.set(trace)
    CURRENT_WORLD.set(world)
    CURRENT_ACTOR.set("agent")


def set_actor(name: str) -> None:
    CURRENT_ACTOR.set(name)


def get_actor() -> str:
    return CURRENT_ACTOR.get()
