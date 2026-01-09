"""Tests for the reviewer system."""

import pytest
from datetime import datetime

from src.models import (
    ReviewIssue,
    Severity,
    StoryConcept,
    StoryState,
    Chapter,
    ChapterStatus,
)
from src.reviewers.base import (
    ContentType,
    ReviewContext,
    ReviewResult,
)
from src.reviewers.registry import ReviewerRegistry


class TestContentType:
    """Tests for ContentType enum."""

    def test_content_type_values(self):
        """Test that content types have expected values."""
        assert ContentType.CONCEPT.value == "concept"
        assert ContentType.OUTLINE.value == "outline"
        assert ContentType.CHAPTER.value == "chapter"

    def test_content_type_is_string_enum(self):
        """Test that ContentType can be used as string."""
        assert str(ContentType.CONCEPT) == "ContentType.CONCEPT"
        assert ContentType.CONCEPT == "concept"


class TestReviewContext:
    """Tests for ReviewContext dataclass."""

    @pytest.fixture
    def sample_concept(self):
        """Create a sample concept for testing."""
        return StoryConcept(
            title="Test Story",
            logline="A test story",
            synopsis="This is a test.",
        )

    def test_create_concept_context(self, sample_concept):
        """Test creating a context for concept review."""
        context = ReviewContext(
            content_type=ContentType.CONCEPT,
            concept=sample_concept,
            content="Test content",
        )
        assert context.content_type == ContentType.CONCEPT
        assert context.concept.title == "Test Story"
        assert context.state is None
        assert context.chapter is None
        assert context.iteration == 0

    def test_create_chapter_context(self, sample_concept):
        """Test creating a context for chapter review."""
        state = StoryState(concept=sample_concept)
        chapter = Chapter(
            number=1,
            title="Chapter One",
            content="Chapter content here.",
            status=ChapterStatus.REVIEWING,
        )

        context = ReviewContext(
            content_type=ContentType.CHAPTER,
            concept=sample_concept,
            state=state,
            chapter=chapter,
            content=chapter.content,
            iteration=2,
        )

        assert context.content_type == ContentType.CHAPTER
        assert context.chapter.number == 1
        assert context.iteration == 2

    def test_context_defaults(self, sample_concept):
        """Test that context defaults are set correctly."""
        context = ReviewContext(
            content_type=ContentType.OUTLINE,
            concept=sample_concept,
        )
        assert context.state is None
        assert context.chapter is None
        assert context.chapter_outline is None
        assert context.content == ""
        assert context.iteration == 0


