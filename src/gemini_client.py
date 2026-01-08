"""Gemini API client wrapper with retry logic and context management."""

import time
from pathlib import Path
from typing import Optional

from google import genai
from google.genai import types

from .models import GenerationLog

# Model for image generation (Nano Banana 2)
IMAGE_MODEL = "gemini-2.5-flash-image"


class GeminiClient:
    """Wrapper for Google Gemini API with retry logic."""

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.0-flash",
        default_temperature: float = 0.8,
    ):
        """Initialize the Gemini client.

        Args:
            api_key: Google API key for Gemini
            model: Model name to use (e.g., gemini-2.0-flash, gemini-1.5-pro)
            default_temperature: Default temperature for generation
        """
        self.client = genai.Client(api_key=api_key)
        self.model_name = model
        self.default_temperature = default_temperature
        self.logs: list[GenerationLog] = []

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
        max_retries: int = 3,
    ) -> str:
        """Generate text from a prompt.

        Args:
            prompt: The user prompt
            system_instruction: Optional system instruction
            temperature: Temperature for this generation (uses default if None)
            max_retries: Maximum retry attempts on failure

        Returns:
            Generated text response
        """
        temp = temperature if temperature is not None else self.default_temperature

        # Build generation config
        config = types.GenerateContentConfig(
            temperature=temp,
            system_instruction=system_instruction,
        )

        last_error = None
        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=self.model_name,
                    contents=prompt,
                    config=config,
                )

                result = response.text

                # Log successful generation
                self.logs.append(
                    GenerationLog(
                        action="generate",
                        prompt_summary=prompt[:100] + "..." if len(prompt) > 100 else prompt,
                        response_length=len(result),
                        model=self.model_name,
                        temperature=temp,
                        success=True,
                    )
                )

                return result

            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # Check for rate limiting
                if "resource" in error_str or "quota" in error_str or "rate" in error_str:
                    wait_time = 2 ** attempt * 10  # Exponential backoff: 10s, 20s, 40s
                    print(f"Rate limited. Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                elif attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"API error: {e}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)

        # Log failed generation
        self.logs.append(
            GenerationLog(
                action="generate",
                prompt_summary=prompt[:100] + "..." if len(prompt) > 100 else prompt,
                response_length=0,
                model=self.model_name,
                temperature=temp,
                success=False,
                error=str(last_error),
            )
        )

        raise RuntimeError(f"Failed to generate after {max_retries} attempts: {last_error}")

    def generate_with_context(
        self,
        prompt: str,
        context: list[str],
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Generate text with additional context prepended.

        Args:
            prompt: The main prompt
            context: List of context strings to prepend
            system_instruction: Optional system instruction
            temperature: Temperature for generation

        Returns:
            Generated text response
        """
        full_prompt = "\n\n".join(context) + "\n\n" + prompt
        return self.generate(
            full_prompt,
            system_instruction=system_instruction,
            temperature=temperature,
        )

    def generate_structured(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
    ) -> str:
        """Generate text expected to contain structured data (JSON).

        Uses lower temperature for more consistent output.

        Args:
            prompt: The prompt requesting structured output
            system_instruction: Optional system instruction
            temperature: Temperature (defaults to 0.3 for structured)

        Returns:
            Generated text response
        """
        temp = temperature if temperature is not None else 0.3
        return self.generate(
            prompt,
            system_instruction=system_instruction,
            temperature=temp,
        )

    def generate_image(
        self,
        prompt: str,
        output_path: Path,
        aspect_ratio: str = "2:3",
        max_retries: int = 3,
    ) -> Path:
        """Generate an image using Nano Banana 2 (Gemini 2.5 Flash Image).

        Args:
            prompt: Text prompt describing the image to generate
            output_path: Path to save the generated image
            aspect_ratio: Aspect ratio (e.g., "2:3" for book covers, "16:9" for wide)
            max_retries: Maximum retry attempts on failure

        Returns:
            Path to the saved image

        Raises:
            RuntimeError: If image generation fails after all retries
        """
        config = types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
        )

        last_error = None
        for attempt in range(max_retries):
            try:
                response = self.client.models.generate_content(
                    model=IMAGE_MODEL,
                    contents=prompt,
                    config=config,
                )

                # Extract and save the image
                for part in response.parts:
                    if part.inline_data is not None:
                        image = part.as_image()
                        image.save(output_path)

                        # Log successful generation
                        self.logs.append(
                            GenerationLog(
                                action="generate_image",
                                prompt_summary=prompt[:100] + "..." if len(prompt) > 100 else prompt,
                                response_length=0,
                                model=IMAGE_MODEL,
                                temperature=0.0,
                                success=True,
                            )
                        )

                        return output_path

                raise RuntimeError("No image data in response")

            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                if "resource" in error_str or "quota" in error_str or "rate" in error_str:
                    wait_time = 2 ** attempt * 10
                    print(f"Rate limited. Waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                elif attempt < max_retries - 1:
                    wait_time = 2 ** attempt
                    print(f"API error: {e}. Retrying in {wait_time}s...")
                    time.sleep(wait_time)

        # Log failed generation
        self.logs.append(
            GenerationLog(
                action="generate_image",
                prompt_summary=prompt[:100] + "..." if len(prompt) > 100 else prompt,
                response_length=0,
                model=IMAGE_MODEL,
                temperature=0.0,
                success=False,
                error=str(last_error),
            )
        )

        raise RuntimeError(f"Failed to generate image after {max_retries} attempts: {last_error}")

    def count_tokens(self, text: str) -> int:
        """Count tokens in a text string.

        Args:
            text: Text to count tokens for

        Returns:
            Token count
        """
        response = self.client.models.count_tokens(
            model=self.model_name,
            contents=text,
        )
        return response.total_tokens

    def get_logs(self) -> list[GenerationLog]:
        """Get all generation logs."""
        return self.logs.copy()

    def clear_logs(self) -> None:
        """Clear generation logs."""
        self.logs.clear()
