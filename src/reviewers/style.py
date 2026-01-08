"""Style reviewer for voice, pacing, and craft quality."""

from .abstract_reviewer import AbstractReviewer
from .base import ReviewContext, ContentType


class StyleReviewer(AbstractReviewer):
    """Reviews content for style and craft quality.

    Evaluates:
    - Voice consistency
    - Pacing
    - Show vs tell
    - Prose quality
    - Dialogue authenticity
    """

    @property
    def name(self) -> str:
        return "style"

    @property
    def supported_content_types(self) -> list[ContentType]:
        return [ContentType.CHAPTER]

    def _get_system_instruction(self) -> str:
        return """You are an expert fiction editor specializing in prose style and craft.
You have a refined sense for voice, pacing, and narrative technique.
You provide specific feedback on craft elements that impact reader experience.
Always respond with valid JSON when asked for structured output."""

    def _get_criteria_description(self) -> str:
        return """1. VOICE
   - Narrative voice consistent throughout
   - Character dialogue feels authentic and distinct
   - Tone matches the story's established style
   - Point of view maintained consistently

2. PACING
   - Opens with an engaging hook
   - Scenes flow naturally
   - Tension managed appropriately
   - No sections that drag or feel rushed

3. CRAFT
   - "Show don't tell" principle followed
   - Sensory details bring scenes to life
   - Dialogue serves character and plot
   - Prose avoids cliches and purple prose
   - Action is clear and easy to follow"""

    def _build_review_prompt(self, context: ReviewContext) -> str:
        concept = context.concept
        chapter = context.chapter

        return f"""Review this chapter for prose style and craft quality.

=== STORY CONTEXT ===
Title: {concept.title}
Genre: {', '.join(concept.genre_tags)}

=== CHAPTER TO REVIEW ===
Chapter {chapter.number}: {chapter.title}
{chapter.content}

=== EVALUATION CRITERIA ===
{self._get_criteria_description()}

Focus on craft issues that significantly impact reader experience.
Minor stylistic preferences are LOW severity.
Significant pacing or voice problems that break immersion are HIGH severity.

Respond with JSON:
{self._format_json_schema()}"""
