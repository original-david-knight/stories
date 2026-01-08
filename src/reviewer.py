"""Self-review system for chapter quality assessment."""

import json
import re
from datetime import datetime
from typing import Optional

from .gemini_client import GeminiClient
from .models import (
    Chapter,
    ChapterReview,
    ReviewIssue,
    Severity,
    StoryConcept,
    StoryState,
)


REVIEW_SYSTEM_INSTRUCTION = """You are an expert fiction editor specializing in science fiction.
You have a keen eye for continuity errors, pacing issues, voice inconsistencies, and craft problems.
You provide constructive, specific feedback that helps improve the work.
Always respond with valid JSON when asked for structured output."""


REVIEW_PROMPT = """Review this chapter for quality and consistency with the story.

=== STORY CONTEXT ===
Title: {title}
Themes: {themes}
World Setting: {world_setting}

=== ESTABLISHED CHARACTERS ===
{characters}

=== PREVIOUS CHAPTER SUMMARIES ===
{previous_summaries}

=== CHAPTER TO REVIEW ===
Chapter {chapter_num}: {chapter_title}
{chapter_content}

=== EVALUATION CRITERIA ===
Evaluate the chapter on these dimensions:

1. CONTINUITY
   - Character names spelled consistently
   - Character behaviors match established personalities
   - World details consistent with story bible
   - Timeline and sequence of events logical
   - No contradictions with previous chapters

2. PACING
   - Chapter opens with an engaging hook
   - Scenes flow naturally without abrupt jumps
   - Tension rises appropriately
   - No sections that drag or feel rushed
   - Ending creates forward momentum

3. VOICE
   - Narrative voice consistent with genre (sci-fi)
   - Character dialogue feels authentic and distinct
   - Tone matches the story's established style
   - Point of view maintained consistently

4. PLOT
   - Chapter advances the main plot
   - Events align with the chapter's intended purpose
   - Foreshadowing and setup are present where needed
   - Subplots are woven in naturally

5. CRAFT
   - "Show don't tell" principle followed
   - Sensory details bring scenes to life
   - Dialogue serves character and plot
   - Prose avoids clichés and purple prose
   - Action is clear and easy to follow

Respond with a JSON object:
{{
    "overall_quality": "excellent/good/needs_revision/poor",
    "strengths": ["strength 1", "strength 2", ...],
    "issues": [
        {{
            "category": "continuity/pacing/voice/plot/craft",
            "severity": "low/medium/high",
            "location": "Quote the problematic text (max 50 words)",
            "description": "What the problem is",
            "suggestion": "How to fix it"
        }}
    ],
    "revision_needed": true/false
}}

Be thorough but fair. Only flag genuine issues that impact reader experience.
A chapter can be good without being perfect."""


