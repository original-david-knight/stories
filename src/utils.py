"""Shared utility functions for the story generator."""

import json
import re
from typing import Union


def parse_json_response(response: str) -> Union[dict, list]:
    """Parse JSON from a response that may contain markdown or extra text.

    Handles common LLM response patterns:
    - JSON wrapped in markdown code blocks (```json ... ```)
    - JSON with surrounding text/preamble
    - Both array and object responses

    Args:
        response: Raw response text from the model

    Returns:
        Parsed JSON data as dict or list

    Raises:
        ValueError: If no valid JSON can be extracted
    """
    # Try to extract JSON from markdown code blocks
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", response)
    if json_match:
        json_str = json_match.group(1).strip()
    else:
        json_str = response.strip()

    # Find the start of JSON array or object
    array_idx = json_str.find("[")
    object_idx = json_str.find("{")

    if array_idx == -1 and object_idx == -1:
        raise ValueError(f"Could not find JSON in response: {response[:200]}")

    # Determine which comes first
    if array_idx == -1:
        start_idx = object_idx
        start_char = "{"
        end_char = "}"
    elif object_idx == -1:
        start_idx = array_idx
        start_char = "["
        end_char = "]"
    else:
        start_idx = min(array_idx, object_idx)
        start_char = json_str[start_idx]
        end_char = "]" if start_char == "[" else "}"

    json_str = json_str[start_idx:]

    # Find matching end bracket
    depth = 0
    end_idx = 0
    for i, char in enumerate(json_str):
        if char in "[{":
            depth += 1
        elif char in "]}":
            depth -= 1
            if depth == 0:
                end_idx = i + 1
                break

    json_str = json_str[:end_idx]

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON: {e}\nResponse: {json_str[:500]}")


def parse_json_response_safe(
    response: str,
    default: Union[dict, list, None] = None,
) -> Union[dict, list]:
    """Parse JSON from response, returning a default on failure.

    A safe version of parse_json_response that never raises exceptions.
    Useful for review parsing where failures should be handled gracefully.

    Args:
        response: Raw response text from the model
        default: Default value to return on parse failure.
                 If None, returns {"issues": [], "strengths": [], "overall_quality": "unknown"}

    Returns:
        Parsed JSON data or default value
    """
    if default is None:
        default = {"issues": [], "strengths": [], "overall_quality": "unknown"}

    try:
        return parse_json_response(response)
    except (ValueError, json.JSONDecodeError):
        return default
