"""Story concept and outline generation."""

from typing import Optional

from ..gemini_client import GeminiClient
from ..utils import parse_json_response
from ..models import (
    Character,
    ChapterOutline,
    StoryConcept,
    WorldDetails,
)

# Constants for limiting history items in prompts
MAX_AVOID_NAMES = 30  # Max character names to include in avoidance list
MAX_AVOID_TITLES = 20  # Max titles to include in avoidance list
MAX_AVOID_LOGLINES = 5  # Max loglines to include for premise avoidance


CONCEPT_SYSTEM_INSTRUCTION = """You are an expert science fiction author and story architect.
You specialize in creating thought-provoking, character-driven stories with compelling premises.
Your target audience is highly educated science fiction readers who appreciate originality, depth and technical accuracy.
Your concepts are original, avoid clichés, and have strong commercial and literary appeal.
Always respond with valid JSON when asked for structured output."""


CONCEPT_GENERATION_PROMPT = """Generate {count} unique science fiction story concepts.

Requirements:
- Each concept should be distinctly different in tone, subgenre, and premise
- Prefer hard sci-fi with plausible technology and scientific grounding
- Strong central conflict with personal stakes for the protagonist
- Avoid overused tropes: chosen one narratives, evil AI uprising, generic alien invasions
- Each concept should feel fresh and marketable

{theme_section}
{avoid_section}

For each concept, provide a JSON array with objects containing:
- "title": A compelling, evocative title
- "logline": One sentence that captures the core conflict and stakes
- "synopsis": 2-3 paragraphs expanding on the premise, conflict, and emotional journey
- "genre_tags": Array of relevant tags (e.g., ["space opera", "first contact", "military sci-fi"])
- "themes": Array of thematic elements explored
- "protagonist": Brief description of the main character
- "antagonist": Brief description of the opposing force (can be person, society, nature, self)

Respond ONLY with the JSON array, no additional text."""


CHARACTER_SYSTEM_INSTRUCTION = """You are an expert character designer for science fiction stories.
You create complex, believable characters with clear motivations, flaws, and growth potential.
Your characters feel like real people with distinct voices and compelling personal journeys.
Always respond with valid JSON when asked for structured output."""


CHARACTER_GENERATION_PROMPT = """Based on this story concept, generate the major characters.

STORY CONCEPT:
Title: {title}
Logline: {logline}
Synopsis: {synopsis}
Themes: {themes}
{avoid_section}

Generate {num_characters} major characters. For each character, provide:
- "name": Full name
- "role": Their role (protagonist, antagonist, deuteragonist, mentor, ally, etc.)
- "description": Physical appearance, personality traits, background (2-3 sentences)
- "motivation": What drives them, what they want most
- "flaw": Their key weakness or internal conflict
- "arc": How they will change through the story (beginning state → end state)
- "relationships": How they relate to other characters

Make characters feel distinct, with their own voices and perspectives.
Ensure the protagonist has a meaningful personal journey that ties into the themes.

Respond with a JSON array of character objects."""


CHARACTER_REGENERATE_PROMPT = """Regenerate this character with a fresh take.

STORY CONCEPT:
Title: {title}
Logline: {logline}
Themes: {themes}

CURRENT CHARACTER TO REPLACE:
Name: {char_name}
Role: {char_role}
Description: {char_description}

OTHER CHARACTERS (for relationship context):
{other_characters}

Create a NEW version of this {char_role} character. Make them:
- Distinct from the previous version
- Fitting for the story's tone and themes
- Complex with clear motivation, flaws, and growth potential

Provide the character in JSON format:
{{
    "name": "...",
    "role": "{char_role}",
    "description": "...",
    "motivation": "...",
    "flaw": "...",
    "arc": "...",
    "relationships": [...]
}}"""


