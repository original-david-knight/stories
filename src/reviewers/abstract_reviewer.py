"""Abstract base class providing common reviewer functionality."""

import json
import re
from abc import ABC, abstractmethod
from typing import Optional

from ..gemini_client import GeminiClient
from ..models import ReviewIssue, Severity
from .base import Reviewer, ReviewContext, ReviewResult, ContentType


class AbstractReviewer(ABC):
    """Abstract base class for reviewers with common functionality.

    Provides shared methods for prompt construction, JSON parsing,
    and result building that concrete reviewers can use.
    """

    def __init__(self, client: GeminiClient):
        """Initialize with a Gemini client.

        Args:
            client: Configured GeminiClient instance
        """
        self.client = client

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this reviewer."""
        pass

    @property
    @abstractmethod
    def supported_content_types(self) -> list[ContentType]:
        """Content types this reviewer can evaluate."""
        pass

    @abstractmethod
    def _get_system_instruction(self) -> str:
        """Get the system instruction for this reviewer."""
        pass

    @abstractmethod
    def _build_review_prompt(self, context: ReviewContext) -> str:
        """Build the review prompt for the given context."""
        pass

    @abstractmethod
    def _get_criteria_description(self) -> str:
        """Get the evaluation criteria description for prompts."""
        pass

    def review(self, context: ReviewContext) -> ReviewResult:
        """Perform a review of the given content."""
        prompt = self._build_review_prompt(context)

        response = self.client.generate(
            prompt,
            system_instruction=self._get_system_instruction(),
            temperature=0.3,
        )

        review_data = self._parse_json_response(response)
        issues = self._parse_issues(review_data.get("issues", []))

        passed = not any(i.severity == Severity.HIGH for i in issues)

        return ReviewResult(
            reviewer_name=self.name,
            content_type=context.content_type,
            passed=passed,
            issues=issues,
            strengths=review_data.get("strengths", []),
            overall_assessment=review_data.get("overall_quality", ""),
            chapter_number=context.chapter.number if context.chapter else None,
        )

    def get_revision_guidance(self, result: ReviewResult) -> list[str]:
        """Get guidance for revising based on review results.

        Only includes HIGH severity issues since those block passing.
        """
        guidance = []
        for issue in result.get_high_severity_issues():
            guidance.append(
                f"[{self.name.upper()} - {issue.category.upper()}] "
                f"{issue.description} "
                f'(Location: "{issue.location}") '
                f"Suggestion: {issue.suggestion}"
            )
        return guidance

    def _parse_issues(self, issues_data: list[dict]) -> list[ReviewIssue]:
        """Parse issue dictionaries into ReviewIssue objects."""
        issues = []
        for issue_data in issues_data:
            try:
                severity = Severity(issue_data.get("severity", "low").lower())
            except ValueError:
                severity = Severity.LOW

            issue = ReviewIssue(
                category=issue_data.get("category", "general"),
                severity=severity,
                location=issue_data.get("location", "")[:200],
                description=issue_data.get("description", ""),
                suggestion=issue_data.get("suggestion", ""),
            )
            issues.append(issue)
        return issues

    def _parse_json_response(self, response: str) -> dict:
        """Parse JSON from response text."""
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", response)
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            json_str = response.strip()

        start_idx = json_str.find("{")
        if start_idx == -1:
            return {"overall_quality": "unknown", "issues": [], "strengths": []}

        depth = 0
        end_idx = start_idx
        for i, char in enumerate(json_str[start_idx:], start_idx):
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    end_idx = i + 1
                    break

        json_str = json_str[start_idx:end_idx]

        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            return {"overall_quality": "unknown", "issues": [], "strengths": []}

    def _format_json_schema(self) -> str:
        """Get the common JSON response schema."""
        return """{
    "overall_quality": "excellent/good/needs_revision/poor",
    "strengths": ["strength 1", "strength 2", ...],
    "issues": [
        {
            "category": "category_name",
            "severity": "low/medium/high",
            "location": "Quote the problematic text (max 50 words)",
            "description": "What the problem is",
            "suggestion": "How to fix it"
        }
    ]
}"""

    def _format_characters(self, concept) -> str:
        """Format character info for review context."""
        if not concept.characters:
            return "No characters defined"
        return "\n".join(
            f"- {c.name} ({c.role}): {c.description}"
            for c in concept.characters
        )
