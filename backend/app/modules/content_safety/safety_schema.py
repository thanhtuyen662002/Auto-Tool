from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SafetyIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    severity: Literal["info", "warning", "error"]
    category: str
    field: str | None = None
    message: str
    suggestion: str | None = None


class SafetyCheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    passed: bool
    issues: list[SafetyIssue] = Field(default_factory=list)
    warnings_count: int = 0
    errors_count: int = 0


def build_safety_result(issues: list[SafetyIssue]) -> SafetyCheckResult:
    unique: list[SafetyIssue] = []
    seen: set[tuple[str, str | None, str, str]] = set()
    for issue in issues:
        key = (issue.severity, issue.field, issue.category, issue.message)
        if key in seen:
            continue
        unique.append(issue)
        seen.add(key)
    warnings = sum(1 for issue in unique if issue.severity == "warning")
    errors = sum(1 for issue in unique if issue.severity == "error")
    return SafetyCheckResult(
        passed=errors == 0,
        issues=unique,
        warnings_count=warnings,
        errors_count=errors,
    )


def merge_safety_results(*results: SafetyCheckResult) -> SafetyCheckResult:
    issues: list[SafetyIssue] = []
    for result in results:
        issues.extend(result.issues)
    return build_safety_result(issues)
