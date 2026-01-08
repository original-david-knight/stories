"""Scientific accuracy reviewer for sci-fi plausibility."""

from ..models import ChapterStatus
from .abstract_reviewer import AbstractReviewer
from .base import ReviewContext, ContentType


class ScientificAccuracyReviewer(AbstractReviewer):
    """Reviews content for scientific and technological plausibility.

    Evaluates:
    - Physics accuracy (or consistent hand-waving)
    - Biology plausibility
    - Technology consistency
    - Space travel realism
    - Future society plausibility
    """

    @property
    def name(self) -> str:
        return "scientific_accuracy"

    @property
    def supported_content_types(self) -> list[ContentType]:
        return [ContentType.CONCEPT, ContentType.OUTLINE, ContentType.CHAPTER]

    def _get_system_instruction(self) -> str:
        return """You are a science consultant for science fiction stories.
You have expertise in physics, biology, astronomy, and technology.
You understand the difference between hard sci-fi accuracy and soft sci-fi that
requires internal consistency even with fictional science.
You flag issues that would break reader immersion for a knowledgeable audience.
Always respond with valid JSON when asked for structured output."""

    def _get_criteria_description(self) -> str:
        return """1. PHYSICS
   - Basic physics respected (unless explicitly hand-waved)
   - Space mechanics reasonable for the tech level
   - Energy requirements considered
   - Scale and distances appropriate

2. BIOLOGY
   - Life support needs addressed
   - Alien biology internally consistent
   - Medical/biological elements plausible
   - Evolution and ecology make sense

3. TECHNOLOGY
   - Tech level consistent throughout
   - Capabilities don't contradict
   - Limitations respected
   - Social implications considered

4. PLAUSIBILITY
   - Future society developments reasonable
   - Economic factors addressed
   - Political structures make sense
   - Cultural evolution plausible

NOTE: Soft sci-fi gets more latitude. Focus on internal consistency
rather than hard science accuracy unless the story claims hard sci-fi."""

    def _build_review_prompt(self, context: ReviewContext) -> str:
        if context.content_type == ContentType.CONCEPT:
            return self._build_concept_prompt(context)
        elif context.content_type == ContentType.OUTLINE:
            return self._build_outline_prompt(context)
        else:
            return self._build_chapter_prompt(context)

    def _build_concept_prompt(self, context: ReviewContext) -> str:
        concept = context.concept
        return f"""Review this sci-fi concept for scientific plausibility.

=== CONCEPT ===
Title: {concept.title}
Logline: {concept.logline}
Synopsis: {concept.synopsis}
Genre Tags: {', '.join(concept.genre_tags)}

=== EVALUATION CRITERIA ===
{self._get_criteria_description()}

Is this hard sci-fi or soft sci-fi? Adjust expectations accordingly.
Flag scientific impossibilities that aren't addressed by the premise.
Internal consistency matters more than textbook accuracy.

Respond with JSON:
{self._format_json_schema()}"""

    def _build_outline_prompt(self, context: ReviewContext) -> str:
        concept = context.concept

        world_info = ""
        if concept.world:
            world_info = f"""
Setting: {concept.world.setting}
Time Period: {concept.world.time_period}
Technology Level: {concept.world.technology_level}
World Rules: {'; '.join(concept.world.rules) if concept.world.rules else 'Not specified'}
"""

        chapters = "\n".join([
            f"Chapter {ch.number}: {ch.title} - {ch.summary}"
            for ch in concept.chapter_outlines
        ])

        return f"""Review this sci-fi outline for scientific consistency.

=== STORY ===
Title: {concept.title}
Genre: {', '.join(concept.genre_tags)}

=== WORLD ===
{world_info}

=== CHAPTER OUTLINE ===
{chapters}

=== EVALUATION CRITERIA ===
{self._get_criteria_description()}

Check that science/technology is used consistently across the outline.
Flag any plot points that contradict the established science rules.

Respond with JSON:
{self._format_json_schema()}"""

    def _build_chapter_prompt(self, context: ReviewContext) -> str:
        concept = context.concept
        chapter = context.chapter

        world_info = ""
        if concept.world:
            world_info = f"""
Technology Level: {concept.world.technology_level}
World Rules: {'; '.join(concept.world.rules) if concept.world.rules else 'Not specified'}
"""

        return f"""Review this chapter for scientific accuracy and consistency.

=== WORLD CONTEXT ===
{world_info}

=== CHAPTER ===
Chapter {chapter.number}: {chapter.title}
{chapter.content}

=== EVALUATION CRITERIA ===
{self._get_criteria_description()}

Focus on:
- Does the science/tech match the established level?
- Are there physics/biology errors that break immersion?
- Is the technology used consistently?

Respond with JSON:
{self._format_json_schema()}"""
