# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Sci-Fi Story Generator is a CLI tool that uses Google Gemini to generate complete science fiction novels with iterative self-review and revision. Stories are generated through a multi-stage pipeline: concept generation → outline expansion → chapter generation, with multi-reviewer validation at each stage.

## Commands

```bash
# Install
pip install -e .          # Install for development
pip install -e ".[dev]"   # Include test dependencies

# Run CLI
stories new               # Create new story (interactive)
stories list              # List all stories
stories show STORY_ID     # Show story details
stories outline STORY_ID  # View full outline
stories chapter STORY_ID  # Generate next chapter
stories chapter STORY_ID --all  # Generate all remaining
stories resume STORY_ID   # Resume in-progress story
stories export STORY_ID   # Export to markdown
stories concept           # Generate concepts only (no story)
stories config            # Show current configuration

# Development
pytest                    # Run all tests
pytest tests/test_models.py::TestChapter  # Run specific test class
pytest -k "test_create"   # Run tests matching pattern
```

## Architecture

```
src/
├── cli.py              # Typer CLI entry point, user interactions
├── orchestrator.py     # Main workflow controller, coordinates generators and reviewers
├── gemini_client.py    # Gemini API wrapper with retry logic
├── persistence.py      # File storage for stories (~/.stories/)
├── models.py           # Pydantic data models (StoryConcept, Chapter, etc.)
├── generators/
│   ├── concept.py      # Concept generation, outline expansion, character generation
│   └── chapter.py      # Chapter generation with context awareness
└── reviewers/          # Multi-reviewer system
    ├── base.py         # Reviewer Protocol, ReviewContext, ReviewResult, ContentType
    ├── abstract_reviewer.py  # Shared reviewer implementation (template pattern)
    ├── registry.py     # ReviewerRegistry for managing multiple reviewers
    ├── correctness.py  # Continuity, plot logic, character consistency
    ├── style.py        # Voice, pacing, craft quality
    └── scientific.py   # Scientific accuracy for sci-fi plausibility
```

**Key flow**: `CLI → StoryOrchestrator → ConceptGenerator/ChapterGenerator → GeminiClient`

The orchestrator coordinates the full workflow:
1. Generates content via ConceptGenerator or ChapterGenerator
2. Runs multi-reviewer validation (ReviewerRegistry dispatches to applicable reviewers)
3. Revises content if any reviewer returns HIGH severity issues
4. Repeats until all pass or max_revisions (default: 7) is reached

## Interactive Story Creation Flow

After automated concept review, the CLI guides users through:

### 1. Concept Feedback Loop
- Concept is displayed
- User is asked "Would you like to request any changes?"
- If yes, user provides free-form feedback and concept is revised
- Repeats until user says no more changes

### 2. Character Approval
- Major characters are generated based on the concept
- Each character is displayed with: name, role, description, motivation, arc, relationships
- User chooses "accept" or "retry" for each character
- Retry generates a fresh version of that character
- Continues until all characters are approved

### 3. Outline Expansion
- Proceeds to generate full chapter outline with automated review

## Multi-Reviewer System

Reviews run at three stages based on `ContentType`:
- **CONCEPT**: Correctness + Scientific Accuracy
- **OUTLINE**: Correctness + Scientific Accuracy
- **CHAPTER**: Correctness + Style + Scientific Accuracy

Pass criteria: No HIGH severity issues. MEDIUM/LOW issues are logged but don't block.

### Adding a New Reviewer

1. Create reviewer in `src/reviewers/myreviewer.py`:

```python
from .abstract_reviewer import AbstractReviewer
from .base import ContentType

class MyReviewer(AbstractReviewer):
    @property
    def name(self) -> str:
        return "my_reviewer"

    @property
    def supported_content_types(self) -> list[ContentType]:
        return [ContentType.CHAPTER]

    def _get_system_instruction(self) -> str:
        return "You are an expert in..."

    def _get_criteria_description(self) -> str:
        return "1. CRITERION_A\n2. CRITERION_B..."

    def _build_review_prompt(self, context: ReviewContext) -> str:
        # Build prompt using context.content, context.concept, etc.
        ...
```

2. Register in `orchestrator._create_default_registry()`:
```python
registry.register(MyReviewer(self.client))
```

3. Export from `src/reviewers/__init__.py`

## Configuration

Environment variables:
- `GEMINI_API_KEY` - Required API key (get from [Google AI Studio](https://makersuite.google.com/app/apikey))
- `GEMINI_MODEL` - Model name (default: gemini-2.0-flash)
- `STORIES_PATH` - Storage location (default: ~/.stories/)

Can also use `.env` file (loaded via python-dotenv).

## Storage Structure

```
~/.stories/{story-id}/
├── concept.json      # Full story concept with outline
├── state.json        # Current generation progress
├── generation_log.json
├── concept_review.json        # Concept review results
├── outline_review.json        # Outline review results
└── chapters/
    ├── 01_chapter_title.md
    ├── 01_meta.json
    └── 01_aggregated_review.json  # Multi-reviewer results
```

## Key Patterns

- All data models use Pydantic with `model_dump(mode="json")` for serialization
- JSON responses from Gemini are parsed via shared utilities in `src/utils.py` (handles markdown code blocks)
- Chapter generation includes previous chapter summaries + last 2000 words for voice continuity
- Temperature varies by task: 0.9 for concept generation, 0.85 for chapters, 0.3 for reviews/summaries
- Reviewers implement the `Reviewer` Protocol and are managed via `ReviewerRegistry`
- AbstractReviewer uses template pattern: subclasses override `_get_system_instruction()`, `_get_criteria_description()`, `_build_review_prompt()`
- ReviewContext carries all state needed for review (concept, state, chapter, content_type, iteration count)