CHARACTER_REVISE_PROMPT = """Revise this character based on user feedback.

STORY CONCEPT:
Title: {title}
Logline: {logline}
Themes: {themes}

CURRENT CHARACTER:
Name: {char_name}
Role: {char_role}
Description: {char_description}
Motivation: {char_motivation}
Arc: {char_arc}

USER'S REQUESTED CHANGES:
{user_feedback}

OTHER CHARACTERS (for relationship context):
{other_characters}

Revise this character according to the user's feedback while:
- Keeping them fitting for the story's tone and themes
- Maintaining complexity with clear motivation, flaws, and growth potential
- Preserving aspects the user didn't ask to change

Provide the revised character in JSON format:
{{
    "name": "...",
    "role": "{char_role}",
    "description": "...",
    "motivation": "...",
    "flaw": "...",
    "arc": "...",
    "relationships": [...]
}}"""


OUTLINE_SYSTEM_INSTRUCTION = """You are an expert story architect specializing in science fiction narratives.
You excel at creating detailed, well-paced story structures with compelling character arcs.
Your outlines balance action, character development, and thematic exploration.
Always respond with valid JSON when asked for structured output."""


OUTLINE_EXPANSION_PROMPT = """Expand this story concept into a complete novel outline.

CONCEPT:
Title: {title}
Logline: {logline}
Synopsis: {synopsis}
Themes: {themes}

TARGET LENGTH: {num_chapters} chapters

Create a detailed outline with the following JSON structure:
{{
    "world": {{
        "setting": "Primary setting description",
        "time_period": "When the story takes place",
        "technology_level": "Description of technology available",
        "society": "Social/political structure",
        "key_locations": ["Location 1", "Location 2", ...],
        "rules": ["Unique rule 1", "Unique rule 2", ...],
        "history": "Relevant backstory of this world"
    }},
    "characters": [
        {{
            "name": "Character name",
            "role": "protagonist/antagonist/supporting",
            "description": "Physical and personality description",
            "motivation": "What drives this character",
            "arc": "How they change through the story",
            "relationships": ["Relationship to other characters"]
        }}
    ],
    "chapter_outlines": [
        {{
            "number": 1,
            "title": "Chapter title",
            "summary": "2-3 sentence summary of what happens",
            "key_events": ["Event 1", "Event 2", ...],
            "characters_involved": ["Character names"],
            "location": "Where this chapter takes place",
            "emotional_arc": "The emotional journey in this chapter",
            "chapter_goal": "What this chapter accomplishes for the plot"
        }}
    ]
}}

Ensure:
- The story has a clear three-act structure
- Rising tension with well-placed revelations
- Character arcs progress naturally across chapters
- Subplots are woven throughout
- The ending is satisfying and thematically resonant

Respond ONLY with the JSON, no additional text."""


