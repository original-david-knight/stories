"""CLI interface for the Sci-Fi Story Generator."""

import os
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.table import Table

from .gemini_client import GeminiClient
from .models import Character, Severity, StoryConcept
from .orchestrator import StoryOrchestrator

# Load environment variables
load_dotenv()

app = typer.Typer(
    name="stories",
    help="AI-powered science fiction story generator using Google Gemini",
    add_completion=False,
)
console = Console()

# Default paths
DEFAULT_STORAGE_PATH = Path.home() / ".stories"
DEFAULT_MODEL = "gemini-2.0-flash"


def get_api_key() -> str:
    """Get the Gemini API key from environment."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        console.print("[red]Error: GEMINI_API_KEY environment variable not set[/red]")
        console.print("Set it with: export GEMINI_API_KEY=your_api_key")
        raise typer.Exit(1)
    return api_key


def get_orchestrator(
    storage_path: Optional[Path] = None,
    model: Optional[str] = None,
) -> StoryOrchestrator:
    """Create and return a configured orchestrator."""
    api_key = get_api_key()
    storage = storage_path or DEFAULT_STORAGE_PATH
    model_name = model or os.getenv("GEMINI_MODEL", DEFAULT_MODEL)

    client = GeminiClient(api_key=api_key, model=model_name)

    def progress_callback(msg: str) -> None:
        console.print(f"  [dim]{msg}[/dim]")

    return StoryOrchestrator(
        client=client,
        storage_path=storage,
        on_progress=progress_callback,
    )


def display_concept(concept: StoryConcept) -> None:
    """Display a concept in a formatted panel."""
    console.print(Panel(
        f"[bold]{concept.title}[/bold]\n\n"
        f"[italic]{concept.logline}[/italic]\n\n"
        f"{concept.synopsis}\n\n"
        f"[dim]Themes: {', '.join(concept.themes)}[/dim]",
        title="[cyan]Current Concept[/cyan]",
        border_style="cyan",
    ))


def user_feedback_loop(
    orchestrator: StoryOrchestrator,
    concept: StoryConcept,
) -> StoryConcept:
    """Interactive loop for user to request changes to a concept.

    Args:
        orchestrator: The story orchestrator
        concept: The concept to refine

    Returns:
        The refined concept
    """
    while True:
        console.print()
        display_concept(concept)
        console.print()

        if not Confirm.ask("Would you like to request any changes?", default=False):
            console.print("[green]Concept finalized![/green]")
            break

        feedback = Prompt.ask(
            "What changes would you like?",
            default="",
        )

        if not feedback.strip():
            console.print("[dim]No changes requested[/dim]")
            continue

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task("Revising concept...", total=None)
            concept = orchestrator.revise_concept_with_user_feedback(concept, feedback)

    return concept


def display_character(character: Character, index: int) -> None:
    """Display a character in a formatted panel."""
    relationships_str = ", ".join(character.relationships) if character.relationships else "None defined"

    console.print(Panel(
        f"[bold cyan]{character.name}[/bold cyan] ([italic]{character.role}[/italic])\n\n"
        f"[bold]Description:[/bold]\n{character.description}\n\n"
        f"[bold]Motivation:[/bold]\n{character.motivation}\n\n"
        f"[bold]Character Arc:[/bold]\n{character.arc}\n\n"
        f"[dim]Relationships: {relationships_str}[/dim]",
        title=f"[yellow]Character {index + 1}[/yellow]",
        border_style="yellow",
    ))


def character_approval_loop(
    orchestrator: StoryOrchestrator,
    concept: StoryConcept,
    num_characters: int = 4,
) -> StoryConcept:
    """Generate characters and get user approval for each.

    Args:
        orchestrator: The story orchestrator
        concept: The story concept
        num_characters: Number of characters to generate

    Returns:
        Concept with approved characters
    """
    # Generate initial characters
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Generating characters...", total=None)
        concept = orchestrator.generate_characters(concept, num_characters)

    console.print()
    console.print("[bold]Character Approval[/bold]")
    console.print("Review each character. You can accept or retry for a new version.\n")

    # Loop through each character for approval
    i = 0
    while i < len(concept.characters):
        character = concept.characters[i]
        display_character(character, i)
        console.print()

        choice = Prompt.ask(
            f"Character {i + 1}/{len(concept.characters)}",
            choices=["accept", "retry"],
            default="accept",
        )

        if choice == "accept":
            console.print(f"[green]✓ {character.name} accepted[/green]\n")
            i += 1
        else:
            # Ask for optional feedback
            feedback = Prompt.ask(
                "Feedback for regeneration (or press Enter for fresh take)",
                default="",
            )
            user_feedback = feedback.strip() if feedback.strip() else None

            # Regenerate this character
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                action = "Revising" if user_feedback else "Regenerating"
                progress.add_task(f"{action} {character.role}...", total=None)
                concept = orchestrator.regenerate_character(concept, i, user_feedback)
            console.print()
            # Don't increment i, show the new character

    console.print("[green]All characters approved![/green]")
    return concept


def concept_selection_loop(
    orchestrator: StoryOrchestrator,
    theme_list: Optional[list[str]] = None,
) -> StoryConcept:
    """Generate concepts one at a time until user accepts one.

    Args:
        orchestrator: The story orchestrator
        theme_list: Optional themes to incorporate

    Returns:
        The accepted concept
    """
    while True:
        # Generate a single concept
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task("Generating story concept...", total=None)
            concept = orchestrator.generate_concept(themes=theme_list)

        console.print()
        display_concept(concept)
        console.print()

        choice = Prompt.ask(
            "Do you want to use this concept?",
            choices=["accept", "reject"],
            default="accept",
        )

        if choice == "accept":
            console.print(f"[green]Accepted:[/green] {concept.title}")
            return concept
        else:
            # Save rejected concept to avoid generating similar ones
            orchestrator.reject_concept(concept)
            console.print("[dim]Generating a new concept...[/dim]\n")


@app.command()
def new(
    themes: Optional[str] = typer.Option(
        None, "--themes", "-t",
        help="Comma-separated themes to incorporate",
    ),
    chapters: int = typer.Option(
        12, "--chapters", "-c",
        help="Target number of chapters",
    ),
    characters: int = typer.Option(
        4, "--characters",
        help="Number of major characters to generate",
    ),
    model: Optional[str] = typer.Option(
        None, "--model", "-m",
        help="Gemini model to use",
    ),
):
    """Start a new story by generating and selecting a concept."""
    orchestrator = get_orchestrator(model=model)

    theme_list = [t.strip() for t in themes.split(",")] if themes else None

    console.print(Panel("🚀 [bold]Sci-Fi Story Generator[/bold]", style="cyan"))
    console.print()

    # Generate concepts one at a time until user accepts
    selected_concept = concept_selection_loop(orchestrator, theme_list)

    # User feedback loop for concept refinement
    selected_concept = user_feedback_loop(orchestrator, selected_concept)

    # Character generation and approval
    console.print()
    selected_concept = character_approval_loop(orchestrator, selected_concept, characters)

    # Confirm and create story
    console.print()
    if Confirm.ask("Expand into full outline and create story?", default=True):
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task("Expanding outline...", total=None)
            story_id = orchestrator.create_story(selected_concept, num_chapters=chapters)

        console.print(f"\n[green]✓ Story created![/green]")
        console.print(f"  ID: [cyan]{story_id}[/cyan]")
        console.print(f"  Chapters: {chapters}")
        console.print()
        console.print("Start generating with: [cyan]stories chapter next[/cyan]")


@app.command()
def concept(
    count: int = typer.Option(5, "--count", "-n", help="Number of concepts to generate"),
    themes: Optional[str] = typer.Option(None, "--themes", "-t", help="Themes to incorporate"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model to use"),
):
    """Generate story concepts without creating a story."""
    orchestrator = get_orchestrator(model=model)
    theme_list = [t.strip() for t in themes.split(",")] if themes else None

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Generating concepts...", total=None)
        concepts = orchestrator.generate_concepts(count=count, themes=theme_list)

    for i, concept in enumerate(concepts, 1):
        console.print(Panel(
            f"[bold]{concept.title}[/bold]\n\n"
            f"[italic]{concept.logline}[/italic]\n\n"
            f"{concept.synopsis[:500]}...",
            title=f"[cyan]{i}[/cyan]",
        ))


@app.command()
def chapter(
    story_id: str = typer.Argument(..., help="Story ID"),
    number: Optional[int] = typer.Option(None, "--number", "-n", help="Chapter number (default: next)"),
    all_chapters: bool = typer.Option(False, "--all", "-a", help="Generate all remaining chapters"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model to use"),
):
    """Generate chapter(s) for a story."""
    orchestrator = get_orchestrator(model=model)

    state = orchestrator.get_story_state(story_id)
    if not state:
        console.print(f"[red]Story not found: {story_id}[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]{state.concept.title}[/bold]")
    console.print()

    if all_chapters:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Generating chapters...", total=None)
            chapters = orchestrator.generate_all_chapters(story_id)

        console.print(f"\n[green]✓ Generated {len(chapters)} chapters[/green]")
    else:
        chapter_num = number
        if chapter_num is None:
            # Show next chapter info
            completed = len(state.get_completed_chapters())
            total = len(state.concept.chapter_outlines)
            chapter_num = completed + 1
            console.print(f"Progress: {completed}/{total} chapters")

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            progress.add_task(f"Generating chapter {chapter_num}...", total=None)
            chapter = orchestrator.generate_chapter(story_id, chapter_num)

        console.print(f"\n[green]✓ Chapter {chapter.number} complete[/green]")
        console.print(f"  Title: {chapter.title}")
        console.print(f"  Words: {chapter.word_count}")
        console.print(f"  Revisions: {chapter.revision_count}")


@app.command(name="list")
def list_stories():
    """List all saved stories."""
    orchestrator = get_orchestrator()
    stories = orchestrator.list_stories()

    if not stories:
        console.print("[dim]No stories found[/dim]")
        console.print("Create one with: [cyan]stories new[/cyan]")
        return

    table = Table(title="Your Stories")
    table.add_column("ID", style="cyan")
    table.add_column("Title")
    table.add_column("Progress")
    table.add_column("Status")
    table.add_column("Updated")

    for story in stories:
        progress = f"{story['chapters_complete']}/{story['total_chapters']}"
        table.add_row(
            story["id"],
            story["title"][:30],
            progress,
            story["status"],
            story["updated_at"][:10],
        )

    console.print(table)


@app.command()
def show(
    story_id: str = typer.Argument(..., help="Story ID"),
):
    """Show details of a story."""
    orchestrator = get_orchestrator()
    state = orchestrator.get_story_state(story_id)

    if not state:
        console.print(f"[red]Story not found: {story_id}[/red]")
        raise typer.Exit(1)

    concept = state.concept

    console.print(Panel(
        f"[bold]{concept.title}[/bold]\n\n"
        f"[italic]{concept.logline}[/italic]\n\n"
        f"{concept.synopsis}",
        title="Story Concept",
    ))

    console.print()
    console.print("[bold]Chapters:[/bold]")

    for outline in concept.chapter_outlines:
        # Find if chapter is generated
        chapter = next(
            (ch for ch in state.chapters if ch.number == outline.number),
            None,
        )
        status = "✓" if chapter and chapter.status.value == "complete" else "○"
        words = f"({chapter.word_count} words)" if chapter else ""

        console.print(f"  {status} Chapter {outline.number}: {outline.title} {words}")


@app.command()
def outline(
    story_id: str = typer.Argument(..., help="Story ID"),
):
    """Show the full outline of a story."""
    orchestrator = get_orchestrator()
    state = orchestrator.get_story_state(story_id)

    if not state:
        console.print(f"[red]Story not found: {story_id}[/red]")
        raise typer.Exit(1)

    concept = state.concept

    console.print(f"[bold]{concept.title}[/bold]")
    console.print()

    if concept.world:
        console.print(Panel(
            f"[bold]Setting:[/bold] {concept.world.setting}\n"
            f"[bold]Time:[/bold] {concept.world.time_period}\n"
            f"[bold]Technology:[/bold] {concept.world.technology_level}\n"
            f"[bold]Society:[/bold] {concept.world.society}",
            title="World",
        ))

    console.print()
    console.print("[bold]Characters:[/bold]")
    for char in concept.characters:
        console.print(f"  • [cyan]{char.name}[/cyan] ({char.role})")
        console.print(f"    {char.description}")
        console.print()

    console.print("[bold]Chapter Outline:[/bold]")
    for ch in concept.chapter_outlines:
        console.print(f"\n[cyan]Chapter {ch.number}: {ch.title}[/cyan]")
        console.print(f"  {ch.summary}")
        console.print(f"  [dim]Events: {', '.join(ch.key_events[:3])}[/dim]")


@app.command()
def export(
    story_id: str = typer.Argument(..., help="Story ID"),
):
    """Export a story to a markdown file."""
    orchestrator = get_orchestrator()

    try:
        path = orchestrator.export_story(story_id)
        console.print(f"[green]✓ Story exported to:[/green] {path}")
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def epub(
    story_id: str = typer.Argument(..., help="Story ID"),
):
    """Export completed chapters to an EPUB file."""
    orchestrator = get_orchestrator()

    try:
        path = orchestrator.export_epub(story_id)
        console.print(f"[green]✓ Story exported to:[/green] {path}")
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def cover(
    story_id: str = typer.Argument(..., help="Story ID"),
    style: str = typer.Option(
        "cinematic", "--style", "-s",
        help="Visual style: cinematic, illustrated, minimalist, retro",
    ),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model to use"),
):
    """Generate a book cover image using Nano Banana 2."""
    orchestrator = get_orchestrator(model=model)

    state = orchestrator.get_story_state(story_id)
    if not state:
        console.print(f"[red]Story not found: {story_id}[/red]")
        raise typer.Exit(1)

    console.print(f"[bold]{state.concept.title}[/bold]")
    console.print(f"Style: {style}")
    console.print()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        progress.add_task("Generating cover image...", total=None)
        try:
            path = orchestrator.generate_cover(story_id, style=style)
        except Exception as e:
            console.print(f"[red]Error generating cover: {e}[/red]")
            raise typer.Exit(1)

    console.print(f"\n[green]✓ Cover generated![/green]")
    console.print(f"  Path: [cyan]{path}[/cyan]")


@app.command()
def resume(
    story_id: str = typer.Argument(..., help="Story ID"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Model to use"),
):
    """Resume generating a story from where you left off."""
    orchestrator = get_orchestrator(model=model)
    state = orchestrator.resume_story(story_id)

    if not state:
        console.print(f"[red]Story not found: {story_id}[/red]")
        raise typer.Exit(1)

    completed = len(state.get_completed_chapters())
    total = len(state.concept.chapter_outlines)

    console.print(f"[bold]{state.concept.title}[/bold]")
    console.print(f"Progress: {completed}/{total} chapters")
    console.print()

    if completed >= total:
        console.print("[green]Story is complete![/green]")
        if Confirm.ask("Export story?", default=True):
            path = orchestrator.export_story(story_id)
            console.print(f"Exported to: {path}")
    else:
        if Confirm.ask(f"Continue generating from chapter {completed + 1}?", default=True):
            all_remaining = Confirm.ask("Generate all remaining chapters?", default=False)
            if all_remaining:
                chapters = orchestrator.generate_all_chapters(story_id)
                console.print(f"\n[green]✓ Generated {len(chapters)} chapters[/green]")
            else:
                chapter = orchestrator.generate_chapter(story_id)
                console.print(f"\n[green]✓ Chapter {chapter.number} complete[/green]")


@app.command()
def config():
    """Show current configuration."""
    api_key = os.getenv("GEMINI_API_KEY", "")
    model = os.getenv("GEMINI_MODEL", DEFAULT_MODEL)
    storage = os.getenv("STORIES_PATH", str(DEFAULT_STORAGE_PATH))

    table = Table(title="Configuration")
    table.add_column("Setting")
    table.add_column("Value")

    api_display = f"{api_key[:8]}...{api_key[-4:]}" if len(api_key) > 12 else "(not set)"
    table.add_row("GEMINI_API_KEY", api_display)
    table.add_row("GEMINI_MODEL", model)
    table.add_row("STORIES_PATH", storage)

    console.print(table)


def main():
    """Entry point for the CLI."""
    app()


if __name__ == "__main__":
    main()
