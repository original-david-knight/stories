"""Tests for the persistence layer."""

import json
import pytest
from pathlib import Path
from datetime import datetime

from src.models import (
    Chapter,
    ChapterOutline,
    ChapterReview,
    ChapterStatus,
    Character,
    ReviewIssue,
    Severity,
    StoryConcept,
    StoryState,
    StoryStatus,
    WorldDetails,
    AggregatedReview,
)
from src.persistence import StoryPersistence, GenerationHistory


class TestGenerationHistory:
    """Tests for GenerationHistory model."""

    def test_create_empty_history(self):
        """Test creating an empty history."""
        history = GenerationHistory()
        assert history.titles == []
        assert history.character_names == []
        assert history.loglines == []
        assert history.rejected_loglines == []
        assert history.max_items == 50

    def test_add_story(self):
        """Test adding a story to history."""
        history = GenerationHistory()
        concept = StoryConcept(
            title="Test Title",
            logline="Test logline",
            synopsis="Test synopsis",
            characters=[
                Character(
                    name="Alice",
                    role="protagonist",
                    description="Main character",
                    motivation="Save the world",
                    arc="Grows stronger",
                ),
                Character(
                    name="Bob",
                    role="antagonist",
                    description="Villain",
                    motivation="Rule the world",
                    arc="Falls from power",
                ),
            ],
        )

        history.add_story(concept)

        assert "Test Title" in history.titles
        assert "Test logline" in history.loglines
        assert "Alice" in history.character_names
        assert "Bob" in history.character_names

    def test_add_rejected(self):
        """Test adding a rejected concept."""
        history = GenerationHistory()
        concept = StoryConcept(
            title="Rejected Story",
            logline="This concept was rejected",
            synopsis="Test",
        )

        history.add_rejected(concept)

        assert "This concept was rejected" in history.rejected_loglines
        assert "Rejected Story" not in history.titles

    def test_trim_keeps_max_items(self):
        """Test that history is trimmed to max_items."""
        history = GenerationHistory(max_items=5)

        # Add more than max_items titles
        for i in range(10):
            concept = StoryConcept(
                title=f"Title {i}",
                logline=f"Logline {i}",
                synopsis="Test",
            )
            history.add_story(concept)

        assert len(history.titles) == 5
        assert len(history.loglines) == 5
        # Should keep the most recent ones
        assert "Title 9" in history.titles
        assert "Title 0" not in history.titles

    def test_no_duplicates(self):
        """Test that duplicates are not added."""
        history = GenerationHistory()
        concept = StoryConcept(
            title="Same Title",
            logline="Same logline",
            synopsis="Test",
        )

        history.add_story(concept)
        history.add_story(concept)

        assert history.titles.count("Same Title") == 1
        assert history.loglines.count("Same logline") == 1