class ConceptGenerator:
    """Generates story concepts and expands them into outlines."""

    def __init__(self, client: GeminiClient):
        """Initialize with a Gemini client.

        Args:
            client: Configured GeminiClient instance
        """
        self.client = client

    def generate_concepts(
        self,
        count: int = 3,
        themes: Optional[list[str]] = None,
        avoid_titles: Optional[list[str]] = None,
        avoid_loglines: Optional[list[str]] = None,
        rejected_loglines: Optional[list[str]] = None,
    ) -> list[StoryConcept]:
        """Generate multiple story concepts.

        Args:
            count: Number of concepts to generate
            themes: Optional themes to incorporate
            avoid_titles: Previously used titles to avoid
            avoid_loglines: Previously used loglines to avoid similarity to
            rejected_loglines: Loglines from concepts the user rejected (must avoid)

        Returns:
            List of StoryConcept objects (without full outlines yet)
        """
        theme_section = ""
        if themes:
            theme_section = f"Incorporate these themes/elements: {', '.join(themes)}"

        avoid_section = self._build_avoid_section(
            avoid_titles=avoid_titles,
            avoid_loglines=avoid_loglines,
            rejected_loglines=rejected_loglines,
        )

        prompt = CONCEPT_GENERATION_PROMPT.format(
            count=count,
            theme_section=theme_section,
            avoid_section=avoid_section,
        )

        response = self.client.generate(
            prompt,
            system_instruction=CONCEPT_SYSTEM_INSTRUCTION,
            temperature=0.9,  # Higher creativity for concepts
        )

        # Parse JSON from response
        concepts_data = parse_json_response(response)

        concepts = []
        for data in concepts_data:
            concept = StoryConcept(
                title=data.get("title", "Untitled"),
                logline=data.get("logline", ""),
                synopsis=data.get("synopsis", ""),
                genre_tags=data.get("genre_tags", []),
                themes=data.get("themes", []),
            )
            concepts.append(concept)

        return concepts

    def expand_to_outline(
        self,
        concept: StoryConcept,
        num_chapters: int = 12,
    ) -> StoryConcept:
        """Expand a concept into a full outline with world and characters.

        Args:
            concept: The story concept to expand
            num_chapters: Target number of chapters

        Returns:
            Updated StoryConcept with world, characters, and chapter outlines
        """
        prompt = OUTLINE_EXPANSION_PROMPT.format(
            title=concept.title,
            logline=concept.logline,
            synopsis=concept.synopsis,
            themes=", ".join(concept.themes),
            num_chapters=num_chapters,
        )

        response = self.client.generate(
            prompt,
            system_instruction=OUTLINE_SYSTEM_INSTRUCTION,
            temperature=0.7,  # Slightly lower for more coherent structure
        )

        outline_data = parse_json_response(response)

        # Handle both list and dict responses
        if isinstance(outline_data, list):
            outline_data = outline_data[0] if outline_data else {}

        # Parse world details
        world_data = outline_data.get("world", {})
        concept.world = WorldDetails(
            setting=world_data.get("setting", ""),
            time_period=world_data.get("time_period", ""),
            technology_level=world_data.get("technology_level", ""),
            society=world_data.get("society", ""),
            key_locations=world_data.get("key_locations", []),
            rules=world_data.get("rules", []),
            history=world_data.get("history", ""),
        )

        # Parse characters
        concept.characters = []
        for char_data in outline_data.get("characters", []):
            relationships = self._normalize_relationships(char_data.get("relationships", []))

            character = Character(
                name=char_data.get("name", "Unknown"),
                role=char_data.get("role", "supporting"),
                description=char_data.get("description", ""),
                motivation=char_data.get("motivation", ""),
                arc=char_data.get("arc", ""),
                relationships=relationships,
            )
            concept.characters.append(character)

        # Parse chapter outlines
        concept.chapter_outlines = []
        for ch_data in outline_data.get("chapter_outlines", []):
            chapter = ChapterOutline(
                number=ch_data.get("number", len(concept.chapter_outlines) + 1),
                title=ch_data.get("title", f"Chapter {len(concept.chapter_outlines) + 1}"),
                summary=ch_data.get("summary", ""),
                key_events=ch_data.get("key_events", []),
                characters_involved=ch_data.get("characters_involved", []),
                location=ch_data.get("location", ""),
                emotional_arc=ch_data.get("emotional_arc", ""),
                chapter_goal=ch_data.get("chapter_goal", ""),
            )
            concept.chapter_outlines.append(chapter)

        concept.target_chapters = num_chapters

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
            Revised StoryConcept
        """
        revision_prompt = f"""Revise this story concept based on the user's feedback.

USER'S REQUESTED CHANGES:
{user_feedback}

CURRENT CONCEPT:
Title: {concept.title}
Logline: {concept.logline}
Synopsis: {concept.synopsis}
Themes: {', '.join(concept.themes)}
Genre Tags: {', '.join(concept.genre_tags)}

Apply the user's requested changes while maintaining the overall quality and coherence.
If the user's feedback is vague, interpret it creatively while staying true to the spirit of their request.

