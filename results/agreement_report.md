# Judge / human agreement — calibration

27 scenarios, LangGraph + qwen2.5:7b-instruct, judged by `claude-opus-5`. Agreement counts a score within ±0.25 (one rubric step).

| Metric | Result |
|---|---|
| Verdict agreement (PASS/FAIL) | **26/27 = 96%** |
| Score agreement (±0.25) | **27/27 = 100%** |
| Mean absolute score gap | 0.039 |
| Max score gap | 0.25 |
| Judge tokens used | 0 |

## By mode

| Mode | n | Verdict agree | Score agree | Mean gap | Judge bias |
|---|---|---|---|---|---|
| RAM | 6 | 6/6 (100%) | 6/6 (100%) | 0.000 | +0.00 (aligned) |
| FAQ | 7 | 6/7 (86%) | 7/7 (100%) | 0.079 | -0.02 (aligned) |
| UT | 6 | 6/6 (100%) | 6/6 (100%) | 0.000 | +0.00 (aligned) |
| INV | 8 | 8/8 (100%) | 8/8 (100%) | 0.062 | -0.06 (harsher) |

**Controls:** 3/3 verdict agreement.


## Disagreements (1)


### FAQ-03 (FAQ) — **verdict flip**, gap 0.25

- **Human 0.50 PASS** — Asked for clarification instead of guessing, but asked for SKU list rather than the missing threshold criterion.
- **Judge 0.25 FAIL** — The agent asked a question, but not about the actual gap: it requested SKUs ('Could you please provide me with the SKU(s) of the items you want to check?') when the request plainly implied all inventory, while never surfacing the genuinely missing criterion — what stock level counts as 'low'. It also made no tool calls, so no artifact or finding was produced, and the threshold ambiguity remains entirely unacknowledged.