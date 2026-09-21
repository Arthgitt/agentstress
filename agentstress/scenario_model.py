"""The Scenario record shared by every scenario module.

Lives in its own module so that scenarios_phase1 (the assembled suite) and
scenarios_expansion (the 71 scenarios added to reach 100) can both import it
without importing each other.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Scenario:
    id: str
    name: str
    architecture: str  # "single" | "handoff"
    target_mode: str  # "SR" | "RAM" | "UT" | "FAQ" | "INV"
    category: str
    structural_reason: str  # grader-side only
    confidence: str  # "HIGH" | "MEDIUM" | "LOW"
    tools: list[str] = field(default_factory=list)
    prompt: str = ""
    researcher_tools: list[str] = field(default_factory=list)
    researcher_prompt: str = ""
    writer_tools: list[str] = field(default_factory=list)
    writer_prompt_template: str = ""
    is_control: bool = False
    is_exploratory: bool = False  # runs, but excluded from primary comparison
    provocation_notes: str = ""  # grader-side only
    # True only where the task genuinely calls for the same mutation to be
    # applied more than once (UT-04's "bring it down in steps of 5"). The
    # grader scores repeated identical mutations strictly unless this is set,
    # so an unannotated scenario surfaces the mistake rather than excusing it.
    repeated_mutations_expected: bool = False
    # Tool calls a clean run needs, counted across ALL phases. For handoff
    # scenarios that means researcher + writer combined, since the trace the
    # grader sees is a single merged sequence. Where the interesting constraint
    # applies to one phase only, say so in provocation_notes.
    expected_clean_calls: int | None = None
    # Retired scenarios stay defined so their existing traces remain gradeable
    # and auditable, but they are excluded from the active suite and never run
    # again. See RETIRED in scenarios_phase1.
    retired: bool = False
    retired_reason: str = ""
