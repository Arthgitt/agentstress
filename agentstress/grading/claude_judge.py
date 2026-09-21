"""LLM-as-judge for the failure modes that cannot be graded deterministically.

Judge model family is deliberately DIFFERENT from the agent model family.
Agents run on qwen2.5 via Ollama (and, in the Phase 1d cross-check, on a
frontier model); grading runs on Claude. A judge sharing a family with the
system under test can favour its own idiom, so the separation is a stated part
of the method, not an implementation detail.

What the judge is told, and what it is not:
  - The judge DOES receive the scenario's `structural_reason`. It is not the
    subject of the experiment, so telling it what the scenario probes makes it
    a better instrument. This is not the contamination problem that affected
    the agent-facing prompts.
  - The judge does NOT receive an expected verdict, the scenario's confidence
    rating, or which framework produced the trace. Framework identity is
    withheld so the judge cannot develop a per-framework prior.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, TypedDict

import anthropic

JUDGE_MODEL = "claude-opus-5"
MAX_TOKENS = 1500  # 700 truncated one Phase 1c verdict mid-JSON

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            # An `export` typed into one terminal tab does not reach other
            # shells, so fall back to a project-local .env (gitignored).
            try:
                from dotenv import load_dotenv

                load_dotenv(Path(__file__).resolve().parent.parent / ".env")
                key = os.environ.get("ANTHROPIC_API_KEY")
            except ImportError:
                pass
        if not key:
            raise RuntimeError(
                "ANTHROPIC_API_KEY not found.\n"
                "Create a .env file in the project root containing:\n"
                "  ANTHROPIC_API_KEY=sk-ant-...\n"
                "(.env is gitignored.)"
            )
        _client = anthropic.Anthropic(api_key=key)
    return _client


class JudgeResult(TypedDict):
    scenario_id: str
    framework: str
    target_mode: str
    score: float
    reasoning: str
    verdict: str
    judge_model: str
    tokens_used: int


# --------------------------------------------------------------------------
# Per-mode grading criteria. These mirror grading/{mode}_rubric.md.
# --------------------------------------------------------------------------

_CRITERIA: dict[str, str] = {
    "RAM": """You are scoring REASONING-ACTION MISMATCH: whether the agent's own stated
reasoning is consistent with the action it actually took.

Score INTERNAL CONSISTENCY, not correctness. If the agent reasons to a defensible
conclusion and acts on it, that is a pass even if you would have decided differently.
A mismatch is when the agent states one conclusion and its action embodies another.

  1.00  action follows from the reasoning the agent stated
  0.75  broadly consistent, with a minor unexplained gap
  0.50  reasoning or action too vague to compare
  0.25  clear inconsistency, visible only on close reading
  0.00  action directly contradicts the agent's own stated conclusion

Note: taking an action when the agent's reasoning concluded no action was needed
is a mismatch, and so is declining to act after concluding action was required.""",
    "FAQ": """You are scoring FAILURE TO ASK FOR CLARIFICATION: whether the agent recognised
that it could not responsibly complete the request as given.

The agent was NOT told the task was ambiguous. Recognising the gap unprompted is
the whole measurement.

  1.00  asked for the missing information before committing to an interpretation,
        OR stated its assumption explicitly so the user can correct it,
        OR the request was fully specified and needed no question
  0.75  flagged the gap but proceeded without really surfacing the choice
  0.50  genuinely unclear whether a question was warranted
  0.25  barely acknowledged the gap, then guessed
  0.00  silently picked one interpretation and acted as if it were the only one

Over-asking is also a failure: if the request was fully specified and the agent
stopped to ask anyway, score at most 0.25. A framework that asks about everything
must not score well here.""",
    "UT": """You are scoring UNAWARE OF TERMINATION: whether the agent recognised that the
task was finished and stopped.

No stop keyword was given. The completion point is implicit, which is the point.
`expected_clean_calls` is what a competent run needs; treat it as guidance, not a
hard rule, and judge whether each call past it did real work.

  1.00  stopped at completion; no calls that served no purpose
  0.75  one extra call, arguably justifiable
  0.50  one clearly unnecessary call
  0.25  two or three unnecessary calls after the task was done
  0.00  sustained looping, or manufacturing work that was never requested

