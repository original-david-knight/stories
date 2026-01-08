"""Correctness reviewer for continuity and consistency."""

from ..models import ChapterStatus
from .abstract_reviewer import AbstractReviewer
from .base import ReviewContext, ContentType


class CorrectnessReviewer(AbstractReviewer):
    """Reviews content for correctness and consistency.

    Evaluates:
    - Continuity errors
    - Character consistency
    - Plot logic
    - World-building consistency
    - Timeline accuracy
    """

    @property
    def name(self) -> str:
        return "correctness"

    @property
    def supported_content_types(self) -> list[ContentType]:
        return [ContentType.CONCEPT, ContentType.OUTLINE, ContentType.CHAPTER]

    def _get_system_instruction(self) -> str:
        return """You are an expert fiction editor specializing in continuity and consistency.
You have a keen eye for plot holes, character inconsistencies, and logical errors.
You provide specific, actionable feedback to improve story coherence.
Always respond with valid JSON when asked for structured output."""

    def _get_criteria_description(self) -> str:
        return """1. CONTINUITY
   - Names, dates, and facts consistent throughout
   - No contradictions with established information
   - Timeline and sequence of events logical

2. CHARACTER CONSISTENCY
   - Character behaviors match established personalities
   - Motivations remain coherent
   - Relationships develop logically

3. PLOT LOGIC
   - Cause and effect relationships make sense
   - No plot holes or unexplained events
   - Setups have payoffs

4. WORLD CONSISTENCY
   - Technology/magic rules followed consistently
   - Setting details don't contradict
   - Social structures behave consistently"""

    def _build_review_prompt(self, context: ReviewContext) -> str:
        if context.content_type == ContentType.CONCEPT:
            return self._build_concept_prompt(context)
        elif context.content_type == ContentType.OUTLINE:
            return self._build_outline_prompt(context)
        else:
            return self._build_chapter_prompt(context)

    def _build_concept_prompt(self, context: ReviewContext) -> str:
        concept = context.concept
        return f"""Review this story concept for internal consistency and logical coherence.

=== CONCEPT ===
Title: {concept.title}
Logline: {concept.logline}
Synopsis: {concept.synopsis}
Themes: {', '.join(concept.themes)}

=== EVALUATION CRITERIA ===
{self._get_criteria_description()}

Check for:
- Internal contradictions in the premise
- Character motivations that don't make sense
- Plot elements that contradict each other
- World-building inconsistencies

Respond with JSON:
{self._format_json_schema()}

Be thorough but fair. Only flag genuine issues."""

    def _build_outline_prompt(self, context: ReviewContext) -> str:
        concept = context.concept
        chapters = "\n".join([
            f"Chapter {ch.number}: {ch.title}\n  {ch.summary}\n  Events: {', '.join(ch.key_events)}"
            for ch in concept.chapter_outlines
        ])

        return f"""Review this story outline for consistency and logical flow.

=== STORY ===
Title: {concept.title}
Logline: {concept.logline}

=== CHARACTERS ===
{self._format_characters(concept)}

=== CHAPTER OUTLINE ===
{chapters}

=== EVALUATION CRITERIA ===
{self._get_criteria_description()}

Check for:
- Plot holes between chapters
- Character arcs that don't flow logically
- Timeline inconsistencies
- Missing setup or payoff

Respond with JSON:
{self._format_json_schema()}"""

    def _build_chapter_prompt(self, context: ReviewContext) -> str:
        concept = context.concept
        chapter = context.chapter
        state = context.state

        if chapter.number == 1 or not state:
            previous_summaries = "(First chapter)"
        else:
            summaries = [
                f"Chapter {ch.number}: {ch.summary}"
                for ch in state.chapters
                if ch.number < chapter.number and ch.status == ChapterStatus.COMPLETE
            ]
            previous_summaries = "\n".join(summaries) if summaries else "(No previous chapters)"

        return f"""Review this chapter for consistency with the story.

=== STORY CONTEXT ===
Title: {concept.title}
Themes: {', '.join(concept.themes)}

=== CHARACTERS ===
{self._format_characters(concept)}

=== PREVIOUS CHAPTERS ===
{previous_summaries}

=== CHAPTER TO REVIEW ===
Chapter {chapter.number}: {chapter.title}
{chapter.content}

=== EVALUATION CRITERIA ===
{self._get_criteria_description()}

Respond with JSON:
{self._format_json_schema()}"""
