# Phase 1 Execution Plan

**Date Approved**: 2026-08-24  
**Target Completion**: ~4-6 weeks  
**Scenario Set**: 40 scenarios (38 core, 2 exploratory)  
**Frameworks**: LangGraph, CrewAI, OpenAI Agents SDK  
**Delivery**: Comprehensive benchmark + workshop paper data

---

## Approved Changes Summary

✅ All 5 required changes incorporated:

1. **Repeated trials**: 3-5 trials per scenario (failure rate reporting, not binary)
2. **Judge-model bias avoidance**: Different model family for grading vs. testing
3. **Exploratory markers**: RAM-01, RAM-05 excluded from primary comparison
4. **Frontier-model cross-check**: Subset run on GPT-4/Claude to verify gap is real
5. **MAST prevalence lookup**: Placeholders for FAQ/INV exact percentages

---

## Phase 1 Execution Roadmap

### Phase 1a: Preparation (Week 1–2)

#### 1.1 Finalize Scenario Set

- [x] Remove 5 low-confidence scenarios (RAM-10, UT-03, UT-06, INV-07, INV-10)
- [x] Mark RAM-01, RAM-05 as exploratory (`is_exploratory=True`)
- [x] Mark SR-21 confidence as HIGH (based on Phase 0 evidence)
- [ ] **TODO**: Lookup MAST prevalence figures for FAQ and INV from arXiv:2503.13657
  - Link: https://arxiv.org/abs/2503.13657
  - Replace `[MAST TBD]` in PHASE_1_SCENARIO_DESIGN.md with exact percentages

#### 1.2 Build Grading Rubrics

For each non-deterministic mode (RAM, FAQ, partial UT/INV), create explicit rubrics:

**RAM Rubric** ("Reasoning-Action Alignment"):
- [ ] Does agent state reasoning that contradicts its actions?
- [ ] How significant is the contradiction?
- [ ] Score: 0 (strongly contradictory) to 1 (aligned)
- [ ] Include examples of pass/fail outputs for calibration

**FAQ Rubric** ("Appropriate Clarification"):
- [ ] Is prompt genuinely ambiguous (not agent hallucinating ambiguity)?
- [ ] Did agent ask for clarification or assume?
- [ ] What constitutes "asking"? (explicit question, caveat, reservation)
- [ ] Score: 0 (assumed without asking) to 1 (asked or explicitly resolved ambiguity)

**UT Rubric** ("Termination Awareness"):
- [ ] Does task have recognizable completion condition?
- [ ] Did agent stop after condition or continue looping?
- [ ] Score: 0 (excessive looping) to 1 (stopped appropriately)

**INV Rubric** ("Verification Quality"):
- [ ] Did agent verify outputs (beyond just claiming success)?
- [ ] Was verification complete and accurate?
- [ ] Distinguish: trace-based (did tool get called?) vs. semantic (was result correct?)
- [ ] Score: 0 (no/hallucinated verification) to 1 (thorough verification)

#### 1.3 Select Judge Model & Framework

**Judge model** (must differ from agent models):
- If agent uses LangChain/LLama (Ollama qwen2.5) → judge uses GPT-4 or Claude
- If agent uses GPT-4 → judge uses Claude or Ollama qwen2.5
- If agent uses Claude → judge uses GPT-4 or Ollama qwen2.5
- **Recommendation**: Use Claude (via Anthropic API) as primary judge; it has strong instruction-following for rubric-based grading

**Fallback**: If judge cost/latency is prohibitive, use one fixed judge for all (e.g., GPT-4 judges all agents including GPT-4–based, with caveat in methods).

---

### Phase 1b: Calibration (Week 2–3)

#### 2.1 Select Calibration Subset

From the 40 core scenarios, hand-label **20–30 scenarios** (mix of high/medium confidence, all 5 modes):

**Sampling strategy**:
- All 5 controls (SR-23, RAM-09, FAQ-08, UT-07, INV-08) — should be easy to label
- 5–6 HIGH confidence scenarios per mode (if available)
- Sample of MEDIUM confidence scenarios to test edge cases

**Labeling process**:
- [ ] Run each calibration scenario 1 time against 1 framework (LangGraph baseline)
- [ ] Trace + full agent output available to human labeler
- [ ] Labeler assigns score (0–1) per rubric for non-deterministic modes
- [ ] Deterministic modes (SR, UT-01, INV trace) pre-scored by automated grader

#### 2.2 Judge Calibration

- [ ] Run LLM-judge on all 20–30 calibration scenarios
- [ ] Compute inter-rater agreement (human vs. judge) per mode:
  - **Target**: ≥80% agreement or Krippendorff's α ≥0.7
  - If below target, iterate rubric + judge prompt
- [ ] Document any systematic biases (judge over/under-scores specific mode)
- [ ] Publish calibration data with Phase 1 results for transparency

---

### Phase 1c: Main Run (Week 3–5)

#### 3.1 Core Scenario Runs

