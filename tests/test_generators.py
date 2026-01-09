"""Tests for story generators."""

import pytest
from unittest.mock import Mock, MagicMock

from src.models import (
    Chapter,
    ChapterOutline,
    ChapterStatus,
    Character,
    StoryConcept,
    StoryState,
    WorldDetails,
)
from src.generators.concept import ConceptGenerator, MAX_AVOID_NAMES, MAX_AVOID_TITLES, MAX_AVOID_LOGLINES
from src.generators.chapter import ChapterGenerator, VOICE_CONTINUITY_WORDS, SUMMARY_CONTENT_LIMIT


class TestConceptGenerator:
    """Tests for ConceptGenerator class."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Gemini client."""
        return Mock()

    @pytest.fixture
    def generator(self, mock_client):
        """Create a ConceptGenerator with mock client."""
        return ConceptGenerator(mock_client)

    @pytest.fixture
    def sample_concept(self):
        """Create a sample concept for testing."""
        return StoryConcept(
            title="Test Story",
            logline="A test about testing",
            synopsis="This is a test synopsis.",
            themes=["testing", "automation"],
            characters=[
                Character(
                    name="Alice",
                    role="protagonist",
                    description="Main character",
                    motivation="Test things",
                    arc="Becomes better at testing",
                ),
                Character(
                    name="Bob",
                    role="antagonist",
                    description="Villain",
                    motivation="Break things",
                    arc="Gets caught",
                ),
            ],
        )

    def test_build_avoid_section_empty(self, generator):
        """Test building avoid section with no inputs."""
        result = generator._build_avoid_section()
        assert result == ""

    def test_build_avoid_section_with_titles(self, generator):
        """Test building avoid section with titles."""
        titles = ["Title 1", "Title 2", "Title 3"]
        result = generator._build_avoid_section(avoid_titles=titles)

        assert "Do NOT use or closely resemble" in result
        assert "Title 1" in result
        assert "Title 2" in result
        assert "Title 3" in result

    def test_build_avoid_section_limits_titles(self, generator):
        """Test that avoid section limits number of titles."""
        titles = [f"Title {i}" for i in range(30)]
        result = generator._build_avoid_section(avoid_titles=titles)

        # Should only include last MAX_AVOID_TITLES
        assert f"Title {30 - MAX_AVOID_TITLES}" not in result or MAX_AVOID_TITLES >= 30
        assert "Title 29" in result

    def test_build_avoid_section_with_loglines(self, generator):
        """Test building avoid section with loglines."""
        loglines = ["Logline 1", "Logline 2"]
        result = generator._build_avoid_section(avoid_loglines=loglines)

        assert "DIFFERENT premises" in result
        assert "Logline 1" in result

    def test_build_avoid_section_limits_loglines(self, generator):
        """Test that avoid section limits loglines."""
        loglines = [f"Logline {i}" for i in range(10)]
        result = generator._build_avoid_section(avoid_loglines=loglines)

        # Should only include last MAX_AVOID_LOGLINES
        assert f"Logline {10 - MAX_AVOID_LOGLINES - 1}" not in result
        assert "Logline 9" in result

    def test_build_avoid_section_with_rejected(self, generator):
        """Test building avoid section with rejected loglines."""
        rejected = ["Rejected concept 1", "Rejected concept 2"]
        result = generator._build_avoid_section(rejected_loglines=rejected)

        assert "CRITICAL" in result
        assert "REJECTED" in result
        assert "Rejected concept 1" in result

    def test_normalize_relationships_empty(self, generator):
        """Test normalizing empty relationships."""
        assert generator._normalize_relationships(None) == []
        assert generator._normalize_relationships([]) == []
        assert generator._normalize_relationships("") == []

    def test_normalize_relationships_string(self, generator):
        """Test normalizing a single string relationship."""
        result = generator._normalize_relationships("Friend of the protagonist")
        assert result == ["Friend of the protagonist"]

    def test_normalize_relationships_list_of_strings(self, generator):
        """Test normalizing list of string relationships."""
        relationships = ["Friend of Alice", "Enemy of Bob"]
        result = generator._normalize_relationships(relationships)
        assert result == ["Friend of Alice", "Enemy of Bob"]

    def test_normalize_relationships_list_of_dicts(self, generator):
        """Test normalizing list of dict relationships."""
        relationships = [
            {"character": "Alice", "description": "Best friend"},
            {"name": "Bob", "relationship": "Rival"},
        ]
        result = generator._normalize_relationships(relationships)
        assert "Alice: Best friend" in result
        assert "Bob: Rival" in result

    def test_normalize_relationships_mixed(self, generator):
        """Test normalizing mixed relationship formats."""
        relationships = [
            "Simple string",
            {"character": "Alice", "description": "Friend"},
            {"name": "Bob"},  # Dict with only name
        ]
        result = generator._normalize_relationships(relationships)
        assert "Simple string" in result
        assert "Alice: Friend" in result
        assert "Bob" in result

    def test_generate_concepts_calls_client(self, generator, mock_client):
        """Test that generate_concepts calls the client correctly."""
        mock_client.generate.return_value = '''[
            {"title": "Test", "logline": "Test logline", "synopsis": "Test synopsis",
             "genre_tags": ["sci-fi"], "themes": ["testing"]}
        ]'''

        concepts = generator.generate_concepts(count=1)

        mock_client.generate.assert_called_once()
        assert len(concepts) == 1
        assert concepts[0].title == "Test"

    def test_regenerate_character_with_feedback(self, generator, mock_client, sample_concept):
        """Test regenerating a character with user feedback."""
        mock_client.generate.return_value = '''{
            "name": "New Alice",
            "role": "protagonist",
            "description": "Improved character",
            "motivation": "New motivation",
            "flaw": "New flaw",
            "arc": "New arc",
            "relationships": ["Friend of Bob"]
        }'''

        new_char = generator.regenerate_character(
            sample_concept,
            character_index=0,
            user_feedback="Make her more interesting",
        )

        assert new_char.name == "New Alice"
        assert new_char.description == "Improved character"
        # Lower temperature for revision
        call_kwargs = mock_client.generate.call_args[1]
        assert call_kwargs["temperature"] == 0.8

    def test_regenerate_character_without_feedback(self, generator, mock_client, sample_concept):
        """Test regenerating a character without feedback (fresh take)."""
        mock_client.generate.return_value = '''{
            "name": "Fresh Alice",
            "role": "protagonist",
            "description": "Completely new take",
            "motivation": "Different motivation",
            "flaw": "Different flaw",
            "arc": "Different arc",
            "relationships": []
        }'''

        new_char = generator.regenerate_character(
            sample_concept,
            character_index=0,
        )

        assert new_char.name == "Fresh Alice"
        # Higher temperature for fresh generation
        call_kwargs = mock_client.generate.call_args[1]
        assert call_kwargs["temperature"] == 0.9

    def test_regenerate_character_invalid_index(self, generator, sample_concept):
        """Test that invalid character index raises error."""
        with pytest.raises(ValueError, match="out of range"):
            generator.regenerate_character(sample_concept, character_index=10)


