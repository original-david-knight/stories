"""Tests for data models."""

import pytest
from datetime import datetime

from src.models import (
    Chapter,
    ChapterOutline,
    ChapterStatus,
    Character,
    ReviewIssue,
    Severity,
    StoryConcept,
    StoryState,
    WorldDetails,
)


class TestStoryConcept:
    def test_create_basic_concept(self):
        concept = StoryConcept(
            title="Test Story",
            logline="A test story about testing",
            synopsis="This is a test synopsis.",
        )
        assert concept.title == "Test Story"
        assert concept.id is not None
        assert concept.target_chapters == 12

    def test_concept_with_world(self):
        world = WorldDetails(
            setting="Space station",
            time_period="2350 AD",
            technology_level="FTL travel",
            society="Corporate oligarchy",
        )
        concept = StoryConcept(
            title="Test",
            logline="Test",
            synopsis="Test",
            world=world,
        )
        assert concept.world.setting == "Space station"


class TestChapter:
    def test_create_chapter(self):
        chapter = Chapter(
            number=1,
            title="The Beginning",
            content="It was a dark and stormy night...",
        )
        assert chapter.number == 1
        assert chapter.status == ChapterStatus.PENDING
        assert chapter.revision_count == 0

    def test_chapter_word_count(self):
        content = "word " * 100
        chapter = Chapter(
            number=1,
            title="Test",
            content=content,
            word_count=len(content.split()),
        )
        assert chapter.word_count == 100


class TestStoryState:
    def test_get_chapter_summaries(self):
        state = StoryState()
        state.chapters = [
            Chapter(
                number=1,
                title="One",
                content="Content 1",
                summary="Summary 1",
                status=ChapterStatus.COMPLETE,
            ),
            Chapter(
                number=2,
                title="Two",
                content="Content 2",
                summary="Summary 2",
                status=ChapterStatus.COMPLETE,
            ),
            Chapter(
                number=3,
                title="Three",
                content="Content 3",
                status=ChapterStatus.PENDING,
            ),
        ]

        summaries = state.get_chapter_summaries()
        assert len(summaries) == 2
        assert "Summary 1" in summaries[0]

    def test_get_completed_chapters(self):
        state = StoryState()
        state.chapters = [
            Chapter(number=1, title="One", content="", status=ChapterStatus.COMPLETE),
            Chapter(number=2, title="Two", content="", status=ChapterStatus.PENDING),
        ]

        completed = state.get_completed_chapters()
        assert len(completed) == 1
        assert completed[0].number == 1


class TestReviewIssue:
    def test_create_issue(self):
        issue = ReviewIssue(
            category="continuity",
            severity=Severity.MEDIUM,
            location="John walked through the door",
            description="Character name inconsistent",
            suggestion="Change John to James",
        )
        assert issue.severity == Severity.MEDIUM
        assert issue.category == "continuity"