Provide the revised concept in JSON format:
{{
    "title": "...",
    "logline": "...",
    "synopsis": "...",
    "themes": [...],
    "genre_tags": [...]
}}"""

        response = self.client.generate(
            revision_prompt,
            system_instruction=CONCEPT_SYSTEM_INSTRUCTION,
            temperature=0.8,
        )

        data = parse_json_response(response)
        if isinstance(data, list):
            data = data[0] if data else {}

        concept.title = data.get("title", concept.title)
        concept.logline = data.get("logline", concept.logline)
        concept.synopsis = data.get("synopsis", concept.synopsis)
        concept.themes = data.get("themes", concept.themes)
        concept.genre_tags = data.get("genre_tags", concept.genre_tags)

        return concept

    def revise_concept(
        self,
        concept: StoryConcept,
        issues: list[str],
    ) -> StoryConcept:
        """Revise a concept based on review feedback.

        Args:
            concept: Concept to revise
            issues: List of issues to address

        Returns:
            Revised StoryConcept
        """
        revision_prompt = f"""Revise this story concept to address the following issues:

ISSUES TO FIX:
{chr(10).join(f"- {issue}" for issue in issues)}

ORIGINAL CONCEPT:
Title: {concept.title}
Logline: {concept.logline}
Synopsis: {concept.synopsis}
Themes: {', '.join(concept.themes)}
Genre Tags: {', '.join(concept.genre_tags)}

Provide the revised concept in JSON format:
{{
    "title": "...",
    "logline": "...",
    "synopsis": "...",
    "themes": [...],
    "genre_tags": [...]
}}

Maintain the core appeal while fixing the identified issues."""

        response = self.client.generate(
            revision_prompt,
            system_instruction=CONCEPT_SYSTEM_INSTRUCTION,
            temperature=0.7,
        )

        data = parse_json_response(response)
        if isinstance(data, list):
            data = data[0] if data else {}

        concept.title = data.get("title", concept.title)
        concept.logline = data.get("logline", concept.logline)
        concept.synopsis = data.get("synopsis", concept.synopsis)
        concept.themes = data.get("themes", concept.themes)
        concept.genre_tags = data.get("genre_tags", concept.genre_tags)

        return concept

    def revise_outline(
        self,
        concept: StoryConcept,
        issues: list[str],
    ) -> StoryConcept:
        """Revise an outline based on review feedback.

        Args:
            concept: Concept with outline to revise
            issues: List of issues to address

        Returns:
            StoryConcept with revised outline
        """
        characters_str = "\n".join(
            f"- {c.name} ({c.role}): {c.description}"
            for c in concept.characters
        )
        chapters_str = "\n".join(
            f"Chapter {ch.number}: {ch.title} - {ch.summary}"
            for ch in concept.chapter_outlines
        )

        revision_prompt = f"""Revise this story outline to address the following issues:

ISSUES TO FIX:
{chr(10).join(f"- {issue}" for issue in issues)}

CURRENT OUTLINE:
Title: {concept.title}
Logline: {concept.logline}

Characters:
{characters_str}

Chapters:
{chapters_str}

Provide the revised outline in the same JSON structure:
{{
    "world": {{...}},
    "characters": [...],
    "chapter_outlines": [...]
}}