class ChapterReviewer:
    """Reviews chapters for quality and consistency."""

    def __init__(
        self,
        client: GeminiClient,
        revision_threshold: Severity = Severity.MEDIUM,
    ):
        """Initialize the reviewer.

        Args:
            client: Configured GeminiClient instance
            revision_threshold: Minimum severity to trigger revision
        """
        self.client = client
        self.revision_threshold = revision_threshold

    def review_chapter(
        self,
        chapter: Chapter,
        concept: StoryConcept,
        state: StoryState,
    ) -> ChapterReview:
        """Review a chapter for quality and consistency.

        Args:
            chapter: The chapter to review
            concept: Story concept for context
            state: Current story state

        Returns:
            ChapterReview with issues found
        """
        # Build context
        characters = self._format_characters(concept)
        previous_summaries = self._format_previous_summaries(state, chapter.number)
        world_setting = concept.world.setting if concept.world else "Not specified"

        prompt = REVIEW_PROMPT.format(
            title=concept.title,
            themes=", ".join(concept.themes),
            world_setting=world_setting,
            characters=characters,
            previous_summaries=previous_summaries,
            chapter_num=chapter.number,
            chapter_title=chapter.title,
            chapter_content=chapter.content,
        )

        response = self.client.generate(
            prompt,
            system_instruction=REVIEW_SYSTEM_INSTRUCTION,
            temperature=0.3,  # Lower temperature for analytical task
        )

        review_data = self._parse_json_response(response)

        # Parse issues
        issues = []
        for issue_data in review_data.get("issues", []):
            try:
                severity = Severity(issue_data.get("severity", "low").lower())
            except ValueError:
                severity = Severity.LOW

            issue = ReviewIssue(
                category=issue_data.get("category", "craft"),
                severity=severity,
                location=issue_data.get("location", "")[:200],  # Limit length
                description=issue_data.get("description", ""),
                suggestion=issue_data.get("suggestion", ""),
            )
            issues.append(issue)

        # Determine if revision is needed based on threshold
        revision_needed = self._should_revise(issues)

        return ChapterReview(
            chapter_number=chapter.number,
            issues=issues,
            overall_quality=review_data.get("overall_quality", "good"),
            strengths=review_data.get("strengths", []),
            revision_needed=revision_needed,
            reviewed_at=datetime.now(),
        )

    def get_revision_issues(self, review: ChapterReview) -> list[str]:
        """Get a list of issues that need to be addressed in revision.

        Args:
            review: The chapter review

        Returns:
            List of issue descriptions for revision prompt
        """
        revision_issues = []

        for issue in review.issues:
            if self._severity_meets_threshold(issue.severity):
                revision_issues.append(
                    f"[{issue.category.upper()}] {issue.description} "
                    f"(Location: \"{issue.location}\") "
                    f"Suggestion: {issue.suggestion}"
                )

        return revision_issues

    def _should_revise(self, issues: list[ReviewIssue]) -> bool:
        """Determine if revision is needed based on issues and threshold."""
        severity_order = {Severity.LOW: 0, Severity.MEDIUM: 1, Severity.HIGH: 2}
        threshold_level = severity_order[self.revision_threshold]

        # Count issues at or above threshold
        significant_issues = sum(
            1 for issue in issues
            if severity_order[issue.severity] >= threshold_level
        )

        # Revision needed if any high severity, or multiple medium+
        has_high = any(issue.severity == Severity.HIGH for issue in issues)
        return has_high or significant_issues >= 2

    def _severity_meets_threshold(self, severity: Severity) -> bool:
        """Check if a severity level meets the revision threshold."""
        severity_order = {Severity.LOW: 0, Severity.MEDIUM: 1, Severity.HIGH: 2}
        return severity_order[severity] >= severity_order[self.revision_threshold]

    def _format_characters(self, concept: StoryConcept) -> str:
        """Format character info for review context."""
        if not concept.characters:
            return "No characters defined"

        lines = []
        for char in concept.characters:
            lines.append(f"- {char.name} ({char.role}): {char.description}")

        return "\n".join(lines)

    def _format_previous_summaries(self, state: StoryState, current_chapter: int) -> str:
        """Format previous chapter summaries."""
        summaries = state.get_chapter_summaries(up_to=current_chapter)
        if not summaries:
            return "(This is the first chapter)"
        return "\n".join(summaries)

    def _parse_json_response(self, response: str) -> dict:
        """Parse JSON from response."""
        # Try to extract JSON from markdown code blocks
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", response)
        if json_match:
            json_str = json_match.group(1).strip()
        else:
            json_str = response.strip()

        # Find JSON object
        start_idx = json_str.find("{")
        if start_idx == -1:
            return {"overall_quality": "good", "issues": [], "strengths": [], "revision_needed": False}

        # Find matching end brace
        depth = 0
        end_idx = start_idx
        for i, char in enumerate(json_str[start_idx:], start_idx):
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    end_idx = i + 1
                    break

        json_str = json_str[start_idx:end_idx]

        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            # Return safe default if parsing fails
            return {
                "overall_quality": "good",
                "issues": [],
                "strengths": [],
                "revision_needed": False,
            }
