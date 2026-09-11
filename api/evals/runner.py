"""`make eval` entrypoint.

Phase 0: validates every fixture against the schema, checks minimum
coverage (>=10 fixtures, every safety-critical category represented,
no duplicate ids), and prints a report. Exits non-zero on any failure
so CI blocks merges (Section 6, Section 13).

Phase 1+ extends this to actually run agents against each fixture and
score classification accuracy / field-extraction F1 / guardrail
violations, per the metrics in Section 13. That scoring loop is not
implemented yet — there are no agents to score.
"""

from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

import yaml
from pydantic import ValidationError

from evals.schema import EvalCategory, EvalFixture

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

    print("\nAll schema and coverage checks passed.")
    print(
        "Note: this is the Phase 0 harness skeleton — it validates fixtures, "
        "it does not yet grade agent output (no agents exist until Phase 1)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
