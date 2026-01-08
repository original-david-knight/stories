"""Chapter generation with context awareness."""

from datetime import datetime
from typing import Optional

from ..gemini_client import GeminiClient
from ..models import (
    Chapter,
    ChapterOutline,
    ChapterStatus,
    StoryConcept,
    StoryState,
)


CHAPTER_SYSTEM_INSTRUCTION = """You are an acclaimed science fiction author known for vivid prose,
compelling characters, and thought-provoking narratives. Your writing balances action,
dialogue, and introspection. You show rather than tell, use strong sensory details,
and create memorable scenes that advance both plot and character development.

Write in third-person limited perspective unless otherwise specified.
Each chapter should have a clear beginning hook, rising tension, and an ending that
compels the reader to continue."""


CHAPTER_GENERATION_PROMPT = """Write Chapter {chapter_num} of "{title}".

=== STORY BIBLE ===
{story_bible}

=== PREVIOUS CHAPTER SUMMARIES ===
{previous_summaries}

{previous_chapter_section}

=== THIS CHAPTER'S OUTLINE ===
Title: {chapter_title}
Summary: {chapter_summary}
Key Events: {key_events}
Characters: {characters}
Location: {location}
Emotional Arc: {emotional_arc}
Chapter Goal: {chapter_goal}

=== WRITING REQUIREMENTS ===
- Target length: {target_words} words (minimum 3000, aim for 4000-5000)
- Open with a compelling hook that draws the reader in
- Include vivid sensory details that bring the world to life
- Balance dialogue, action, and internal reflection
- Maintain consistent character voices established in previous chapters
- End with tension, revelation, or emotional resonance that propels the story forward
- Use scene breaks (marked with "* * *") where appropriate
- Show character emotions through action and dialogue, not exposition

Write the complete chapter now. Begin directly with the chapter content, no preamble."""


CHAPTER_SUMMARY_PROMPT = """Summarize this chapter in 2-3 sentences, focusing on:
1. Key plot developments
2. Character changes or revelations
3. Important information revealed

Chapter:
{chapter_content}

Provide only the summary, no additional text."""


