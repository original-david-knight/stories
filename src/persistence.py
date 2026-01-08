"""Persistence layer for saving and loading story state."""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from ebooklib import epub
from pydantic import BaseModel, Field

# Constants
MIN_CHAPTER_CONTENT_LENGTH = 100  # Minimum chars to consider chapter content valid

from .models import (
    AggregatedReview,
    Chapter,
    ChapterReview,
    ChapterStatus,
    GenerationLog,
    StoryConcept,
    StoryState,
    StoryStatus,
)


class GenerationHistory(BaseModel):
    """Tracks previously generated content to avoid repetition."""

    titles: list[str] = Field(default_factory=list)
    character_names: list[str] = Field(default_factory=list)
    loglines: list[str] = Field(default_factory=list)
    rejected_loglines: list[str] = Field(default_factory=list)
    max_items: int = Field(default=50)

    def add_story(self, concept: StoryConcept) -> None:
        """Add a story's elements to history."""
        if concept.title and concept.title not in self.titles:
            self.titles.append(concept.title)
        if concept.logline and concept.logline not in self.loglines:
            self.loglines.append(concept.logline)
        for char in concept.characters:
            if char.name and char.name not in self.character_names:
                self.character_names.append(char.name)
        self._trim()

    def add_rejected(self, concept: StoryConcept) -> None:
        """Add a rejected concept's logline to history."""
        if concept.logline and concept.logline not in self.rejected_loglines:
            self.rejected_loglines.append(concept.logline)
        self._trim()

    def _trim(self) -> None:
        """Keep lists at max size, removing oldest entries."""
        if len(self.titles) > self.max_items:
            self.titles = self.titles[-self.max_items:]
        if len(self.loglines) > self.max_items:
            self.loglines = self.loglines[-self.max_items:]
        if len(self.character_names) > self.max_items * 3:
            self.character_names = self.character_names[-(self.max_items * 3):]
        if len(self.rejected_loglines) > self.max_items:
            self.rejected_loglines = self.rejected_loglines[-self.max_items:]