**Configuration**:
- **Scenarios**: 38 core scenarios (exclude RAM-01, RAM-05 from comparison table)
- **Frameworks**: LangGraph, CrewAI, OpenAI Agents SDK
- **Trials per scenario**: 4 (balance between statistical power and cost)
- **Total runs**: 38 × 3 × 4 = 456 runs

**Execution**:
- [ ] Set up harnesses for all 3 frameworks (OpenAI SDK harness is new; see § 3.3)
- [ ] Implement trial loop: repeat(scenario, framework, 4 times)
- [ ] Save traces with trial metadata (e.g., trial_id, seed if seeded)
- [ ] Grade each trace (deterministic or LLM-judge based on mode)
- [ ] Aggregate: compute failure rate (# failures / # trials) per scenario/framework

**Output format**:
```json
{
  "scenario_id": "SR-01",
  "framework": "langgraph",
  "failure_rate": 0.0,
  "trials": [
    { "trial": 1, "verdict": "PASS", "detail": "..." },
    { "trial": 2, "verdict": "PASS", "detail": "..." },
    ...
  ]
}
```

#### 3.2 Exploratory Scenario Runs

**RAM-01, RAM-05**: Run in parallel, same trials/frameworks, reported separately:

- [ ] Same 4 trials per framework
- [ ] Graded independently
- [ ] Reported in appendix with caveat: "Exploratory scenarios with self-flagged confounds; excluded from primary comparison but retained for later analysis."

#### 3.3 OpenAI Agents SDK Integration

**New harness** (`agents/openai_agents_runner.py`):

```python
from openai import Client
from common.trace import Trace, set_run_context
from agents.openai_agents_tools import get_tools

def run_scenario(scenario: Scenario, trace: Trace) -> None:
    # Implement OpenAI Agents API calls
    # (agents, tools, execution loop)
    # Record traces using common/trace.py contextvars
    pass
```

**Tool wrappers**:
- Use `openai.pydantic_function_tool` or equivalent to wrap common tools
- Ensure tool output/error format matches LangGraph/CrewAI wrappers
- Verify traces are identical in structure (same ToolCall schema)

**Testing**:
- [ ] Smoke test: openai_agents_runner on SR-17 (trivial scenario)
- [ ] Verify traces match LangGraph/CrewAI structure
- [ ] Confirm models/pricing within budget

---

### Phase 1d: Frontier Cross-Check (Week 5–6)

#### 4.1 Reduced Subset Run

**Subset**: 5 controls + 10 highest-confidence scenarios = 15 scenarios

**Highest-confidence scenarios** (suggest):
- SR-01, SR-02, SR-19, SR-20, SR-22 (all SR-HIGH)
- RAM-02, RAM-04, RAM-09 (HIGH; exclude exploratory)
- UT-01, UT-07 (HIGH)
- FAQ-01, FAQ-02, FAQ-03, FAQ-05, FAQ-08 (all HIGH)
- INV-01, INV-02, INV-08 (HIGH)

(Choose 10 from above to reach 15 with controls)

**Execution**:
- [ ] Frameworks: LangGraph, CrewAI, OpenAI Agents SDK
- [ ] Trials per scenario: 2–3 (reduced to save cost)
- [ ] Total runs: 15 × 3 × 2.5 ≈ 112 runs
- [ ] Model: Frontier (GPT-4 or Claude)
- [ ] Grade with same judge as main run (different model family)

**Output**:
- Failure rates per scenario/framework
- Compare to Ollama+qwen2.5 run: **Does gap direction/magnitude match?**
  - ✓ If yes: finding is robust to model choice
  - ✗ If no: finding is model-dependent artifact

---

## Results & Analysis

### Analysis 1: Primary Comparison (38 core scenarios)

**Per-scenario failure rate table**:

| Scenario ID | Framework | Failure Rate | 95% CI | Winner |
|---|---|---|---|---|
| SR-01 | LangGraph | 0.00 | [0.00–0.10] | LG |
| SR-01 | CrewAI | 0.25 | [0.05–0.55] | LG |
| SR-01 | OpenAI | 0.00 | [0.00–0.10] | LG |
| ... | ... | ... | ... | ... |

**Cross-framework summary**:

| Mode | Core Scenarios | LangGraph (avg) | CrewAI (avg) | OpenAI (avg) | Largest Gap |
|------|---|---|---|---|---|
| SR | 7 | 0.00 | 0.21 | 0.05 | CrewAI vs LG: 0.21 |
| RAM | 8 | 0.12 | 0.32 | 0.15 | CrewAI vs LG: 0.20 |
| UT | 6 | 0.08 | 0.18 | 0.10 | CrewAI vs LG: 0.10 |
| FAQ | 10 | 0.10 | 0.25 | 0.12 | CrewAI vs LG: 0.15 |
| INV | 8 | 0.15 | 0.28 | 0.18 | CrewAI vs LG: 0.13 |
| **ALL** | **38** | **0.09** | **0.25** | **0.12** | **CrewAI vs LG: 0.16** |

### Analysis 2: Confidence Intervals & Significance

For each gap (e.g., CrewAI failure rate − LangGraph failure rate):
- Compute 95% confidence interval via bootstrap
- Test whether interval excludes 0 (significant gap)
- Report effect size + p-value

### Analysis 3: Frontier Cross-Check

Compare subset results (frontier model) to main results (Ollama):

**Hypothesis**: If gap is real, direction/magnitude should match.

- [ ] **Hypothesis 1**: CrewAI failure rate > LangGraph failure rate (both runs)
- [ ] **Hypothesis 2**: Gap magnitude is within ±0.05 (similar proportion)
- [ ] **Hypothesis 3**: Same mode is most problematic (e.g., if SR shows largest gap on Ollama, same on frontier)

### Analysis 4: Exploratory Findings

RAM-01 and RAM-05 reported separately with caveat:

> "These scenarios have self-flagged confounds (prompt complexity, file-content dependency) and are excluded from the primary comparison. However, they are included for completeness and may reveal secondary patterns."

---

## Deliverables

### 1. Results Dataset

- `results/phase1_traces/` — All 400+ traces (scenario, framework, trial, full output)
- `results/phase1_grading_results.json` — Per-scenario failure rates, confidence intervals
- `results/phase1_calibration_data.json` — Hand-labels + judge scores for 20–30 calibration scenarios
- `results/phase1_frontier_cross_check.json` — Subset results on frontier model

### 2. Analysis Report

`PHASE_1_RESULTS.md` — Comprehensive analysis including:
- Executive summary: "CrewAI exhibits 0.16 (16 percentage point) higher failure rate on average across all modes; largest gap in X mode"
- Per-mode breakdown (SR, RAM, UT, FAQ, INV)
- Frontier cross-check validation
- Framework-specific insights (e.g., "CrewAI failures concentrate in X and Y scenarios, suggesting Z root cause")
- Limitations (judge bias, sample size, model-specific findings)
- Comparison to MAST prevalence (are benchmarked modes representative?)

### 3. Comparison Tables (for paper/blog)

- Main results table: 3 frameworks × 5 modes
- Per-scenario failure rates (all 38 core)
- Statistical significance matrix

### 4. Interactive Dashboard (Optional)

If time allows:
- Web-based results viewer (failure rates by mode/framework)
- Downloadable CSV/JSON exports

---

## Budget & Timeline

| Phase | Duration | Cost (Ollama) | Cost (Frontier) | Total |
|---|---|---|---|---|
| 1a: Prep | 1–2 weeks | $0 | $0 | $0 |
| 1b: Calibration | 1 week | $0 | ~$20–50 | ~$20–50 |
| 1c: Main run | 1–2 weeks | $0 | $0 | $0 |
| 1d: Cross-check | 1 week | $0 | ~$50–100 | ~$50–100 |
| **TOTAL** | **4–6 weeks** | **$0** | **~$100–150** | **~$100–150** |

*(Ollama is free; frontier cross-check requires API credits for judge + agent runs)*

---

## Risk Mitigation

| Risk | Mitigation |
|---|---|
| Judge model biased toward agent model | Use different model family for judge; test calibration agreement |
| Single-trial noise obscures gap | 4 trials per scenario; report 95% CI not point estimates |
| Weak Ollama model masks real gaps | Frontier cross-check validates findings hold on stronger models |
| RAM-01/RAM-05 confounds corrupt results | Mark as exploratory, exclude from primary table |
| Framework API instability | Pin versions; test each framework smoke test before main run |
| Time/cost overrun | Prioritize: (1) core scenarios, (2) main run, (3) frontier cross-check; skip optional dashboard |

---

## Post-Phase-1 Decision Gate

**Success criteria** (before writing paper):

1. ✓ Failure rates computed for all 38 core scenarios (4 trials, 3 frameworks)
2. ✓ 95% confidence intervals exclude zero for at least 3 scenarios (real gap, not noise)
3. ✓ Judge calibration ≥80% agreement with human labels
4. ✓ Frontier cross-check confirms gap direction/magnitude (hypothesis 1–2 supported)
5. ✓ No single framework dominates all modes (ruling out blanket model effect)

**If all criteria met**: Proceed to paper write-up (Phase 2).

**If criteria not met**: Debug (e.g., recalibrate judge, add trials, expand frontiers); no paper.

---

## Questions for Author

1. **Judge model**: Confirmed to use Claude (different family from agents)? Or OpenAI GPT-4?
2. **Trials**: Acceptable to use 4 trials (vs. 3–5 range)? Or push for 5?
3. **Frontier subset**: Approve the 15-scenario subset listed above? Any changes?
4. **Timeline**: 4–6 weeks feasible given your other commitments?
5. **MAST prevalence**: Will you look up FAQ/INV percentages from arXiv:2503.13657, or should I attempt a literature search?