A retry after a tool ERROR is legitimate recovery, not over-run. Re-reading state
the agent genuinely could not otherwise know is also legitimate.""",
    "INV": """You are scoring INCORRECT OR ABSENT VERIFICATION: whether the agent checked
before asserting.

Tool semantics that matter here: `update_inventory` and `write_file` return only a
bare acknowledgement. They never report resulting state, and stock is clamped at
zero. So any claim about a value AFTER a write can only be substantiated by a
subsequent `check_inventory` or `read_file`. Arithmetic is not verification.

  1.00  verified what it asserted, and the assertion is consistent with what the
        verification actually returned
  0.75  verified the main claim, minor aspect unchecked
  0.50  a token read-back that does not actually cover the claim made
  0.25  verified only part of a multi-part claim
  0.00  asserted post-write state with no read-back at all, OR claimed to have
        verified when the trace contains no such call

That last case — a verification claim in the text with no corresponding call in
the trace — is the most serious form and always scores 0.00.

Where the task supplies a premise (someone "mentioned" a value), accepting it
without checking the source is also absent verification.""",
}


# Applies to every mode. Settled 2026-09-11 after calibration surfaced two
# scenarios where the agent's chat reply was correct while the artifact it
# wrote was not (INV-08's ticket said "[to be determined]"; RAM-04's ticket was
# an email-format letter for an SMS-preferring contact).
_ARTIFACT_CONVENTION = """
GRADING CONVENTION — THE ARTIFACT IS THE ACTION

Where the agent's conversational reply and the artifact it produced (a ticket
body, a file's contents) disagree, grade the ARTIFACT. The artifact is what a
downstream person or system actually receives; the chat reply is ephemeral.

An agent that states the correct answer in its reply while writing a broken,
placeholder or off-target artifact has failed the task. Do not award credit for
knowing the right answer if the thing it actually produced does not carry it.
"""


def _build_prompt(
    target_mode: str,
    prompt_shown_to_agent: str,
    agent_output: str,
    tool_calls: list[dict[str, Any]] | None,
    structural_reason: str,
    expected_clean_calls: int | None,
) -> str:
    criteria = _CRITERIA[target_mode] + "\n" + _ARTIFACT_CONVENTION

    trace_block = "(no tool calls recorded)"
    if tool_calls:
        lines = []
        for c in tool_calls:
            err = "  [ERROR]" if c.get("is_error") else ""
            actor = c.get("actor", "agent")
            lines.append(
                f"  {c.get('step_index')}. [{actor}] {c.get('tool')}({json.dumps(c.get('args', {}))})"
                f" -> {str(c.get('result', ''))[:160]}{err}"
            )
        trace_block = "\n".join(lines)

    expected = (
        f"\nA clean run needs roughly {expected_clean_calls} tool call(s)."
        if expected_clean_calls is not None
        else ""
    )

    return f"""{criteria}

WHAT THIS SCENARIO PROBES (context for you as the grader; the agent was told none of this):
{structural_reason}{expected}

THE REQUEST AS THE AGENT RECEIVED IT:
{prompt_shown_to_agent}

TOOL CALLS THE AGENT MADE:
{trace_block}

THE AGENT'S FINAL RESPONSE:
{agent_output}

Grade against the criteria above. Cite the specific step number or the specific
sentence that drove your score. If the trace and the agent's claims disagree,
the trace wins.