class TestStoryPersistence:
    """Tests for StoryPersistence class."""

    @pytest.fixture
    def persistence(self, tmp_path):
        """Create a persistence instance with a temporary directory."""
        return StoryPersistence(tmp_path)

    @pytest.fixture
    def sample_concept(self):
        """Create a sample concept for testing."""
        return StoryConcept(
            id="test_story_123",
            title="The Test Story",
            logline="A story about testing",
            synopsis="This is a comprehensive test of persistence.",
            themes=["testing", "automation"],
            genre_tags=["sci-fi", "thriller"],
            world=WorldDetails(
                setting="A testing facility",
                time_period="2025",
                technology_level="Modern",
                society="Tech-focused",
            ),
            characters=[
                Character(
                    name="Tester",
                    role="protagonist",
                    description="A diligent tester",
                    motivation="Find all bugs",
                    arc="Becomes senior tester",
                ),
            ],
            chapter_outlines=[
                ChapterOutline(
                    number=1,
                    title="The Beginning",
                    summary="Story begins",
                    key_events=["Introduction"],
                    characters_involved=["Tester"],
                    location="Office",
                    emotional_arc="Curious",
                    chapter_goal="Set the stage",
                ),
            ],
        )

    def test_create_story(self, persistence, sample_concept):
        """Test creating a new story."""
        story_id = persistence.create_story(sample_concept)

        assert story_id == sample_concept.id
        assert (persistence.get_story_path(story_id) / "concept.json").exists()
        assert (persistence.get_story_path(story_id) / "state.json").exists()
        assert (persistence.get_story_path(story_id) / "chapters").is_dir()

    def test_save_and_load_concept(self, persistence, sample_concept):
        """Test saving and loading a concept."""
        persistence.create_story(sample_concept)

        loaded = persistence.load_concept(sample_concept.id)

        assert loaded is not None
        assert loaded.title == sample_concept.title
        assert loaded.logline == sample_concept.logline
        assert loaded.world.setting == sample_concept.world.setting
        assert len(loaded.characters) == 1
        assert loaded.characters[0].name == "Tester"

    def test_save_and_load_state(self, persistence, sample_concept):
        """Test saving and loading story state."""
        story_id = persistence.create_story(sample_concept)

        # Load and modify state
        state = persistence.load_state(story_id)
        state.status = StoryStatus.WRITING
        state.current_chapter = 1
        state.chapters = [
            Chapter(
                number=1,
                title="Chapter One",
                content="Test content",
                status=ChapterStatus.COMPLETE,
            )
        ]
        persistence.save_state(story_id, state)

        # Reload and verify
        reloaded = persistence.load_state(story_id)
        assert reloaded.status == StoryStatus.WRITING
        assert reloaded.current_chapter == 1
        assert len(reloaded.chapters) == 1

    def test_save_chapter(self, persistence, sample_concept):
        """Test saving a chapter."""
        story_id = persistence.create_story(sample_concept)

        chapter = Chapter(
            number=1,
            title="The First Chapter",
            content="This is the chapter content.\n\nWith multiple paragraphs.",
            word_count=8,
            status=ChapterStatus.COMPLETE,
        )
        persistence.save_chapter(story_id, chapter)

        chapters_path = persistence.get_story_path(story_id) / "chapters"
        assert (chapters_path / "01_the_first_chapter.md").exists()
        assert (chapters_path / "01_meta.json").exists()

        # Verify markdown content
        md_content = (chapters_path / "01_the_first_chapter.md").read_text()
        assert "# Chapter 1: The First Chapter" in md_content
        assert "This is the chapter content." in md_content

    def test_save_and_load_review(self, persistence, sample_concept):
        """Test saving a chapter review."""
        story_id = persistence.create_story(sample_concept)

        review = ChapterReview(
            chapter_number=1,
            issues=[
                ReviewIssue(
                    category="continuity",
                    severity=Severity.MEDIUM,
                    location="Paragraph 3",
                    description="Timeline issue",
                    suggestion="Fix dates",
                ),
            ],
            overall_quality="good",
            strengths=["Strong opening", "Clear prose"],
        )
        persistence.save_review(story_id, review)

        review_file = persistence.get_story_path(story_id) / "chapters" / "01_review.json"
        assert review_file.exists()

        data = json.loads(review_file.read_text())
        assert data["overall_quality"] == "good"
        assert len(data["issues"]) == 1

    def test_save_aggregated_review_for_chapter(self, persistence, sample_concept):
        """Test saving aggregated review for a chapter."""
        story_id = persistence.create_story(sample_concept)

        review = AggregatedReview(
            content_type="chapter",
            chapter_number=1,
            reviewer_results={"correctness": True, "style": True},
            all_passed=True,
        )
        persistence.save_aggregated_review(story_id, review)

        review_file = persistence.get_story_path(story_id) / "chapters" / "01_aggregated_review.json"
        assert review_file.exists()

    def test_save_aggregated_review_for_concept(self, persistence, sample_concept):
        """Test saving aggregated review for a concept."""
        story_id = persistence.create_story(sample_concept)

        review = AggregatedReview(
            content_type="concept",
            reviewer_results={"correctness": True},
            all_passed=True,
        )
        persistence.save_aggregated_review(story_id, review)

        review_file = persistence.get_story_path(story_id) / "concept_review.json"
        assert review_file.exists()

    def test_list_stories(self, persistence, sample_concept):
        """Test listing all stories."""
        # Initially empty
        assert persistence.list_stories() == []

        # Create a story
        persistence.create_story(sample_concept)

        stories = persistence.list_stories()
        assert len(stories) == 1
        assert stories[0]["id"] == sample_concept.id
        assert stories[0]["title"] == sample_concept.title
        assert stories[0]["status"] == "concept"

    def test_list_stories_sorted_by_date(self, persistence):
        """Test that stories are sorted by updated_at descending."""
        # Create multiple stories
        for i in range(3):
            concept = StoryConcept(
                id=f"story_{i}",
                title=f"Story {i}",
                logline=f"Logline {i}",
                synopsis="Test",
            )
            persistence.create_story(concept)

        stories = persistence.list_stories()
        assert len(stories) == 3

        # Most recently updated should be first
        dates = [s["updated_at"] for s in stories]
        assert dates == sorted(dates, reverse=True)

    def test_list_stories_handles_corrupt_files(self, persistence, sample_concept):
        """Test that corrupt story files don't break listing."""
        # Create a valid story
        persistence.create_story(sample_concept)

        # Create a corrupt story directory
        corrupt_path = persistence.base_path / "corrupt_story"
        corrupt_path.mkdir()
        (corrupt_path / "state.json").write_text("not valid json")

        # Should still list the valid story
        stories = persistence.list_stories()
        assert len(stories) == 1
        assert stories[0]["id"] == sample_concept.id

    def test_load_nonexistent_concept(self, persistence):
        """Test loading a nonexistent concept returns None."""
        assert persistence.load_concept("nonexistent") is None

    def test_load_nonexistent_state(self, persistence):
        """Test loading a nonexistent state returns None."""
        assert persistence.load_state("nonexistent") is None

    def test_export_story_markdown(self, persistence, sample_concept):
        """Test exporting a story to markdown."""
        story_id = persistence.create_story(sample_concept)

        # Add completed chapters
        state = persistence.load_state(story_id)
        state.chapters = [
            Chapter(
                number=1,
                title="Chapter One",
                content="First chapter content.",
                status=ChapterStatus.COMPLETE,
            ),
            Chapter(
                number=2,
                title="Chapter Two",
                content="Second chapter content.",
                status=ChapterStatus.COMPLETE,
            ),
        ]
        persistence.save_state(story_id, state)

        export_path = persistence.export_story(story_id)

        assert Path(export_path).exists()
        content = Path(export_path).read_text()
        assert sample_concept.title in content
        assert sample_concept.logline in content
        assert "Chapter One" in content
        assert "Chapter Two" in content

    def test_export_nonexistent_story_raises(self, persistence):
        """Test that exporting nonexistent story raises ValueError."""
        with pytest.raises(ValueError, match="not found"):
            persistence.export_story("nonexistent")

    def test_slugify(self, persistence):
        """Test the slugify helper method."""
        assert persistence._slugify("Hello World") == "hello_world"
        assert persistence._slugify("Test!@#$%") == "test"
        assert persistence._slugify("Multiple   Spaces") == "multiple_spaces"
        assert persistence._slugify("A" * 100)[:50] == "a" * 50  # Truncated

    def test_history_persistence(self, persistence):
        """Test saving and loading generation history."""
        concept = StoryConcept(
            title="History Test",
            logline="Testing history",
            synopsis="Test",
        )

        # Add to history
        persistence.add_to_history(concept)

        # Load history
        history = persistence.load_history()
        assert "History Test" in history.titles

    def test_history_load_empty(self, persistence):
        """Test loading history when file doesn't exist."""
        history = persistence.load_history()
        assert isinstance(history, GenerationHistory)
        assert history.titles == []

    def test_history_load_corrupt(self, persistence):
        """Test loading corrupt history file."""
        persistence._history_file.write_text("not valid json")
        history = persistence.load_history()
        assert isinstance(history, GenerationHistory)

    def test_add_rejected_concept(self, persistence):
        """Test adding a rejected concept to history."""
        concept = StoryConcept(
            title="Rejected",
            logline="This was rejected",
            synopsis="Test",
        )

        persistence.add_rejected_concept(concept)

        history = persistence.load_history()
        assert "This was rejected" in history.rejected_loglines


