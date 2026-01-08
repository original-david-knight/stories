"""Registry for managing multiple reviewers."""

from typing import Optional
from .base import Reviewer, ContentType, ReviewContext, ReviewResult


class ReviewerRegistry:
    """Registry for managing multiple reviewers.

    Handles registration, configuration, and coordinated execution
    of reviewers across different content types.
    """

    def __init__(self):
        self._reviewers: dict[str, Reviewer] = {}
        self._enabled: dict[str, bool] = {}
        self._content_type_reviewers: dict[ContentType, list[str]] = {
            ct: [] for ct in ContentType
        }

    def register(self, reviewer: Reviewer, enabled: bool = True) -> None:
        """Register a reviewer.

        Args:
            reviewer: Reviewer instance to register
            enabled: Whether this reviewer is active
        """
        name = reviewer.name
        self._reviewers[name] = reviewer
        self._enabled[name] = enabled

        for content_type in reviewer.supported_content_types:
            if name not in self._content_type_reviewers[content_type]:
                self._content_type_reviewers[content_type].append(name)

    def enable(self, name: str) -> None:
        """Enable a reviewer by name."""
        if name in self._enabled:
            self._enabled[name] = True

    def disable(self, name: str) -> None:
        """Disable a reviewer by name."""
        if name in self._enabled:
            self._enabled[name] = False

    def get_reviewers_for_content_type(
        self,
        content_type: ContentType
    ) -> list[Reviewer]:
        """Get all enabled reviewers for a content type."""
        reviewer_names = self._content_type_reviewers.get(content_type, [])
        return [
            self._reviewers[name]
            for name in reviewer_names
            if self._enabled.get(name, False)
        ]

    def run_all_reviews(self, context: ReviewContext) -> list[ReviewResult]:
        """Run all applicable enabled reviewers on content."""
        reviewers = self.get_reviewers_for_content_type(context.content_type)
        results = []

        for reviewer in reviewers:
            result = reviewer.review(context)
            results.append(result)

        return results

    def all_passed(self, results: list[ReviewResult]) -> bool:
        """Check if all reviews passed (no HIGH severity issues)."""
        return all(result.passed for result in results)

    def get_all_revision_guidance(self, results: list[ReviewResult]) -> list[str]:
        """Aggregate revision guidance from all failed reviews."""
        guidance = []
        for result in results:
            if not result.passed:
                reviewer = self._reviewers.get(result.reviewer_name)
                if reviewer:
                    guidance.extend(reviewer.get_revision_guidance(result))
        return guidance

    @property
    def registered_reviewers(self) -> list[str]:
        """Get names of all registered reviewers."""
        return list(self._reviewers.keys())

    @property
    def enabled_reviewers(self) -> list[str]:
        """Get names of all enabled reviewers."""
        return [name for name, enabled in self._enabled.items() if enabled]