Keep what works, fix what doesn't. Maintain the target of {concept.target_chapters} chapters."""

        response = self.client.generate(
            revision_prompt,
            system_instruction=OUTLINE_SYSTEM_INSTRUCTION,
            temperature=0.7,
        )

        outline_data = parse_json_response(response)
        if isinstance(outline_data, list):
            outline_data = outline_data[0] if outline_data else {}

        # Update world if provided
        if "world" in outline_data:
            world_data = outline_data["world"]
            concept.world = WorldDetails(
                setting=world_data.get("setting", concept.world.setting if concept.world else ""),
                time_period=world_data.get("time_period", concept.world.time_period if concept.world else ""),
                technology_level=world_data.get("technology_level", concept.world.technology_level if concept.world else ""),
                society=world_data.get("society", concept.world.society if concept.world else ""),
                key_locations=world_data.get("key_locations", concept.world.key_locations if concept.world else []),
                rules=world_data.get("rules", concept.world.rules if concept.world else []),
                history=world_data.get("history", concept.world.history if concept.world else ""),
            )

        # Update characters if provided
        if "characters" in outline_data:
            concept.characters = []
            for char_data in outline_data["characters"]:
                relationships = self._normalize_relationships(char_data.get("relationships", []))

                character = Character(
                    name=char_data.get("name", "Unknown"),
                    role=char_data.get("role", "supporting"),
                    description=char_data.get("description", ""),
                    motivation=char_data.get("motivation", ""),
                    arc=char_data.get("arc", ""),
                    relationships=relationships,
                )
                concept.characters.append(character)

        # Update chapter outlines if provided
        if "chapter_outlines" in outline_data:
            concept.chapter_outlines = []
            for ch_data in outline_data["chapter_outlines"]:
                chapter = ChapterOutline(
                    number=ch_data.get("number", len(concept.chapter_outlines) + 1),
                    title=ch_data.get("title", f"Chapter {len(concept.chapter_outlines) + 1}"),
                    summary=ch_data.get("summary", ""),
                    key_events=ch_data.get("key_events", []),
                    characters_involved=ch_data.get("characters_involved", []),
                    location=ch_data.get("location", ""),
                    emotional_arc=ch_data.get("emotional_arc", ""),
                    chapter_goal=ch_data.get("chapter_goal", ""),
                )
                concept.chapter_outlines.append(chapter)

        return concept

    def generate_characters(
        self,
        concept: StoryConcept,
        num_characters: int = 4,
        avoid_names: Optional[list[str]] = None,
    ) -> list[Character]:
        """Generate major characters for a story concept.

        Args:
            concept: The story concept
            num_characters: Number of characters to generate
            avoid_names: Previously used character names to avoid

        Returns:
            List of Character objects
        """
        avoid_section = ""
        if avoid_names:
            # Limit to most recent names to keep prompt reasonable
            recent_names = avoid_names[-MAX_AVOID_NAMES:]
            avoid_section = (
                f"\nIMPORTANT: Do NOT use these character names (they were used in previous stories): "
                f"{', '.join(recent_names)}\n"
                f"Create fresh, original names that feel different from these."
            )

        prompt = CHARACTER_GENERATION_PROMPT.format(
            title=concept.title,
            logline=concept.logline,
            synopsis=concept.synopsis,
            themes=", ".join(concept.themes),
            num_characters=num_characters,
            avoid_section=avoid_section,
        )

        response = self.client.generate(
            prompt,
            system_instruction=CHARACTER_SYSTEM_INSTRUCTION,
            temperature=0.85,
        )

        characters_data = parse_json_response(response)
        if isinstance(characters_data, dict):
            characters_data = [characters_data]

        characters = []
        for char_data in characters_data:
            relationships = self._normalize_relationships(char_data.get("relationships", []))

            character = Character(
                name=char_data.get("name", "Unknown"),
                role=char_data.get("role", "supporting"),
                description=char_data.get("description", ""),
                motivation=char_data.get("motivation", ""),
                arc=char_data.get("arc", ""),
                relationships=relationships,
            )
            characters.append(character)

        return characters

    def regenerate_character(
        self,
        concept: StoryConcept,
        character_index: int,
        user_feedback: Optional[str] = None,
    ) -> Character:
        """Regenerate a specific character, optionally with user feedback.

        Args:
            concept: The story concept (with existing characters)
            character_index: Index of the character to regenerate
            user_feedback: Optional feedback for how to change the character

        Returns:
            New Character object
        """
        if character_index >= len(concept.characters):
            raise ValueError(f"Character index {character_index} out of range")

        old_char = concept.characters[character_index]

        # Build context of other characters
        other_chars = [c for i, c in enumerate(concept.characters) if i != character_index]
        other_characters_str = "\n".join(
            f"- {c.name} ({c.role}): {c.description}"
            for c in other_chars
        ) if other_chars else "No other characters yet"

        if user_feedback:
            # Use revision prompt with user feedback
            prompt = CHARACTER_REVISE_PROMPT.format(
                title=concept.title,
                logline=concept.logline,
                themes=", ".join(concept.themes),
                char_name=old_char.name,
                char_role=old_char.role,
                char_description=old_char.description,
                char_motivation=old_char.motivation,
                char_arc=old_char.arc,
                user_feedback=user_feedback,
                other_characters=other_characters_str,
            )
            temperature = 0.8
        else:
            # Use regenerate prompt for fresh take
            prompt = CHARACTER_REGENERATE_PROMPT.format(
                title=concept.title,
                logline=concept.logline,
                themes=", ".join(concept.themes),
                char_name=old_char.name,
                char_role=old_char.role,
                char_description=old_char.description,
                other_characters=other_characters_str,
            )
            temperature = 0.9

        response = self.client.generate(
            prompt,
            system_instruction=CHARACTER_SYSTEM_INSTRUCTION,
            temperature=temperature,
        )

        char_data = parse_json_response(response)
        if isinstance(char_data, list):
            char_data = char_data[0] if char_data else {}

        relationships = self._normalize_relationships(char_data.get("relationships", []))

        return Character(
            name=char_data.get("name", "Unknown"),
            role=char_data.get("role", old_char.role),
            description=char_data.get("description", ""),
            motivation=char_data.get("motivation", ""),
            arc=char_data.get("arc", ""),
            relationships=relationships,
        )

    def _build_avoid_section(
        self,
        avoid_titles: Optional[list[str]] = None,
        avoid_loglines: Optional[list[str]] = None,
        rejected_loglines: Optional[list[str]] = None,
    ) -> str:
        """Build the avoidance section for concept prompts.

        Args:
            avoid_titles: Previously used titles to avoid
            avoid_loglines: Previously used loglines to avoid similarity to
            rejected_loglines: Loglines the user explicitly rejected (must avoid)

        Returns:
            Formatted string for prompt, or empty string if nothing to avoid
        """
        parts = []

        if avoid_titles:
            # Limit to most recent to keep prompt reasonable
            recent_titles = avoid_titles[-MAX_AVOID_TITLES:]
            parts.append(
                f"IMPORTANT: Do NOT use or closely resemble these previously used titles: "
                f"{', '.join(recent_titles)}"
            )

        if avoid_loglines:
            # Just use a few recent loglines as examples of premises to avoid
            recent_loglines = avoid_loglines[-MAX_AVOID_LOGLINES:]
            parts.append(
                f"Create concepts with DIFFERENT premises from these recent stories:\n"
                + "\n".join(f"- {ll}" for ll in recent_loglines)
            )

        if rejected_loglines:
            # These are concepts the user explicitly rejected - must avoid completely
            parts.append(
                f"CRITICAL: The user has REJECTED these story concepts. Do NOT generate anything similar:\n"
                + "\n".join(f"- {ll}" for ll in rejected_loglines)
            )

        if parts:
            return "\n\n".join(parts) + "\n\nGenerate fresh, original concepts."
        return ""

    def _normalize_relationships(self, relationships) -> list[str]:
        """Normalize relationships to a list of strings.

        The LLM may return relationships as:
        - A string (single relationship)
        - A list of strings
        - A list of dicts with character/description keys

        Args:
            relationships: Raw relationships data from LLM

        Returns:
            List of relationship strings
        """
        if not relationships:
            return []

        if isinstance(relationships, str):
            return [relationships]

        if isinstance(relationships, list):
            normalized = []
            for item in relationships:
                if isinstance(item, str):
                    normalized.append(item)
                elif isinstance(item, dict):
                    # Extract meaningful info from dict
                    char_name = item.get("character", item.get("name", ""))
                    description = item.get("description", item.get("relationship", ""))
                    if char_name and description:
                        normalized.append(f"{char_name}: {description}")
                    elif char_name:
                        normalized.append(char_name)
                    elif description:
                        normalized.append(description)
            return normalized

        return []

