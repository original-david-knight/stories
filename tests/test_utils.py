"""Tests for utility functions."""

import pytest

from src.utils import parse_json_response, parse_json_response_safe


class TestParseJsonResponse:
    """Tests for the parse_json_response function."""

    def test_parse_simple_object(self):
        """Test parsing a simple JSON object."""
        response = '{"key": "value", "number": 42}'
        result = parse_json_response(response)
        assert result == {"key": "value", "number": 42}

    def test_parse_simple_array(self):
        """Test parsing a simple JSON array."""
        response = '[{"id": 1}, {"id": 2}]'
        result = parse_json_response(response)
        assert result == [{"id": 1}, {"id": 2}]

    def test_parse_json_in_markdown_code_block(self):
        """Test parsing JSON wrapped in markdown code blocks."""
        response = '''Here is the result:
```json
{"title": "Test", "value": 123}
```
That's the output.'''
        result = parse_json_response(response)
        assert result == {"title": "Test", "value": 123}

    def test_parse_json_in_markdown_without_language(self):
        """Test parsing JSON in code block without language specifier."""
        response = '''```
{"items": ["a", "b", "c"]}
```'''
        result = parse_json_response(response)
        assert result == {"items": ["a", "b", "c"]}

    def test_parse_json_with_preamble(self):
        """Test parsing JSON with text before it."""
        response = 'Here is the JSON output: {"result": true}'
        result = parse_json_response(response)
        assert result == {"result": true}

    def test_parse_json_with_postamble(self):
        """Test parsing JSON with text after it."""
        response = '{"status": "ok"} That concludes the response.'
        result = parse_json_response(response)
        assert result == {"status": "ok"}

    def test_parse_nested_json(self):
        """Test parsing nested JSON structures."""
        response = '''{"outer": {"inner": {"deep": "value"}}, "array": [1, 2, 3]}'''
        result = parse_json_response(response)
        assert result["outer"]["inner"]["deep"] == "value"
        assert result["array"] == [1, 2, 3]

    def test_parse_array_of_objects(self):
        """Test parsing array of objects (common for concept generation)."""
        response = '''[
            {"title": "Story 1", "logline": "First story"},
            {"title": "Story 2", "logline": "Second story"}
        ]'''
        result = parse_json_response(response)
        assert len(result) == 2
        assert result[0]["title"] == "Story 1"
        assert result[1]["logline"] == "Second story"

    def test_parse_review_response_format(self):
        """Test parsing the typical review response format."""
        response = '''```json
{
    "overall_quality": "good",
    "strengths": ["Strong pacing", "Vivid descriptions"],
    "issues": [
        {
            "category": "continuity",
            "severity": "medium",
            "location": "Chapter 3",
            "description": "Timeline inconsistency",
            "suggestion": "Fix the dates"
        }
    ]
}
```'''
        result = parse_json_response(response)
        assert result["overall_quality"] == "good"
        assert len(result["strengths"]) == 2
        assert len(result["issues"]) == 1
        assert result["issues"][0]["severity"] == "medium"

    def test_parse_json_with_escaped_characters(self):
        """Test parsing JSON with escaped quotes and newlines."""
        response = '{"text": "He said \\"hello\\"", "multiline": "line1\\nline2"}'
        result = parse_json_response(response)
        assert result["text"] == 'He said "hello"'
        assert result["multiline"] == "line1\nline2"

    def test_raises_on_no_json(self):
        """Test that ValueError is raised when no JSON is found."""
        response = "This is just plain text with no JSON at all."
        with pytest.raises(ValueError, match="Could not find JSON"):
            parse_json_response(response)

    def test_raises_on_invalid_json(self):
        """Test that ValueError is raised for malformed JSON."""
        response = '{"key": "value", "broken": }'
        with pytest.raises(ValueError, match="Failed to parse JSON"):
            parse_json_response(response)

    def test_raises_on_unclosed_braces(self):
        """Test handling of unclosed braces."""
        response = '{"key": "value"'
        with pytest.raises(ValueError):
            parse_json_response(response)


class TestParseJsonResponseSafe:
    """Tests for the parse_json_response_safe function."""

    def test_returns_parsed_json_on_success(self):
        """Test that valid JSON is parsed correctly."""
        response = '{"status": "success"}'
        result = parse_json_response_safe(response)
        assert result == {"status": "success"}

    def test_returns_default_on_invalid_json(self):
        """Test that default is returned for invalid JSON."""
        response = "not valid json at all"
        result = parse_json_response_safe(response)
        assert result == {"issues": [], "strengths": [], "overall_quality": "unknown"}

    def test_returns_custom_default(self):
        """Test that custom default is returned on failure."""
        response = "invalid"
        custom_default = {"custom": "default"}
        result = parse_json_response_safe(response, default=custom_default)
        assert result == {"custom": "default"}

    def test_returns_default_on_empty_response(self):
        """Test handling of empty response."""
        result = parse_json_response_safe("")
        assert "issues" in result
        assert result["issues"] == []

    def test_handles_malformed_json_gracefully(self):
        """Test that malformed JSON doesn't raise exceptions."""
        response = '{"broken": '
        result = parse_json_response_safe(response)
        assert result["overall_quality"] == "unknown"

    def test_handles_markdown_with_invalid_json(self):
        """Test handling of markdown code blocks with invalid JSON."""
        response = '''```json
{this is not: valid json}
```'''
        result = parse_json_response_safe(response)
        assert "issues" in result


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_object(self):
        """Test parsing empty object."""
        result = parse_json_response("{}")
        assert result == {}

    def test_empty_array(self):
        """Test parsing empty array."""
        result = parse_json_response("[]")
        assert result == []

    def test_json_with_unicode(self):
        """Test parsing JSON with unicode characters."""
        response = '{"name": "José García", "emoji": "🚀"}'
        result = parse_json_response(response)
        assert result["name"] == "José García"
        assert result["emoji"] == "🚀"

    def test_json_with_numbers(self):
        """Test parsing various number formats."""
        response = '{"int": 42, "float": 3.14, "negative": -10, "scientific": 1.5e10}'
        result = parse_json_response(response)
        assert result["int"] == 42
        assert result["float"] == 3.14
        assert result["negative"] == -10
        assert result["scientific"] == 1.5e10

    def test_json_with_booleans_and_null(self):
        """Test parsing booleans and null."""
        response = '{"active": true, "deleted": false, "data": null}'
        result = parse_json_response(response)
        assert result["active"] is True
        assert result["deleted"] is False
        assert result["data"] is None

    def test_whitespace_handling(self):
        """Test that whitespace is handled correctly."""
        response = '''

        {
            "key"  :   "value"
        }

        '''
        result = parse_json_response(response)
        assert result == {"key": "value"}

    def test_multiple_json_objects_takes_first(self):
        """Test that when multiple JSON objects exist, the first is taken."""
        response = '{"first": 1} {"second": 2}'
        result = parse_json_response(response)
        assert result == {"first": 1}

    def test_nested_code_blocks(self):
        """Test handling of content that might look like nested code blocks."""
        response = '''```json
{"code": "```python\\nprint('hello')\\n```"}
```'''
        result = parse_json_response(response)
        assert "code" in result