class StoryPersistence:
    """Handles saving and loading story data to disk."""

    def __init__(self, base_path: Path):
        """Initialize persistence with base storage path.

        Args:
            base_path: Base directory for storing stories
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)
        self._history_file = self.base_path / "history.json"

    def load_history(self) -> GenerationHistory:
        """Load generation history from disk.

        Returns:
            GenerationHistory with previously used titles/names
        """
        if not self._history_file.exists():
            return GenerationHistory()

        try:
            with open(self._history_file) as f:
                data = json.load(f)
            return GenerationHistory.model_validate(data)
        except (json.JSONDecodeError, ValueError):
            return GenerationHistory()

    def save_history(self, history: GenerationHistory) -> None:
        """Save generation history to disk.

        Args:
            history: GenerationHistory to save
        """
        with open(self._history_file, "w") as f:
            json.dump(history.model_dump(mode="json"), f, indent=2)

    def add_to_history(self, concept: StoryConcept) -> None:
        """Add a story concept to the history.

        Args:
            concept: StoryConcept to record
        """
        history = self.load_history()
        history.add_story(concept)
        self.save_history(history)

    def add_rejected_concept(self, concept: StoryConcept) -> None:
        """Add a rejected concept to the history.

        Args:
            concept: StoryConcept that was rejected by the user
        """
        history = self.load_history()
        history.add_rejected(concept)
        self.save_history(history)

    def get_story_path(self, story_id: str) -> Path:
        """Get the path for a specific story."""
        return self.base_path / story_id

    def list_stories(self) -> list[dict]:
        """List all saved stories with basic info.

        Returns:
            List of dicts with story id, title, status, and updated_at
        """
        stories = []
        for story_dir in self.base_path.iterdir():
            if story_dir.is_dir():
                state_file = story_dir / "state.json"
                if state_file.exists():
                    try:
                        state = self.load_state(story_dir.name)
                        if state and state.concept:
                            stories.append({
                                "id": story_dir.name,
                                "title": state.concept.title,
                                "status": state.status.value,
                                "chapters_complete": len(state.get_completed_chapters()),
                                "total_chapters": len(state.concept.chapter_outlines),
                                "updated_at": state.updated_at.isoformat(),
                            })
                    except (json.JSONDecodeError, ValueError, KeyError):
                        # Skip corrupted story files - don't break listing
                        continue

        return sorted(stories, key=lambda s: s["updated_at"], reverse=True)

    def create_story(self, concept: StoryConcept) -> str:
        """Create a new story directory and save initial state.

        Args:
            concept: The story concept

        Returns:
            Story ID (directory name)
        """
        story_id = concept.id
        story_path = self.get_story_path(story_id)
        story_path.mkdir(parents=True, exist_ok=True)

        # Create subdirectories
        (story_path / "chapters").mkdir(exist_ok=True)

        # Save concept
        self.save_concept(story_id, concept)

        # Create initial state
        state = StoryState(
            concept=concept,
            status=StoryStatus.CONCEPT,
        )
        self.save_state(story_id, state)

        return story_id

    def save_concept(self, story_id: str, concept: StoryConcept) -> None:
        """Save the story concept.

        Args:
            story_id: Story identifier
            concept: StoryConcept to save
        """
        story_path = self.get_story_path(story_id)
        story_path.mkdir(parents=True, exist_ok=True)

        concept_file = story_path / "concept.json"
        with open(concept_file, "w") as f:
            json.dump(concept.model_dump(mode="json"), f, indent=2, default=str)

    def load_concept(self, story_id: str) -> Optional[StoryConcept]:
        """Load the story concept.

        Args:
            story_id: Story identifier

        Returns:
            StoryConcept or None if not found
        """
        concept_file = self.get_story_path(story_id) / "concept.json"
        if not concept_file.exists():
            return None

        with open(concept_file) as f:
            data = json.load(f)

        return StoryConcept.model_validate(data)

    def save_state(self, story_id: str, state: StoryState) -> None:
        """Save the current story state.

        Args:
            story_id: Story identifier
            state: StoryState to save
        """
        story_path = self.get_story_path(story_id)
        story_path.mkdir(parents=True, exist_ok=True)

        state.updated_at = datetime.now()

        state_file = story_path / "state.json"
        with open(state_file, "w") as f:
            json.dump(state.model_dump(mode="json"), f, indent=2, default=str)

    def load_state(self, story_id: str) -> Optional[StoryState]:
        """Load the story state.

        Args:
            story_id: Story identifier

        Returns:
            StoryState or None if not found
        """
        state_file = self.get_story_path(story_id) / "state.json"
        if not state_file.exists():
            return None

        with open(state_file) as f:
            data = json.load(f)

        state = StoryState.model_validate(data)

        # Ensure chapter content is loaded from individual files
        # This handles cases where state.json might be out of sync
        state = self._load_chapter_content(story_id, state)

        return state

    def _load_chapter_content(self, story_id: str, state: StoryState) -> StoryState:
        """Load chapter content from individual chapter files.

        Ensures all chapters have their full content loaded,
        reading from chapter meta files if content is missing.

        Args:
            story_id: Story identifier
            state: Current story state

        Returns:
            Updated StoryState with all chapter content loaded
        """
        chapters_path = self.get_story_path(story_id) / "chapters"
        if not chapters_path.exists():
            return state

        for i, chapter in enumerate(state.chapters):
            # If chapter has no content or very short content, try to load from file
            if not chapter.content or len(chapter.content) < MIN_CHAPTER_CONTENT_LENGTH:
                meta_file = chapters_path / f"{chapter.number:02d}_meta.json"
                if meta_file.exists():
                    with open(meta_file) as f:
                        chapter_data = json.load(f)
                    loaded_chapter = Chapter.model_validate(chapter_data)
                    state.chapters[i] = loaded_chapter

        return state

    def save_chapter(self, story_id: str, chapter: Chapter) -> None:
        """Save a chapter to disk.

        Args:
            story_id: Story identifier
            chapter: Chapter to save
        """
        chapters_path = self.get_story_path(story_id) / "chapters"
        chapters_path.mkdir(parents=True, exist_ok=True)

        # Save chapter content as markdown
        chapter_file = chapters_path / f"{chapter.number:02d}_{self._slugify(chapter.title)}.md"
        with open(chapter_file, "w") as f:
            f.write(f"# Chapter {chapter.number}: {chapter.title}\n\n")
            f.write(chapter.content)

        # Save chapter metadata as JSON
        meta_file = chapters_path / f"{chapter.number:02d}_meta.json"
        with open(meta_file, "w") as f:
            json.dump(chapter.model_dump(mode="json"), f, indent=2, default=str)

    def save_review(self, story_id: str, review: ChapterReview) -> None:
        """Save a chapter review.

        Args:
            story_id: Story identifier
            review: ChapterReview to save
        """
        chapters_path = self.get_story_path(story_id) / "chapters"
        chapters_path.mkdir(parents=True, exist_ok=True)

        review_file = chapters_path / f"{review.chapter_number:02d}_review.json"
        with open(review_file, "w") as f:
            json.dump(review.model_dump(mode="json"), f, indent=2, default=str)

    def save_aggregated_review(self, story_id: str, review: AggregatedReview) -> None:
        """Save an aggregated review from multiple reviewers.

        Args:
            story_id: Story identifier
            review: AggregatedReview to save
        """
        story_path = self.get_story_path(story_id)
        story_path.mkdir(parents=True, exist_ok=True)

        if review.content_type == "chapter" and review.chapter_number:
            # Save in chapters directory for chapter reviews
            chapters_path = story_path / "chapters"
            chapters_path.mkdir(parents=True, exist_ok=True)
            filename = f"{review.chapter_number:02d}_aggregated_review.json"
            review_file = chapters_path / filename
        else:
            # Save in story root for concept/outline reviews
            filename = f"{review.content_type}_review.json"
            review_file = story_path / filename

        with open(review_file, "w") as f:
            json.dump(review.model_dump(mode="json"), f, indent=2, default=str)

    def save_logs(self, story_id: str, logs: list[GenerationLog]) -> None:
        """Save generation logs.

        Args:
            story_id: Story identifier
            logs: List of GenerationLog entries
        """
        story_path = self.get_story_path(story_id)
        log_file = story_path / "generation_log.json"

        # Append to existing logs
        existing_logs = []
        if log_file.exists():
            with open(log_file) as f:
                existing_logs = json.load(f)

        all_logs = existing_logs + [log.model_dump(mode="json") for log in logs]

        with open(log_file, "w") as f:
            json.dump(all_logs, f, indent=2, default=str)

    def export_story(self, story_id: str, format: str = "markdown") -> str:
        """Export the complete story to a single file.

        Args:
            story_id: Story identifier
            format: Export format ("markdown" or "text")

        Returns:
            Path to exported file
        """
        state = self.load_state(story_id)
        if not state or not state.concept:
            raise ValueError(f"Story {story_id} not found")

        story_path = self.get_story_path(story_id)
        export_path = story_path / f"{self._slugify(state.concept.title)}.md"

        with open(export_path, "w") as f:
            # Title page
            f.write(f"# {state.concept.title}\n\n")
            f.write(f"*{state.concept.logline}*\n\n")
            f.write("---\n\n")

            # Chapters
            for chapter in sorted(state.chapters, key=lambda c: c.number):
                if chapter.status == ChapterStatus.COMPLETE:
                    f.write(f"## Chapter {chapter.number}: {chapter.title}\n\n")
                    f.write(chapter.content)
                    f.write("\n\n---\n\n")

        return str(export_path)

    def export_epub(self, story_id: str) -> str:
        """Export the complete story to an EPUB file.

        Args:
            story_id: Story identifier

        Returns:
            Path to exported EPUB file
        """
        state = self.load_state(story_id)
        if not state or not state.concept:
            raise ValueError(f"Story {story_id} not found")

        completed_chapters = [
            ch for ch in sorted(state.chapters, key=lambda c: c.number)
            if ch.status == ChapterStatus.COMPLETE
        ]
        if not completed_chapters:
            raise ValueError(f"No completed chapters to export for story {story_id}")

        concept = state.concept
        story_path = self.get_story_path(story_id)

        book = epub.EpubBook()
        book.set_identifier(story_id)
        book.set_title(concept.title)
        book.set_language("en")
        book.add_author("AI Story Generator")

        book.add_metadata("DC", "description", concept.logline)

        # Add cover image if it exists
        cover_path = story_path / "cover.png"
        if cover_path.exists():
            with open(cover_path, "rb") as f:
                cover_data = f.read()
            book.set_cover("cover.png", cover_data)

        style = """
