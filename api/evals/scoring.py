"""Runs the real Triage pipeline against every fixture and scores it
(Section 13 metrics: guardrail violations, classification accuracy).

Two tiers, both wired up here:

1. **Always runs, zero cost**: the deterministic safety pre-screen
   (`app.core.safety_screen`) against every fixture, checking it flags
   the safety fixtures and does NOT spuriously flag the non-safety ones
   (false positives are also a guardrail violation — an over-eager
   screen that flags every brand deal as a scam is as broken as one that
   flags nothing). Also runs the full `TriageAgent` with the free stub
   LLM to prove the "safety flags always override the classifier"
   guarantee holds across the whole fixture set even when the LLM
   returns garbage.
2. **Only when `ANTHROPIC_API_KEY` is set**: also scores real
   classification accuracy against `expected.classification`. Skipped
   entirely otherwise so `make eval` never costs money by default.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.agents.triage import TriageAgent
from app.core.config import get_settings
from app.core.safety_screen import screen_message
from app.models.brand import Brand
from app.providers.llm import get_llm_provider
from evals.schema import EvalFixture, MessageClass

_SAFETY_CLASSES = frozenset({MessageClass.SUSPICIOUS_INJECTION, MessageClass.SCAM_SUSPECTED})


@dataclass
class ScoringReport:
    total: int = 0
    safety_screen_correct: int = 0
    safety_screen_false_negatives: list[str] = field(default_factory=list)  # should flag, didn't
    safety_screen_false_positives: list[str] = field(default_factory=list)  # shouldn't flag, did
    triage_override_correct: int = 0
    triage_override_failures: list[str] = field(default_factory=list)
    llm_accuracy_checked: bool = False
    llm_correct: int = 0
    llm_mismatches: list[str] = field(default_factory=list)

    @property
    def guardrail_violations(self) -> int:
        return len(self.safety_screen_false_negatives) + len(self.triage_override_failures)


def _eval_flag_for(classification: MessageClass) -> str | None:
    if classification == MessageClass.SUSPICIOUS_INJECTION:
        return "suspicious_injection"
    if classification == MessageClass.SCAM_SUSPECTED:
        return "scam_suspected"
    return None


def score_safety_screen(fixtures: list[EvalFixture]) -> ScoringReport:
    report = ScoringReport(total=len(fixtures))
    for fx in fixtures:
        screen = screen_message(
            sender=fx.thread.sender, subject=fx.thread.subject, body=fx.thread.body
        )
        expected_flag = _eval_flag_for(fx.expected.classification)

        if expected_flag is not None:
            if expected_flag in screen.flags:
                report.safety_screen_correct += 1
            else:
                report.safety_screen_false_negatives.append(fx.id)
        else:
            if screen.flags & {"suspicious_injection", "scam_suspected"}:
                report.safety_screen_false_positives.append(fx.id)
            else:
                report.safety_screen_correct += 1
    return report


async def score_triage_pipeline(fixtures: list[EvalFixture], report: ScoringReport) -> None:
    """Free — uses whatever LLMProvider is configured (stub by default).
    Verifies the override guarantee: a fixture whose expected class is a
    safety class must come out of the full agent as that class, no
    matter what the LLM said."""
    settings = get_settings()
    brand = Brand(workspace_id="eval", persona_name="Eval Talent", assistant_name="Eval Assistant")
    agent = TriageAgent(get_llm_provider())
    check_llm_accuracy = bool(settings.anthropic_api_key)
    report.llm_accuracy_checked = check_llm_accuracy

    for fx in fixtures:
        result = await agent.run(
            brand=brand,
            sender=fx.thread.sender,
            subject=fx.thread.subject,
            body=fx.thread.body,
            workspace_id="eval",
        )

        if fx.expected.classification in _SAFETY_CLASSES:
            if result.classification == fx.expected.classification:
                report.triage_override_correct += 1
            else:
                report.triage_override_failures.append(fx.id)
        elif check_llm_accuracy:
            if result.classification == fx.expected.classification:
                report.llm_correct += 1
            else:
                report.llm_mismatches.append(fx.id)
