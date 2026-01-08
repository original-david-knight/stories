"""Core abstractions for the multi-reviewer system."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Protocol, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import StoryConcept, StoryState, Chapter, ChapterOutline, ReviewIssue, Severity


class ContentType(str, Enum):
    """Type of content being reviewed."""
    CONCEPT = "concept"
    OUTLINE = "outline"
    CHAPTER = "chapter"


@dataclass
class ReviewContext:
    """Context provided to reviewers for analysis."""
    content_type: ContentType
    concept: "StoryConcept"
    state: Optional["StoryState"] = None
    chapter: Optional["Chapter"] = None
    chapter_outline: Optional["ChapterOutline"] = None
    content: str = ""
    iteration: int = 0


@dataclass
class ReviewResult:
    """Result from a single reviewer."""
    reviewer_name: str
    content_type: ContentType
    passed: bool
    issues: list["ReviewIssue"] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)
    overall_assessment: str = ""
    reviewed_at: datetime = field(default_factory=datetime.now)
    chapter_number: Optional[int] = None

    def has_high_severity_issues(self) -> bool:
        """Check if any HIGH severity issues exist."""
        from ..models import Severity
        return any(issue.severity == Severity.HIGH for issue in self.issues)

    def get_high_severity_issues(self) -> list["ReviewIssue"]:
        """Get only HIGH severity issues for revision."""
        from ..models import Severity
        return [i for i in self.issues if i.severity == Severity.HIGH]


class Reviewer(Protocol):
    """Protocol defining the reviewer interface.

    All reviewers must implement this interface to be used
    in the multi-reviewer system.
    """

    @property
    def name(self) -> str:
        """Unique identifier for this reviewer."""
        ...

    @property
    def supported_content_types(self) -> list[ContentType]:
        """Content types this reviewer can evaluate."""
        ...

    def review(self, context: ReviewContext) -> ReviewResult:
        """Perform a review of the given content."""
        ...

    def get_revision_guidance(self, result: ReviewResult) -> list[str]:
        """Get guidance for revising based on review results."""
        ...