class TestReviewResult:
    """Tests for ReviewResult dataclass."""

    def test_create_passing_result(self):
        """Test creating a passing review result."""
        result = ReviewResult(
            reviewer_name="test_reviewer",
            content_type=ContentType.CONCEPT,
            passed=True,
            strengths=["Good pacing", "Strong characters"],
            overall_assessment="Excellent concept",
        )
        assert result.passed is True
        assert result.reviewer_name == "test_reviewer"
        assert len(result.strengths) == 2
        assert result.issues == []

    def test_create_failing_result_with_issues(self):
        """Test creating a failing result with issues."""
        issues = [
            ReviewIssue(
                category="continuity",
                severity=Severity.HIGH,
                location="Chapter 3",
                description="Timeline error",
                suggestion="Fix the dates",
            ),
            ReviewIssue(
                category="style",
                severity=Severity.MEDIUM,
                location="Chapter 1",
                description="Awkward phrasing",
                suggestion="Rewrite for clarity",
            ),
        ]

        result = ReviewResult(
            reviewer_name="correctness",
            content_type=ContentType.CHAPTER,
            passed=False,
            issues=issues,
            chapter_number=3,
        )

        assert result.passed is False
        assert len(result.issues) == 2
        assert result.chapter_number == 3

    def test_has_high_severity_issues(self):
        """Test checking for high severity issues."""
        high_issue = ReviewIssue(
            category="plot",
            severity=Severity.HIGH,
            location="test",
            description="Major problem",
            suggestion="Fix it",
        )
        low_issue = ReviewIssue(
            category="style",
            severity=Severity.LOW,
            location="test",
            description="Minor issue",
            suggestion="Consider fixing",
        )

        # Result with high severity issue
        result_with_high = ReviewResult(
            reviewer_name="test",
            content_type=ContentType.CHAPTER,
            passed=False,
            issues=[high_issue, low_issue],
        )
        assert result_with_high.has_high_severity_issues() is True

        # Result with only low severity issues
        result_without_high = ReviewResult(
            reviewer_name="test",
            content_type=ContentType.CHAPTER,
            passed=True,
            issues=[low_issue],
        )
        assert result_without_high.has_high_severity_issues() is False

        # Result with no issues
        result_no_issues = ReviewResult(
            reviewer_name="test",
            content_type=ContentType.CHAPTER,
            passed=True,
        )
        assert result_no_issues.has_high_severity_issues() is False

    def test_get_high_severity_issues(self):
        """Test filtering for high severity issues only."""
        issues = [
            ReviewIssue(
                category="continuity",
                severity=Severity.HIGH,
                location="loc1",
                description="High 1",
                suggestion="Fix 1",
            ),
            ReviewIssue(
                category="style",
                severity=Severity.MEDIUM,
                location="loc2",
                description="Medium 1",
                suggestion="Fix 2",
            ),
            ReviewIssue(
                category="plot",
                severity=Severity.HIGH,
                location="loc3",
                description="High 2",
                suggestion="Fix 3",
            ),
            ReviewIssue(
                category="craft",
                severity=Severity.LOW,
                location="loc4",
                description="Low 1",
                suggestion="Fix 4",
            ),
        ]

        result = ReviewResult(
            reviewer_name="test",
            content_type=ContentType.CHAPTER,
            passed=False,
            issues=issues,
        )

        high_issues = result.get_high_severity_issues()
        assert len(high_issues) == 2
        assert all(i.severity == Severity.HIGH for i in high_issues)
        assert high_issues[0].description == "High 1"
        assert high_issues[1].description == "High 2"

    def test_reviewed_at_default(self):
        """Test that reviewed_at is set to current time by default."""
        before = datetime.now()
        result = ReviewResult(
            reviewer_name="test",
            content_type=ContentType.CONCEPT,
            passed=True,
        )
        after = datetime.now()

        assert before <= result.reviewed_at <= after


class MockReviewer:
    """A mock reviewer for testing the registry."""

    def __init__(self, name: str, content_types: list[ContentType], pass_result: bool = True):
        self._name = name
        self._content_types = content_types
        self._pass_result = pass_result
        self._review_calls = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def supported_content_types(self) -> list[ContentType]:
        return self._content_types

    def review(self, context: ReviewContext) -> ReviewResult:
        self._review_calls.append(context)
        issues = []
        if not self._pass_result:
            issues.append(ReviewIssue(
                category="test",
                severity=Severity.HIGH,
                location="test",
                description="Test failure",
                suggestion="Fix it",
            ))
        return ReviewResult(
            reviewer_name=self._name,
            content_type=context.content_type,
            passed=self._pass_result,
            issues=issues,
        )

    def get_revision_guidance(self, result: ReviewResult) -> list[str]:
        return [f"[{self._name}] {i.description}" for i in result.issues]


