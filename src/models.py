"""Pydantic data models for the story generator."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ChapterStatus(str, Enum):
    PENDING = "pending"
    GENERATING = "generating"
    REVIEWING = "reviewing"
    REVISING = "revising"
    COMPLETE = "complete"


class StoryStatus(str, Enum):
    CONCEPT = "concept"
    OUTLINING = "outlining"
    WRITING = "writing"
    COMPLETE = "complete"


class Character(BaseModel):
    """A character in the story."""
    name: str
    role: str = Field(description="protagonist, antagonist, supporting, etc.")
    description: str
    motivation: str
    arc: str = Field(description="How the character changes through the story")
    relationships: list[str] = Field(default_factory=list)


class WorldDetails(BaseModel):
    """World-building details for the story."""
    setting: str
    time_period: str
    technology_level: str
    society: str
    key_locations: list[str] = Field(default_factory=list)
    rules: list[str] = Field(default_factory=list, description="Unique rules of this world")
    history: str = ""


class ChapterOutline(BaseModel):
    """Outline for a single chapter."""
    number: int
    title: str
    summary: str
    key_events: list[str]
    characters_involved: list[str]
    location: str
    emotional_arc: str = Field(description="The emotional journey in this chapter")
    chapter_goal: str = Field(description="What this chapter accomplishes for the plot")


class StoryConcept(BaseModel):
    """A complete story concept with outline."""
    id: str = Field(default_factory=lambda: datetime.now().strftime("%Y%m%d_%H%M%S"))
    title: str
    logline: str = Field(description="One-sentence summary")
    synopsis: str = Field(description="2-3 paragraph overview")
    genre_tags: list[str] = Field(default_factory=list)
    themes: list[str] = Field(default_factory=list)
    world: Optional[WorldDetails] = None
    characters: list[Character] = Field(default_factory=list)
    chapter_outlines: list[ChapterOutline] = Field(default_factory=list)
    target_chapters: int = 12
    created_at: datetime = Field(default_factory=datetime.now)


class ReviewIssue(BaseModel):
    """A single issue found during chapter review."""
    category: str = Field(description="continuity, pacing, voice, plot, craft")
    severity: Severity
    location: str = Field(description="Quote of problematic text")
    description: str
    suggestion: str


class ChapterReview(BaseModel):
    """Review results for a chapter."""
    chapter_number: int
    issues: list[ReviewIssue] = Field(default_factory=list)
    overall_quality: str
    strengths: list[str] = Field(default_factory=list)
    revision_needed: bool = False
    reviewed_at: datetime = Field(default_factory=datetime.now)


class Chapter(BaseModel):
    """A generated chapter."""
    number: int
    title: str
    content: str
    word_count: int = 0
    summary: str = ""
    status: ChapterStatus = ChapterStatus.PENDING
    reviews: list[ChapterReview] = Field(default_factory=list)
    revision_count: int = 0
    generated_at: Optional[datetime] = None
    finalized_at: Optional[datetime] = None


class StoryState(BaseModel):
    """Current state of story generation."""
    concept: Optional[StoryConcept] = None
    chapters: list[Chapter] = Field(default_factory=list)
    current_chapter: int = 0
    status: StoryStatus = StoryStatus.CONCEPT
    started_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    def get_chapter_summaries(self, up_to: Optional[int] = None) -> list[str]:
        """Get summaries of all chapters up to a given number."""
        end = up_to if up_to else len(self.chapters)
        return [
            f"Chapter {ch.number}: {ch.title}\n{ch.summary}"
            for ch in self.chapters[:end]
            if ch.status == ChapterStatus.COMPLETE
        ]

    def get_completed_chapters(self) -> list[Chapter]:
        """Get all completed chapters."""
        return [ch for ch in self.chapters if ch.status == ChapterStatus.COMPLETE]


class GenerationLog(BaseModel):
    """Log entry for a generation request."""
    timestamp: datetime = Field(default_factory=datetime.now)
    action: str
    prompt_summary: str
    response_length: int
    model: str
    temperature: float
    success: bool
    error: Optional[str] = None


class AggregatedReview(BaseModel):
    """Aggregated results from multiple reviewers."""
    content_type: str = Field(description="concept, outline, or chapter")
    chapter_number: Optional[int] = None
    reviewer_results: dict[str, bool] = Field(
        default_factory=dict,
        description="Mapping of reviewer_name -> passed"
    )
    high_severity_issues: list[ReviewIssue] = Field(default_factory=list)
    medium_severity_issues: list[ReviewIssue] = Field(default_factory=list)
    low_severity_issues: list[ReviewIssue] = Field(default_factory=list)
    all_passed: bool = False
    revision_needed: bool = False
    reviewed_at: datetime = Field(default_factory=datetime.now)