class TestChapterGenerator:
    """Tests for ChapterGenerator class."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Gemini client."""
        client = Mock()
        client.generate = MagicMock(return_value="Generated content")
        return client

    @pytest.fixture
    def generator(self, mock_client):
        """Create a ChapterGenerator with mock client."""
        return ChapterGenerator(mock_client)

    @pytest.fixture
    def sample_concept(self):
        """Create a sample concept with chapter outlines."""
        return StoryConcept(
            title="Test Story",
            logline="A test story",
            synopsis="This is a test.",
            themes=["testing"],
            world=WorldDetails(
                setting="Test world",
                time_period="2025",
                technology_level="Modern",
                society="Test society",
                rules=["Rule 1", "Rule 2"],
            ),
            characters=[
                Character(
                    name="Alice",
                    role="protagonist",
                    description="Main character",
                    motivation="Test things",
                    arc="Growth",
                ),
            ],
            chapter_outlines=[
                ChapterOutline(
                    number=1,
                    title="The Beginning",
                    summary="Story begins",
                    key_events=["Event 1", "Event 2"],
                    characters_involved=["Alice"],
                    location="Office",
                    emotional_arc="Curious to excited",
                    chapter_goal="Set the stage",
                ),
                ChapterOutline(
                    number=2,
                    title="The Middle",
                    summary="Conflict arises",
                    key_events=["Event 3"],
                    characters_involved=["Alice"],
                    location="Lab",
                    emotional_arc="Excited to worried",
                    chapter_goal="Raise stakes",
                ),
            ],
        )

    @pytest.fixture
    def sample_state(self, sample_concept):
        """Create a sample state with previous chapters."""
        state = StoryState(concept=sample_concept)
        state.chapters = [
            Chapter(
                number=1,
                title="The Beginning",
                content="This is the first chapter content. " * 100,
                summary="Chapter 1 summary",
                status=ChapterStatus.COMPLETE,
            ),
        ]
        return state

    def test_build_story_bible(self, generator, sample_concept):
        """Test building the story bible context."""
        bible = generator._build_story_bible(sample_concept)

        assert sample_concept.title in bible
        assert sample_concept.logline in bible
        assert "testing" in bible
        assert "Test world" in bible
        assert "Alice" in bible
        assert "protagonist" in bible.lower()

    def test_build_story_bible_without_world(self, generator):
        """Test building story bible without world details."""
        concept = StoryConcept(
            title="No World",
            logline="Test",
            synopsis="Test",
        )
        bible = generator._build_story_bible(concept)

        assert "No World" in bible
        assert "WORLD:" not in bible

    def test_build_previous_summaries_first_chapter(self, generator, sample_state):
        """Test building previous summaries for first chapter."""
        result = generator._build_previous_summaries(sample_state, current_chapter=1)
        assert "first chapter" in result.lower()

    def test_build_previous_summaries_later_chapter(self, generator, sample_state):
        """Test building previous summaries for later chapters."""
        result = generator._build_previous_summaries(sample_state, current_chapter=2)

        assert "Chapter 1" in result
        assert "Chapter 1 summary" in result

    def test_build_previous_chapter_section_first_chapter(self, generator, sample_state):
        """Test building previous chapter section for first chapter."""
        result = generator._build_previous_chapter_section(sample_state, current_chapter=1)
        assert result == ""

    def test_build_previous_chapter_section_later_chapter(self, generator, sample_state):
        """Test building previous chapter section with content."""
        result = generator._build_previous_chapter_section(sample_state, current_chapter=2)

        assert "voice continuity" in result.lower()
        assert "first chapter content" in result

    def test_build_previous_chapter_section_truncates_long_content(self, generator, sample_state):
        """Test that long previous chapters are truncated."""
        # Make previous chapter very long
        sample_state.chapters[0].content = "word " * 5000

        result = generator._build_previous_chapter_section(sample_state, current_chapter=2)

        # Should be truncated to VOICE_CONTINUITY_WORDS
        words = result.split()
        # Allow some buffer for the header text
        assert len(words) < VOICE_CONTINUITY_WORDS + 50

    def test_clean_chapter_content_no_preamble(self, generator):
        """Test cleaning content without preamble."""
        content = "This is the story content.\n\nSecond paragraph."
        result = generator._clean_chapter_content(content)
        assert result == content.strip()

    def test_clean_chapter_content_removes_here_is(self, generator):
        """Test removing 'Here is' preamble."""
        content = "Here is the chapter:\n\nActual content starts here."
        result = generator._clean_chapter_content(content)
        assert not result.startswith("Here is")
        assert "Actual content starts here" in result

    def test_clean_chapter_content_removes_chapter_header(self, generator):
        """Test removing chapter headers."""
        content = "# Chapter 1: The Beginning\n\nActual content."
        result = generator._clean_chapter_content(content)
        assert "# Chapter" not in result
        assert "Actual content" in result

    def test_clean_chapter_content_removes_separator(self, generator):
        """Test removing separator lines."""
        content = "---\n\nActual content here."
        result = generator._clean_chapter_content(content)
        assert "---" not in result
        assert "Actual content" in result

    def test_clean_chapter_content_preserves_later_separators(self, generator):
        """Test that scene break separators later in content are preserved."""
        content = "Story begins here.\n\n* * *\n\nNew scene."
        result = generator._clean_chapter_content(content)
        assert "* * *" in result

    def test_generate_chapter_missing_outline(self, generator, sample_concept, sample_state):
        """Test that generating a chapter without outline raises error."""
        with pytest.raises(ValueError, match="outline not found"):
            generator.generate_chapter(
                chapter_num=10,
                concept=sample_concept,
                state=sample_state,
            )

    def test_generate_chapter_calls_client(self, generator, mock_client, sample_concept, sample_state):
        """Test that generate_chapter calls the client correctly."""
        mock_client.generate.side_effect = [
            "Generated chapter content.",  # Main generation
            "Chapter summary.",  # Summary generation
        ]

        chapter = generator.generate_chapter(
            chapter_num=2,
            concept=sample_concept,
            state=sample_state,
        )

        assert mock_client.generate.call_count == 2
        assert chapter.number == 2
        assert chapter.title == "The Middle"
        assert chapter.status == ChapterStatus.REVIEWING

    def test_revise_chapter(self, generator, mock_client, sample_concept, sample_state):
        """Test revising a chapter based on issues."""
        original_chapter = Chapter(
            number=1,
            title="Test",
            content="Original content",
            status=ChapterStatus.REVIEWING,
            revision_count=0,
        )

        mock_client.generate.side_effect = [
            "Revised chapter content.",
            "New summary.",
        ]

        revised = generator.revise_chapter(
            chapter=original_chapter,
            issues=["Fix timeline", "Improve dialogue"],
            concept=sample_concept,
            state=sample_state,
        )

        assert revised.content == "Revised chapter content."
        assert revised.revision_count == 1
        assert revised.status == ChapterStatus.REVIEWING


class TestConstants:
    """Tests for generator constants."""

    def test_voice_continuity_words_reasonable(self):
        """Test that VOICE_CONTINUITY_WORDS is a reasonable value."""
        assert 1000 <= VOICE_CONTINUITY_WORDS <= 5000

    def test_summary_content_limit_reasonable(self):
        """Test that SUMMARY_CONTENT_LIMIT is reasonable."""
        assert 5000 <= SUMMARY_CONTENT_LIMIT <= 50000

    def test_avoid_limits_reasonable(self):
        """Test that avoid limits are reasonable."""
        assert 10 <= MAX_AVOID_NAMES <= 100
        assert 10 <= MAX_AVOID_TITLES <= 50
        assert 3 <= MAX_AVOID_LOGLINES <= 20