class TestReviewerRegistry:
    """Tests for ReviewerRegistry."""

    @pytest.fixture
    def sample_concept(self):
        """Create a sample concept for testing."""
        return StoryConcept(
            title="Test Story",
            logline="A test story",
            synopsis="This is a test.",
        )

    def test_register_reviewer(self):
        """Test registering a reviewer."""
        registry = ReviewerRegistry()
        reviewer = MockReviewer("test", [ContentType.CONCEPT])

        registry.register(reviewer)

        assert "test" in registry.registered_reviewers
        assert "test" in registry.enabled_reviewers

    def test_register_disabled_reviewer(self):
        """Test registering a disabled reviewer."""
        registry = ReviewerRegistry()
        reviewer = MockReviewer("test", [ContentType.CONCEPT])

        registry.register(reviewer, enabled=False)

        assert "test" in registry.registered_reviewers
        assert "test" not in registry.enabled_reviewers

    def test_enable_disable_reviewer(self):
        """Test enabling and disabling reviewers."""
        registry = ReviewerRegistry()
        reviewer = MockReviewer("test", [ContentType.CONCEPT])
        registry.register(reviewer)

        # Initially enabled
        assert "test" in registry.enabled_reviewers

        # Disable
        registry.disable("test")
        assert "test" not in registry.enabled_reviewers

        # Re-enable
        registry.enable("test")
        assert "test" in registry.enabled_reviewers

    def test_get_reviewers_for_content_type(self):
        """Test getting reviewers for a specific content type."""
        registry = ReviewerRegistry()

        concept_reviewer = MockReviewer("concept_only", [ContentType.CONCEPT])
        chapter_reviewer = MockReviewer("chapter_only", [ContentType.CHAPTER])
        all_reviewer = MockReviewer("all_types", [ContentType.CONCEPT, ContentType.OUTLINE, ContentType.CHAPTER])

        registry.register(concept_reviewer)
        registry.register(chapter_reviewer)
        registry.register(all_reviewer)

        concept_reviewers = registry.get_reviewers_for_content_type(ContentType.CONCEPT)
        assert len(concept_reviewers) == 2
        reviewer_names = [r.name for r in concept_reviewers]
        assert "concept_only" in reviewer_names
        assert "all_types" in reviewer_names
        assert "chapter_only" not in reviewer_names

        chapter_reviewers = registry.get_reviewers_for_content_type(ContentType.CHAPTER)
        assert len(chapter_reviewers) == 2
        reviewer_names = [r.name for r in chapter_reviewers]
        assert "chapter_only" in reviewer_names
        assert "all_types" in reviewer_names

    def test_disabled_reviewers_not_returned(self):
        """Test that disabled reviewers are not returned."""
        registry = ReviewerRegistry()

        reviewer1 = MockReviewer("enabled", [ContentType.CONCEPT])
        reviewer2 = MockReviewer("disabled", [ContentType.CONCEPT])

        registry.register(reviewer1)
        registry.register(reviewer2)
        registry.disable("disabled")

        reviewers = registry.get_reviewers_for_content_type(ContentType.CONCEPT)
        assert len(reviewers) == 1
        assert reviewers[0].name == "enabled"

    def test_run_all_reviews(self, sample_concept):
        """Test running all applicable reviews."""
        registry = ReviewerRegistry()

        reviewer1 = MockReviewer("reviewer1", [ContentType.CONCEPT])
        reviewer2 = MockReviewer("reviewer2", [ContentType.CONCEPT])

        registry.register(reviewer1)
        registry.register(reviewer2)

        context = ReviewContext(
            content_type=ContentType.CONCEPT,
            concept=sample_concept,
            content="Test content",
        )

        results = registry.run_all_reviews(context)

        assert len(results) == 2
        assert all(r.passed for r in results)
        assert len(reviewer1._review_calls) == 1
        assert len(reviewer2._review_calls) == 1

    def test_all_passed(self):
        """Test checking if all reviews passed."""
        registry = ReviewerRegistry()

        # All passing results
        results_pass = [
            ReviewResult(reviewer_name="r1", content_type=ContentType.CONCEPT, passed=True),
            ReviewResult(reviewer_name="r2", content_type=ContentType.CONCEPT, passed=True),
        ]
        assert registry.all_passed(results_pass) is True

        # One failing result
        results_fail = [
            ReviewResult(reviewer_name="r1", content_type=ContentType.CONCEPT, passed=True),
            ReviewResult(reviewer_name="r2", content_type=ContentType.CONCEPT, passed=False),
        ]
        assert registry.all_passed(results_fail) is False

        # Empty results
        assert registry.all_passed([]) is True

    def test_get_all_revision_guidance(self, sample_concept):
        """Test aggregating revision guidance from failed reviews."""
        registry = ReviewerRegistry()

        failing_reviewer = MockReviewer("failing", [ContentType.CONCEPT], pass_result=False)
        passing_reviewer = MockReviewer("passing", [ContentType.CONCEPT], pass_result=True)

        registry.register(failing_reviewer)
        registry.register(passing_reviewer)

        context = ReviewContext(
            content_type=ContentType.CONCEPT,
            concept=sample_concept,
        )

        results = registry.run_all_reviews(context)
        guidance = registry.get_all_revision_guidance(results)

        # Only failing reviewer should contribute guidance
        assert len(guidance) == 1
        assert "[failing]" in guidance[0]


class TestSeverity:
    """Tests for Severity enum."""

    def test_severity_values(self):
        """Test severity enum values."""
        assert Severity.LOW.value == "low"
        assert Severity.MEDIUM.value == "medium"
        assert Severity.HIGH.value == "high"

    def test_severity_from_string(self):
        """Test creating severity from string."""
        assert Severity("low") == Severity.LOW
        assert Severity("medium") == Severity.MEDIUM
        assert Severity("high") == Severity.HIGH

    def test_severity_comparison(self):
        """Test that severities can be compared."""
        # String enum comparison
        assert Severity.LOW == "low"
        assert Severity.HIGH != "low"
