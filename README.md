# Sci-Fi Story Generator

AI-powered science fiction story generator using Google Gemini. Generates complete novels with iterative self-review and revision.

## Features

- Generate unique story concepts with world-building and character details
- Expand concepts into detailed chapter-by-chapter outlines
- Generate chapters one at a time with full context awareness
- Self-review system that critiques and revises each chapter
- Persistent storage to resume generation at any time
- Export complete stories to markdown

## Installation

```bash
# Clone or navigate to the project
cd stories

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or: .venv\Scripts\activate  # Windows

# Install dependencies
pip install -e .
```

## Configuration

1. Get a Google Gemini API key from [Google AI Studio](https://makersuite.google.com/app/apikey)

2. Set your API key:
```bash
export GEMINI_API_KEY=your_api_key_here
```

Or create a `.env` file:
```bash
cp .env.example .env
# Edit .env with your API key
```

## Usage

### Create a New Story

```bash
# Interactive mode - generates concepts, lets you pick one
stories new

# With themes
stories new --themes "space opera, first contact"

# Specify chapter count
stories new --chapters 15
```

### Generate Chapters

```bash
# Generate next chapter
stories chapter STORY_ID

# Generate specific chapter
stories chapter STORY_ID --number 5

# Generate all remaining chapters
stories chapter STORY_ID --all
```

### Manage Stories

```bash
# List all stories
stories list

# Show story details
stories show STORY_ID

# View full outline
stories outline STORY_ID

# Resume an in-progress story
stories resume STORY_ID

# Export to markdown
stories export STORY_ID
```

### Just Generate Concepts

```bash
# Generate 5 concepts without creating a story
stories concept --count 5 --themes "cyberpunk"
```

## How It Works

### 1. Concept Generation
The system generates multiple unique story concepts based on optional themes. Each concept includes:
- Title and logline
- Synopsis
- Genre tags and themes

### 2. Outline Expansion
Once you select a concept, it expands into:
- Detailed world-building (setting, technology, society)
- Character profiles with motivations and arcs
- Chapter-by-chapter plot outline

### 3. Chapter Generation
Each chapter is generated with full context:
- Story bible (world and character details)
- All previous chapter summaries
- Recent chapter text (for voice consistency)
- Current chapter outline

### 4. Self-Review Loop
After generation, each chapter is reviewed for:
- **Continuity**: Character/world consistency
- **Pacing**: Tension and flow
- **Voice**: Style consistency
- **Plot**: Adherence to outline
- **Craft**: Show-don't-tell, avoiding clichs

If issues are found above the threshold, the chapter is automatically revised (up to 2 times).

## Storage

Stories are saved to `~/.stories/` by default:

```
~/.stories/
  {story-id}/
    concept.json      # Story concept and outline
    state.json        # Current progress
    chapters/
      01_chapter.md   # Chapter content
      01_meta.json    # Chapter metadata
      01_review.json  # Review results
```

## Model Selection

By default, uses `gemini-2.0-flash`. Change with:

```bash
# Environment variable
export GEMINI_MODEL=gemini-1.5-pro

# Or per-command
stories new --model gemini-1.5-pro
```

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest
```

## License

MIT
