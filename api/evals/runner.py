"""`make eval` entrypoint.

Validates every fixture against the schema, checks minimum coverage
(>=10 fixtures, every safety-critical category represented, no
duplicate ids), then runs the real pipeline against them:

1. The deterministic safety pre-screen (free, always) — checked for both
   false negatives (a scam/injection fixture it fails to flag) and false
   positives (an ordinary fixture it wrongly flags).
2. The full `TriageAgent` (free, using whatever `LLMProvider` is
   configured — the offline stub by default) — checked for the override
   guarantee: a safety-class fixture must come out classified as that
   safety class no matter what the LLM said.
3. Real LLM classification accuracy against `expected.classification`,
   but ONLY when `ANTHROPIC_API_KEY` is set — otherwise skipped with a
   note, so this never costs money by default.

Exits non-zero on any schema, coverage, or guardrail failure so CI
blocks merges (Section 6, Section 13).
"""

from __future__ import annotations

import asyncio
import sys
from collections import Counter
from pathlib import Path

import yaml
from beanie import init_beanie
from mongomock_motor import AsyncMongoMockClient
from pydantic import ValidationError

from app.models import DOCUMENT_MODELS
from evals.schema import EvalCategory, EvalFixture
from evals.scoring import ScoringReport, score_safety_screen, score_triage_pipeline

FIXTURES_DIR = Path(__file__).parent / "fixtures"
MIN_FIXTURES = 10
REQUIRED_CATEGORIES = {EvalCategory.BRAND_DEAL, EvalCategory.SAFETY}


def load_fixtures() -> list[EvalFixture]:
    fixtures: list[EvalFixture] = []
    errors: list[str] = []

    for path in sorted(FIXTURES_DIR.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text())
        try:
            fixtures.append(EvalFixture.model_validate(raw))
        except ValidationError as exc:
            errors.append(f"{path.name}: {exc}")

    if errors:
        for err in errors:
            print(f"SCHEMA ERROR: {err}", file=sys.stderr)
        raise SystemExit(1)

    return fixtures


def check_coverage(fixtures: list[EvalFixture]) -> list[str]:
    problems: list[str] = []

    if len(fixtures) < MIN_FIXTURES:
        problems.append(f"Expected at least {MIN_FIXTURES} fixtures, found {len(fixtures)}.")

    ids = [f.id for f in fixtures]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        problems.append(f"Duplicate fixture ids: {sorted(dupes)}")

    present_categories = {f.category for f in fixtures}
    missing = REQUIRED_CATEGORIES - present_categories
    if missing:
        problems.append(f"Missing required categories: {sorted(c.value for c in missing)}")

    safety_fixtures = [f for f in fixtures if f.category == EvalCategory.SAFETY]
    if not any(f.expected.must_never for f in safety_fixtures):
        problems.append("At least one safety fixture must declare must_never guardrails.")

    return problems


def _print_scoring_report(report: ScoringReport) -> list[str]:
    problems: list[str] = []

    print(f"\nSafety pre-screen: {report.safety_screen_correct}/{report.total} correct")
    if report.safety_screen_false_negatives:
        problems.append(
            f"Safety screen MISSED (false negative) on: {report.safety_screen_false_negatives}"
        )
    if report.safety_screen_false_positives:
        problems.append(f"Safety screen false positives on: {report.safety_screen_false_positives}")

    print(f"Triage override guarantee: {report.triage_override_correct} fixtures correctly forced")
    if report.triage_override_failures:
        problems.append(
            f"Triage did NOT override to the safety class on: {report.triage_override_failures}"
        )

    if report.llm_accuracy_checked:
        non_safety_total = (
            report.total - report.triage_override_correct - len(report.triage_override_failures)
        )
        print(f"LLM classification accuracy: {report.llm_correct}/{non_safety_total}")
        if report.llm_mismatches:
            print(f"  Mismatches: {report.llm_mismatches}")
    else:
        print("LLM classification accuracy: SKIPPED (no ANTHROPIC_API_KEY — zero-cost mode)")

    return problems


async def _run_scored_checks(fixtures: list[EvalFixture]) -> list[str]:
    client = AsyncMongoMockClient()
    await init_beanie(database=client["greenroom_eval"], document_models=DOCUMENT_MODELS)

    report = score_safety_screen(fixtures)
    await score_triage_pipeline(fixtures, report)
    return _print_scoring_report(report)


def main() -> int:
    fixtures = load_fixtures()
    problems = check_coverage(fixtures)

    category_counts = Counter(f.category.value for f in fixtures)
    print(f"Loaded {len(fixtures)} eval fixtures from {FIXTURES_DIR}")
    for category, count in sorted(category_counts.items()):
        print(f"  {category:15s} {count}")

    if problems:
        print("\nFAILED coverage checks:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    scoring_problems = asyncio.run(_run_scored_checks(fixtures))
    if scoring_problems:
        print("\nFAILED guardrail checks:", file=sys.stderr)
        for p in scoring_problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    print("\nAll schema, coverage, and guardrail checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
