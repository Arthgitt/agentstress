# Archived: invalid calibration run (2026-08-25)

These 25 traces were generated from scenario prompts that leaked grader-side
commentary into the agent-facing text (e.g. FAQ-01 told the agent that "our
policies" was ambiguous and that searching only one policy "is FAQ failure").

They measure instruction-following, not the failure modes, and must NOT be
hand-labelled or used for judge calibration. Retained only as evidence of the
defect. Superseded by the run in ../calibration_data/ against the rewritten
scenarios (see common/scenarios_phase1.py and tests/test_prompt_hygiene.py).