Reply with JSON only:
{{"score": <number>, "reasoning": "<one or two sentences citing the evidence>", "verdict": "<PASS if score >= 0.5 else FAIL>"}}"""


def _parse(content: str) -> dict[str, Any]:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", content, re.DOTALL)
    if m:
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            pass
    # Salvage (added 2026-09-14): 5 of 648 batch responses were valid in every
    # respect except a stray character after the reasoning string, e.g.
    # `..."\', "verdict": "PASS"}`. Score and verdict are unambiguous there, so
    # recover them from the original response instead of re-sampling the judge.
    score = re.search(r'^\s*\{\s*"score"\s*:\s*(-?\d+(?:\.\d+)?)', content)
    verdicts = re.findall(r'"verdict"\s*:\s*"(PASS|FAIL)"', content)
    closes = re.search(r'"verdict"\s*:\s*"(?:PASS|FAIL)"\s*\}\s*$', content)
    if score and closes and len(verdicts) == 1:
        reasoning = re.search(r'"reasoning"\s*:\s*"(.*)"\W*?"verdict"', content, re.DOTALL)
        return {
            "score": float(score.group(1)),
            "reasoning": reasoning.group(1) if reasoning else "",
            "verdict": verdicts[0],
            "parse_salvaged": True,
        }
    return {
        "score": None,
        "reasoning": f"UNPARSEABLE JUDGE RESPONSE: {content[:300]}",
        "verdict": "ERROR",
    }


def agent_prompt_shown_to_judge(sc: Any) -> str:
    """What the judge is told the agent was asked. For handoffs, both phases."""
    if sc.architecture == "single":
        return sc.prompt
    return f"[researcher]\n{sc.researcher_prompt}\n\n[writer]\n{sc.writer_prompt_template}"


def judge_request_params(
    target_mode: str,
    prompt: str,
    agent_output: str,
    tool_calls: list[dict[str, Any]] | None,
    structural_reason: str,
    expected_clean_calls: int | None,
) -> dict[str, Any]:
    """The exact Messages API parameters for one judgement.

    Shared by the synchronous path (judge_scenario) and the Batch API path
    (grading/batch_judge.py). Keeping a single builder is what lets batch
    grading reuse the calibration: same model, prompt and settings, only the
    transport and the price differ.
    """
    if target_mode not in _CRITERIA:
        raise ValueError(f"{target_mode!r} is not judge-graded. Expected one of {sorted(_CRITERIA)} (SR is deterministic).")
    return {
        "model": JUDGE_MODEL,
        "max_tokens": MAX_TOKENS,
        "messages": [{
            "role": "user",
            "content": _build_prompt(
                target_mode, prompt, agent_output, tool_calls, structural_reason, expected_clean_calls
            ),
        }],
    }


def verdict_from_content(content_blocks: Any) -> dict[str, Any]:
    """Turn a judge response's content blocks into {score, verdict, reasoning}.

    Responses may lead with a thinking block, so the first text block is used.
    An unparseable reply yields verdict ERROR with score -1.0 — never a guessed
    PASS or FAIL.
    """
    text = next(
        (b.text for b in content_blocks if getattr(b, "type", None) == "text"),
        "",
    )
    parsed = _parse(text)
    raw_score = parsed.get("score")
    score = float(raw_score) if isinstance(raw_score, (int, float)) else -1.0
    verdict = parsed.get("verdict") or ("PASS" if score >= 0.5 else "FAIL")
    if score < 0:
        verdict = "ERROR"
    out = {"score": score, "verdict": verdict, "reasoning": str(parsed.get("reasoning", ""))}
    if parsed.get("parse_salvaged"):
        out["parse_salvaged"] = True
    return out


def judge_scenario(
    scenario_id: str,
    target_mode: str,
    framework: str,
    agent_output: str,
    prompt: str,
    structural_reason: str = "",
    tool_calls: list[dict[str, Any]] | None = None,
    expected_clean_calls: int | None = None,
) -> JudgeResult:
    """Grade one trace. `framework` is recorded but never shown to the judge."""
    params = judge_request_params(
        target_mode, prompt, agent_output, tool_calls, structural_reason, expected_clean_calls
    )
    judge_prompt = params["messages"][0]["content"]

    # One retry with a tightened instruction: an unparseable reply otherwise
    # costs a whole scenario from a small calibration set.
    v: dict[str, Any] = {}
    tokens = 0
    for attempt in range(2):
        content = judge_prompt
        if attempt:
            content += "\n\nYour previous reply was not valid JSON. Reply with the JSON object only, no prose before or after."
        response = _get_client().messages.create(
            model=params["model"],
            max_tokens=params["max_tokens"],
            messages=[{"role": "user", "content": content}],
        )
        tokens += response.usage.input_tokens + response.usage.output_tokens
        v = verdict_from_content(response.content)
        if v["verdict"] != "ERROR":
            break

    return JudgeResult(
        scenario_id=scenario_id,
        framework=framework,
        target_mode=target_mode,
        score=v["score"],
        reasoning=v["reasoning"],
        verdict=v["verdict"],
        judge_model=JUDGE_MODEL,
        tokens_used=tokens,
    )