class ChapterGenerator:
    """Generates chapters with full story context."""

    def __init__(self, client: GeminiClient):
        """Initialize with a Gemini client.

        Args:
            client: Configured GeminiClient instance
        """
        self.client = client

    def generate_chapter(
        self,
        chapter_num: int,
        concept: StoryConcept,
        state: StoryState,
        target_words: int = 4000,
    ) -> Chapter:
        """Generate a single chapter with full context.

        Args:
            chapter_num: Chapter number to generate (1-indexed)
            concept: The story concept with outlines
            state: Current story state with previous chapters
            target_words: Target word count

        Returns:
            Generated Chapter object
        """
        # Get the chapter outline
        if chapter_num > len(concept.chapter_outlines):
            raise ValueError(
                f"Chapter {chapter_num} outline not found. "
                f"Only {len(concept.chapter_outlines)} chapters outlined."
            )

        outline = concept.chapter_outlines[chapter_num - 1]

        # Build the story bible (compressed world/character info)
        story_bible = self._build_story_bible(concept)

        # Get previous chapter summaries
        previous_summaries = self._build_previous_summaries(state, chapter_num)

        # Get previous chapter text (last 1-2 chapters for voice continuity)
        previous_chapter_section = self._build_previous_chapter_section(state, chapter_num)

        prompt = CHAPTER_GENERATION_PROMPT.format(
            chapter_num=chapter_num,
            title=concept.title,
            story_bible=story_bible,
            previous_summaries=previous_summaries,
            previous_chapter_section=previous_chapter_section,
            chapter_title=outline.title,
            chapter_summary=outline.summary,
            key_events=", ".join(outline.key_events),
            characters=", ".join(outline.characters_involved),
            location=outline.location,
            emotional_arc=outline.emotional_arc,
            chapter_goal=outline.chapter_goal,
            target_words=target_words,
        )

        content = self.client.generate(
            prompt,
            system_instruction=CHAPTER_SYSTEM_INSTRUCTION,
            temperature=0.85,  # Creative but consistent
        )

        # Clean up any potential preamble
        content = self._clean_chapter_content(content)

        # Generate summary
        summary = self._generate_summary(content)

        return Chapter(
            number=chapter_num,
            title=outline.title,
            content=content,
            word_count=len(content.split()),
            summary=summary,
            status=ChapterStatus.REVIEWING,
            generated_at=datetime.now(),
        )

    def revise_chapter(
        self,
        chapter: Chapter,
        issues: list[str],
        concept: StoryConcept,
        state: StoryState,
    ) -> Chapter:
        """Revise a chapter based on review feedback.

        Args:
            chapter: The chapter to revise
            issues: List of issues to address
            concept: Story concept for context
            state: Current story state

        Returns:
            Revised Chapter object
        """
        revision_prompt = f"""Revise this chapter to address the following issues:

ISSUES TO FIX:
{chr(10).join(f"- {issue}" for issue in issues)}

ORIGINAL CHAPTER:
{chapter.content}

STORY CONTEXT:
Title: {concept.title}
Chapter {chapter.number}: {chapter.title}

Rewrite the complete chapter, maintaining everything that works well while
fixing the identified issues. Keep the same overall structure and key events.

Write the revised chapter now, with no preamble or explanation."""

        revised_content = self.client.generate(
            revision_prompt,
            system_instruction=CHAPTER_SYSTEM_INSTRUCTION,
            temperature=0.7,  # Slightly lower for more focused revision
        )

        revised_content = self._clean_chapter_content(revised_content)
        summary = self._generate_summary(revised_content)

        chapter.content = revised_content
        chapter.word_count = len(revised_content.split())
        chapter.summary = summary
        chapter.revision_count += 1
        chapter.status = ChapterStatus.REVIEWING

        return chapter

    def _build_story_bible(self, concept: StoryConcept) -> str:
        """Build a compressed story bible for context."""
        parts = []

        parts.append(f"TITLE: {concept.title}")
        parts.append(f"LOGLINE: {concept.logline}")
        parts.append(f"THEMES: {', '.join(concept.themes)}")

        if concept.world:
            parts.append(f"\nWORLD:")
            parts.append(f"  Setting: {concept.world.setting}")
            parts.append(f"  Time Period: {concept.world.time_period}")
            parts.append(f"  Technology: {concept.world.technology_level}")
            parts.append(f"  Society: {concept.world.society}")
            if concept.world.rules:
                parts.append(f"  Key Rules: {'; '.join(concept.world.rules)}")

        if concept.characters:
            parts.append(f"\nCHARACTERS:")
            for char in concept.characters:
                parts.append(f"  {char.name} ({char.role}): {char.description}")
                parts.append(f"    Motivation: {char.motivation}")
                parts.append(f"    Arc: {char.arc}")

        return "\n".join(parts)

    def _build_previous_summaries(self, state: StoryState, current_chapter: int) -> str:
        """Build summaries of all previous chapters."""
        if current_chapter <= 1:
            return "(This is the first chapter)"

        summaries = []
        for ch in state.chapters:
            if ch.number < current_chapter and ch.status == ChapterStatus.COMPLETE:
                summaries.append(f"Chapter {ch.number} - {ch.title}: {ch.summary}")

        return "\n".join(summaries) if summaries else "(No previous chapters)"

    def _build_previous_chapter_section(self, state: StoryState, current_chapter: int) -> str:
        """Get the previous chapter's full text for voice continuity."""
        if current_chapter <= 1:
            return ""

        # Get the last completed chapter
        previous_chapters = [
            ch for ch in state.chapters
            if ch.number < current_chapter and ch.status == ChapterStatus.COMPLETE
        ]

        if not previous_chapters:
            return ""

        last_chapter = max(previous_chapters, key=lambda c: c.number)

        # Include last 2000 words of previous chapter for voice continuity
        words = last_chapter.content.split()
        if len(words) > 2000:
            excerpt = " ".join(words[-2000:])
            return f"=== END OF PREVIOUS CHAPTER (for voice continuity) ===\n...{excerpt}"
        else:
            return f"=== PREVIOUS CHAPTER (for voice continuity) ===\n{last_chapter.content}"

    def _generate_summary(self, content: str) -> str:
        """Generate a summary of the chapter content."""
        prompt = CHAPTER_SUMMARY_PROMPT.format(chapter_content=content[:10000])

        summary = self.client.generate(
            prompt,
            temperature=0.3,  # Low temperature for factual summary
        )

        return summary.strip()

    def _clean_chapter_content(self, content: str) -> str:
        """Clean up chapter content, removing any preamble."""
        lines = content.strip().split("\n")

        # Remove common preambles
        skip_prefixes = [
            "here is",
            "here's",
            "chapter",
            "# chapter",
            "## chapter",
        ]

        start_idx = 0
        for i, line in enumerate(lines[:5]):
            lower_line = line.lower().strip()
            if any(lower_line.startswith(prefix) for prefix in skip_prefixes):
                start_idx = i + 1
            elif lower_line.startswith("---") or lower_line.startswith("***"):
                start_idx = i + 1

        return "\n".join(lines[start_idx:]).strip()