class TestChapterContentLoading:
    """Tests for chapter content loading from files."""

    @pytest.fixture
    def persistence(self, tmp_path):
        """Create a persistence instance."""
        return StoryPersistence(tmp_path)

    @pytest.fixture
    def story_with_chapter(self, persistence):
        """Create a story with a saved chapter."""
        concept = StoryConcept(
            id="chapter_test",
            title="Chapter Test",
            logline="Test",
            synopsis="Test",
            chapter_outlines=[
                ChapterOutline(
                    number=1,
                    title="Test Chapter",
                    summary="Test",
                    key_events=["Event"],
                    characters_involved=["Character"],
                    location="Location",
                    emotional_arc="Arc",
                    chapter_goal="Goal",
                ),
            ],
        )
        story_id = persistence.create_story(concept)

        # Save a chapter with full content
        chapter = Chapter(
            number=1,
            title="Test Chapter",
            content="This is the full chapter content with many words." * 100,
            word_count=800,
            status=ChapterStatus.COMPLETE,
        )
        persistence.save_chapter(story_id, chapter)

        return story_id

    def test_load_chapter_content_from_meta(self, persistence, story_with_chapter):
        """Test that chapter content is loaded from meta files when needed."""
        # Manually create a state with truncated content
        state = persistence.load_state(story_with_chapter)
        state.chapters = [
            Chapter(
                number=1,
                title="Test Chapter",
                content="Short",  # Less than 100 chars
                status=ChapterStatus.COMPLETE,
            )
        ]
        persistence.save_state(story_with_chapter, state)

        # Reload - should load full content from meta file
        reloaded = persistence.load_state(story_with_chapter)

        # Content should be loaded from meta file
        assert len(reloaded.chapters[0].content) > 100