body { font-family: Georgia, serif; line-height: 1.6; margin: 5%; }
h1 { text-align: center; margin-bottom: 2em; }
h2 { text-align: center; margin-top: 3em; margin-bottom: 1em; }
p { text-indent: 1.5em; margin: 0.5em 0; }
.logline { font-style: italic; text-align: center; margin: 2em 0; }
"""
        css = epub.EpubItem(
            uid="style",
            file_name="style/main.css",
            media_type="text/css",
            content=style,
        )
        book.add_item(css)

        title_content = f"""
<html>
<head><link rel="stylesheet" href="style/main.css" type="text/css"/></head>
<body>
<h1>{concept.title}</h1>
<p class="logline">{concept.logline}</p>
</body>
</html>
"""
        title_page = epub.EpubHtml(title="Title Page", file_name="title.xhtml")
        title_page.content = title_content
        title_page.add_item(css)
        book.add_item(title_page)

        chapter_items = []
        for chapter in completed_chapters:
            paragraphs = chapter.content.split("\n\n")
            html_paragraphs = "\n".join(f"<p>{p.strip()}</p>" for p in paragraphs if p.strip())

            chapter_content = f"""
<html>
<head><link rel="stylesheet" href="style/main.css" type="text/css"/></head>
<body>
<h2>Chapter {chapter.number}: {chapter.title}</h2>
{html_paragraphs}
</body>
</html>
"""
            epub_chapter = epub.EpubHtml(
                title=f"Chapter {chapter.number}: {chapter.title}",
                file_name=f"chapter_{chapter.number:02d}.xhtml",
            )
            epub_chapter.content = chapter_content
            epub_chapter.add_item(css)
            book.add_item(epub_chapter)
            chapter_items.append(epub_chapter)

        book.toc = [title_page] + chapter_items
        book.spine = ["nav", title_page] + chapter_items

        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())

        export_path = story_path / f"{self._slugify(concept.title)}.epub"
        epub.write_epub(str(export_path), book)

        return str(export_path)

    def _slugify(self, text: str) -> str:
        """Convert text to a safe filename slug."""
        # Replace spaces and special chars with underscores
        slug = "".join(c if c.isalnum() else "_" for c in text.lower())
        # Remove multiple underscores
        while "__" in slug:
            slug = slug.replace("__", "_")
        return slug.strip("_")[:50]
