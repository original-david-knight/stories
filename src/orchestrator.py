"""Story orchestrator - main controller for the generation workflow."""

from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from .gemini_client import GeminiClient
from .generators.concept import ConceptGenerator
from .generators.chapter import ChapterGenerator
from .models import (
    AggregatedReview,
    Chapter,
    ChapterStatus,
    Severity,
    StoryConcept,
    StoryState,
    StoryStatus,
)
from .persistence import StoryPersistence
from .reviewers import (
    ContentType,
    CorrectnessReviewer,
    ReviewContext,
    ReviewerRegistry,
    ReviewResult,
    ScientificAccuracyReviewer,
    StyleReviewer,
)


class StoryOrchestrator:
    """Main controller coordinating the full story generation workflow."""

    def __init__(
        self,
        client: GeminiClient,
        storage_path: Path,
        max_revisions: int = 7,
        on_progress: Optional[Callable[[str], None]] = None,
        reviewer_registry: Optional[ReviewerRegistry] = None,
    ):
        """Initialize the orchestrator.

        Args:
            client: Configured GeminiClient
            storage_path: Path for story storage
            max_revisions: Maximum revision attempts per content piece
            on_progress: Optional callback for progress updates
            reviewer_registry: Optional pre-configured registry (default: all reviewers)
        """
        self.client = client
        self.persistence = StoryPersistence(storage_path)
        self.concept_generator = ConceptGenerator(client)
        self.chapter_generator = ChapterGenerator(client)
        self.max_revisions = max_revisions
        self.on_progress = on_progress or (lambda msg: None)

        if reviewer_registry:
            self.reviewer_registry = reviewer_registry
        else:
            self.reviewer_registry = self._create_default_registry()

    def _create_default_registry(self) -> ReviewerRegistry:
        """Create the default reviewer registry with all reviewers."""
        registry = ReviewerRegistry()
        registry.register(CorrectnessReviewer(self.client))
        registry.register(StyleReviewer(self.client))
        registry.register(ScientificAccuracyReviewer(self.client))
        return registry

    def generate_concept(
        self,
        themes: Optional[list[str]] = None,
        review: bool = True,
    ) -> StoryConcept:
        """Generate a single story concept.

        Args:
            themes: Optional themes to incorporate
            review: Whether to review and refine the concept

        Returns:
            A single StoryConcept
        """
        self.on_progress("Generating story concept...")

        # Load history to avoid repetition
        history = self.persistence.load_history()

        concepts = self.concept_generator.generate_concepts(
            count=1,
            themes=themes,
            avoid_titles=history.titles if history.titles else None,
            avoid_loglines=history.loglines if history.loglines else None,
            rejected_loglines=history.rejected_loglines if history.rejected_loglines else None,
        )

        concept = concepts[0]

        if review:
            self.on_progress("Reviewing concept...")
            concept = self._review_and_revise_concept(concept)

        return concept

    def reject_concept(self, concept: StoryConcept) -> None:
        """Mark a concept as rejected to avoid generating similar ones.

        Args:
            concept: The rejected concept
        """
        self.persistence.add_rejected_concept(concept)
        self.on_progress("Concept rejected, will avoid similar ideas")

    def generate_concepts(
        self,
        count: int = 3,
        themes: Optional[list[str]] = None,
        review: bool = True,
    ) -> list[StoryConcept]:
        """Generate story concepts for user selection.

        Args:
            count: Number of concepts to generate
            themes: Optional themes to incorporate
            review: Whether to review and refine concepts

        Returns:
            List of StoryConcept objects
        """
        self.on_progress(f"Generating {count} story concepts...")

        # Load history to avoid repetition
        history = self.persistence.load_history()

        concepts = self.concept_generator.generate_concepts(
            count=count,
            themes=themes,
            avoid_titles=history.titles if history.titles else None,
            avoid_loglines=history.loglines if history.loglines else None,
            rejected_loglines=history.rejected_loglines if history.rejected_loglines else None,
        )

        if review:
            reviewed_concepts = []
            for i, concept in enumerate(concepts):
                self.on_progress(f"Reviewing concept {i + 1}/{count}...")
                concept = self._review_and_revise_concept(concept)
                reviewed_concepts.append(concept)
            return reviewed_concepts

        return concepts

    def create_story(
        self,
        concept: StoryConcept,
        num_chapters: int = 12,
        review: bool = True,
    ) -> str:
        """Create a story from a selected concept.

        Args:
            concept: The chosen story concept
            num_chapters: Target number of chapters
            review: Whether to review and refine the outline

        Returns:
            Story ID
        """
        self.on_progress("Expanding concept into full outline...")
        concept = self.concept_generator.expand_to_outline(concept, num_chapters)

        if review:
            self.on_progress("Reviewing outline...")
            concept = self._review_and_revise_outline(concept)

        # Create the story in persistence
        story_id = self.persistence.create_story(concept)

        # Add to history to avoid repetition in future generations
        self.persistence.add_to_history(concept)

        self.on_progress(f"Story created with ID: {story_id}")
        self.on_progress(f"Outline has {len(concept.chapter_outlines)} chapters")

        return story_id

    def generate_chapter(
        self,
        story_id: str,
        chapter_num: Optional[int] = None,
    ) -> Chapter:
        """Generate a single chapter.

        Args:
            story_id: Story identifier
            chapter_num: Chapter to generate (default: next incomplete)

        Returns:
            Generated Chapter
        """
        state = self.persistence.load_state(story_id)
        if not state or not state.concept:
            raise ValueError(f"Story {story_id} not found")

        concept = state.concept

        if chapter_num is None:
            chapter_num = self._get_next_chapter(state)

        if chapter_num > len(concept.chapter_outlines):
            raise ValueError(f"No outline for chapter {chapter_num}")

        self.on_progress(f"Generating Chapter {chapter_num}: {concept.chapter_outlines[chapter_num-1].title}")

        chapter = self.chapter_generator.generate_chapter(
            chapter_num=chapter_num,
            concept=concept,
            state=state,
        )

        chapter = self._review_and_revise_chapter(story_id, chapter, concept, state)

        chapter.status = ChapterStatus.COMPLETE
        chapter.finalized_at = datetime.now()

        self._update_state_with_chapter(story_id, state, chapter)

        self.on_progress(f"Chapter {chapter_num} complete ({chapter.word_count} words)")

        return chapter

    def generate_all_chapters(self, story_id: str) -> list[Chapter]:
        """Generate all remaining chapters.

        Args:
            story_id: Story identifier

        Returns:
            List of all generated chapters
        """
        state = self.persistence.load_state(story_id)
        if not state or not state.concept:
            raise ValueError(f"Story {story_id} not found")

        chapters = []
        total = len(state.concept.chapter_outlines)

        while True:
            next_chapter = self._get_next_chapter(state)
            if next_chapter > total:
                break

            self.on_progress(f"Progress: {len(state.get_completed_chapters())}/{total} chapters")

            chapter = self.generate_chapter(story_id, next_chapter)
            chapters.append(chapter)

            state = self.persistence.load_state(story_id)

        state.status = StoryStatus.COMPLETE
        self.persistence.save_state(story_id, state)

        self.on_progress("Story complete!")

        return chapters

    def resume_story(self, story_id: str) -> Optional[StoryState]:
        """Resume an in-progress story.

        Args:
            story_id: Story identifier

        Returns:
            Current StoryState or None
        """
        state = self.persistence.load_state(story_id)
        if state:
            completed = len(state.get_completed_chapters())
            total = len(state.concept.chapter_outlines) if state.concept else 0
            self.on_progress(f"Resumed: {completed}/{total} chapters complete")
        return state

    def export_story(self, story_id: str) -> str:
        """Export the story to a file.

        Args:
            story_id: Story identifier

        Returns:
            Path to exported file
        """
        path = self.persistence.export_story(story_id)
        self.on_progress(f"Story exported to: {path}")
        return path

    def export_epub(self, story_id: str) -> str:
        """Export the story to an EPUB file.

        Args:
            story_id: Story identifier

        Returns:
            Path to exported EPUB file
        """
        path = self.persistence.export_epub(story_id)
        self.on_progress(f"Story exported to: {path}")
        return path

    def generate_cover(
        self,
        story_id: str,
        style: str = "cinematic",
    ) -> Path:
        """Generate a book cover image for a story using Nano Banana 2.

        Args:
            story_id: Story identifier
            style: Visual style (cinematic, illustrated, minimalist, retro)

        Returns:
            Path to the generated cover image
        """
        state = self.persistence.load_state(story_id)
        if not state or not state.concept:
            raise ValueError(f"Story {story_id} not found")

        concept = state.concept

        self.on_progress("Building cover prompt from story concept...")

        # Build a detailed prompt based on story elements
        prompt = self._build_cover_prompt(concept, style)

        # Determine output path
        story_path = self.persistence.get_story_path(story_id)
        output_path = story_path / "cover.png"

        self.on_progress("Generating cover image with Nano Banana 2...")
        self.client.generate_image(
            prompt=prompt,
            output_path=output_path,
            aspect_ratio="2:3",  # Standard book cover ratio
        )

        self.on_progress(f"Cover saved to: {output_path}")
        return output_path

    def _build_cover_prompt(self, concept: StoryConcept, style: str) -> str:
        """Build a detailed image generation prompt for the cover.

        Args:
            concept: Story concept
            style: Visual style

        Returns:
            Prompt string for image generation
        """
        style_descriptions = {
            "cinematic": "cinematic movie poster style, dramatic lighting, photorealistic",
            "illustrated": "digital illustration, vibrant colors, detailed artwork",
            "minimalist": "minimalist design, bold typography, simple shapes, elegant",
            "retro": "vintage sci-fi book cover style, 1970s aesthetic, bold colors",
        }

        style_desc = style_descriptions.get(style, style_descriptions["cinematic"])

        # Extract key visual elements from the concept
        world_desc = ""
        if concept.world:
            world_desc = f"Set in {concept.world.setting}, {concept.world.time_period}. "

        # Build character descriptions (focus on protagonist)
        character_desc = ""
        protagonist = next((c for c in concept.characters if "protagonist" in c.role.lower()), None)
        if protagonist:
            character_desc = f"Featuring {protagonist.description}. "

        # Get themes for mood
        themes_str = ", ".join(concept.themes[:3]) if concept.themes else ""
        themes_desc = f"Themes of {themes_str}. " if themes_str else ""

        prompt = (
            f"Science fiction book cover for '{concept.title}'. "
            f"{concept.logline} "
            f"{world_desc}"
            f"{character_desc}"
            f"{themes_desc}"
            f"Style: {style_desc}. "
            f"No text or typography on the image. "
            f"Professional quality, suitable for a published novel."
        )

        return prompt

    def list_stories(self) -> list[dict]:
        """List all saved stories.

        Returns:
            List of story info dicts
        """
        return self.persistence.list_stories()

    def get_story_state(self, story_id: str) -> Optional[StoryState]:
        """Get the current state of a story.

        Args:
            story_id: Story identifier

        Returns:
            StoryState or None
        """
        return self.persistence.load_state(story_id)

    def generate_characters(
        self,
        concept: StoryConcept,
        num_characters: int = 4,
    ) -> StoryConcept:
        """Generate major characters for a concept.

        Args:
            concept: The story concept
            num_characters: Number of characters to generate

        Returns:
            Concept with characters added
        """
        self.on_progress(f"Generating {num_characters} major characters...")

        # Load history to avoid repeating character names
        history = self.persistence.load_history()

        characters = self.concept_generator.generate_characters(
            concept=concept,
            num_characters=num_characters,
            avoid_names=history.character_names if history.character_names else None,
        )
        concept.characters = characters
        self.on_progress(f"Generated {len(characters)} characters")
        return concept

    def regenerate_character(
        self,
        concept: StoryConcept,
        character_index: int,
        user_feedback: Optional[str] = None,
    ) -> StoryConcept:
        """Regenerate a specific character.

        Args:
            concept: The story concept
            character_index: Index of the character to regenerate
            user_feedback: Optional feedback for how to improve the character

        Returns:
            Concept with the character replaced
        """
        old_name = concept.characters[character_index].name
        if user_feedback:
            self.on_progress(f"Revising character: {old_name}...")
        else:
            self.on_progress(f"Regenerating character: {old_name}...")
        new_character = self.concept_generator.regenerate_character(
            concept, character_index, user_feedback
        )
        concept.characters[character_index] = new_character
        self.on_progress(f"New character: {new_character.name}")
        return concept

    def revise_concept_with_user_feedback(
        self,
        concept: StoryConcept,
        user_feedback: str,
    ) -> StoryConcept:
        """Revise a concept based on user feedback.

        Args:
            concept: Concept to revise
            user_feedback: Free-form feedback from the user

        Returns:
            Revised concept
        """
        self.on_progress("Revising concept based on your feedback...")
        concept = self.concept_generator.revise_concept_with_user_feedback(
            concept, user_feedback
        )
        self.on_progress("Concept revised!")
        return concept

    def _review_and_revise_concept(self, concept: StoryConcept) -> StoryConcept:
        """Review a concept and revise if needed.

        Args:
            concept: Concept to review

        Returns:
            Reviewed (and possibly revised) concept
        """
        revision_count = 0

        while revision_count < self.max_revisions:
            context = ReviewContext(
                content_type=ContentType.CONCEPT,
                concept=concept,
                content=f"{concept.title}\n{concept.logline}\n{concept.synopsis}",
                iteration=revision_count,
            )

            results = self.reviewer_registry.run_all_reviews(context)

            for result in results:
                status = "PASS" if result.passed else "FAIL"
                self.on_progress(f"  {result.reviewer_name}: {status}")
                if not result.passed:
                    high_issues = result.get_high_severity_issues()
                    self.on_progress(f"    HIGH severity issues: {len(high_issues)}")

            if self.reviewer_registry.all_passed(results):
                self.on_progress("Concept approved!")
                break

            revision_count += 1
            if revision_count >= self.max_revisions:
                self.on_progress(f"Max revisions reached for concept")
                break

            guidance = self.reviewer_registry.get_all_revision_guidance(results)
            self.on_progress(f"Revising concept (attempt {revision_count})...")
            concept = self.concept_generator.revise_concept(concept, guidance)

        return concept

    def _review_and_revise_outline(self, concept: StoryConcept) -> StoryConcept:
        """Review an outline and revise if needed.

        Args:
            concept: Concept with outline to review

        Returns:
            Concept with reviewed (and possibly revised) outline
        """
        revision_count = 0

        while revision_count < self.max_revisions:
            context = ReviewContext(
                content_type=ContentType.OUTLINE,
                concept=concept,
                content=self._format_outline_for_review(concept),
                iteration=revision_count,
            )

            results = self.reviewer_registry.run_all_reviews(context)

            for result in results:
                status = "PASS" if result.passed else "FAIL"
                self.on_progress(f"  {result.reviewer_name}: {status}")
                if not result.passed:
                    high_issues = result.get_high_severity_issues()
                    self.on_progress(f"    HIGH severity issues: {len(high_issues)}")

            if self.reviewer_registry.all_passed(results):
                self.on_progress("Outline approved!")
                break

            revision_count += 1
            if revision_count >= self.max_revisions:
                self.on_progress(f"Max revisions reached for outline")
                break

            guidance = self.reviewer_registry.get_all_revision_guidance(results)
            self.on_progress(f"Revising outline (attempt {revision_count})...")
            concept = self.concept_generator.revise_outline(concept, guidance)

        return concept

    def _review_and_revise_chapter(
        self,
        story_id: str,
        chapter: Chapter,
        concept: StoryConcept,
        state: StoryState,
    ) -> Chapter:
        """Review a chapter with multiple reviewers and revise if needed.

        Args:
            story_id: Story identifier
            chapter: Chapter to review
            concept: Story concept
            state: Current story state

        Returns:
            Reviewed (and possibly revised) chapter
        """
        revision_count = 0

        while revision_count < self.max_revisions:
            self.on_progress(f"Reviewing chapter {chapter.number}...")

            context = ReviewContext(
                content_type=ContentType.CHAPTER,
                concept=concept,
                state=state,
                chapter=chapter,
                chapter_outline=concept.chapter_outlines[chapter.number - 1],
                content=chapter.content,
                iteration=revision_count,
            )

            results = self.reviewer_registry.run_all_reviews(context)

            all_passed = True
            for result in results:
                status = "PASS" if result.passed else "FAIL"
                self.on_progress(f"  {result.reviewer_name}: {status}")
                if not result.passed:
                    all_passed = False
                    high_issues = result.get_high_severity_issues()
                    self.on_progress(f"    HIGH severity issues: {len(high_issues)}")

            aggregated = self._aggregate_results(results, chapter.number)
            self.persistence.save_aggregated_review(story_id, aggregated)

            if all_passed:
                self.on_progress("Chapter approved by all reviewers!")
                break

            revision_count += 1
            chapter.revision_count = revision_count

            if revision_count >= self.max_revisions:
                self.on_progress(f"Max revisions ({self.max_revisions}) reached")
                break

            guidance = self.reviewer_registry.get_all_revision_guidance(results)
            self.on_progress(f"Revising chapter (attempt {revision_count})...")

            chapter = self.chapter_generator.revise_chapter(
                chapter=chapter,
                issues=guidance,
                concept=concept,
                state=state,
            )

        return chapter

    def _aggregate_results(
        self,
        results: list[ReviewResult],
        chapter_number: int
    ) -> AggregatedReview:
        """Aggregate results from multiple reviewers."""
        high_issues = []
        medium_issues = []
        low_issues = []
        reviewer_results = {}

        for result in results:
            reviewer_results[result.reviewer_name] = result.passed
            for issue in result.issues:
                if issue.severity == Severity.HIGH:
                    high_issues.append(issue)
                elif issue.severity == Severity.MEDIUM:
                    medium_issues.append(issue)
                else:
                    low_issues.append(issue)

        all_passed = all(r.passed for r in results)

        return AggregatedReview(
            content_type="chapter",
            chapter_number=chapter_number,
            reviewer_results=reviewer_results,
            high_severity_issues=high_issues,
            medium_severity_issues=medium_issues,
            low_severity_issues=low_issues,
            all_passed=all_passed,
            revision_needed=not all_passed,
        )

    def _format_outline_for_review(self, concept: StoryConcept) -> str:
        """Format outline content for review."""
        parts = [f"Title: {concept.title}", f"Logline: {concept.logline}"]

        if concept.characters:
            parts.append("\nCharacters:")
            for char in concept.characters:
                parts.append(f"  - {char.name}: {char.description}")

        parts.append("\nChapter Outline:")
        for ch in concept.chapter_outlines:
            parts.append(f"  Chapter {ch.number}: {ch.title}")
            parts.append(f"    {ch.summary}")

        return "\n".join(parts)

    def _get_next_chapter(self, state: StoryState) -> int:
        """Get the next chapter number to generate.

        Args:
            state: Current story state

        Returns:
            Next chapter number (1-indexed)
        """
        completed_nums = {ch.number for ch in state.chapters if ch.status == ChapterStatus.COMPLETE}

        for i in range(1, len(state.concept.chapter_outlines) + 2):
            if i not in completed_nums:
                return i

        return len(state.concept.chapter_outlines) + 1

    def _update_state_with_chapter(
        self,
        story_id: str,
        state: StoryState,
        chapter: Chapter,
    ) -> None:
        """Update state with a new or revised chapter.

        Args:
            story_id: Story identifier
            state: Current story state
            chapter: Chapter to add/update
        """
        existing_idx = next(
            (i for i, ch in enumerate(state.chapters) if ch.number == chapter.number),
            None,
        )

        if existing_idx is not None:
            state.chapters[existing_idx] = chapter
        else:
            state.chapters.append(chapter)
            state.chapters.sort(key=lambda c: c.number)

        state.current_chapter = chapter.number
        state.status = StoryStatus.WRITING

        self.persistence.save_chapter(story_id, chapter)
        self.persistence.save_state(story_id, state)
        self.persistence.save_logs(story_id, self.client.get_logs())
        self.client.clear_logs()
