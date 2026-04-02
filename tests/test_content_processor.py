"""Tests for the content processor AI pipeline."""

import pytest

from ai_processing.content_processor import (
    BIAS_DETECTION_PROMPT,
    CONTENT_PROCESSOR_PERSONA,
    GRAMMAR_CHECK_PROMPT,
    UDL_ENHANCEMENT_PROMPT,
    ContentProcessor,
)


class TestPrompts:
    """Verify that system prompts contain required guidelines."""

    def test_persona_no_ai_signals(self):
        assert "NOT an AI assistant" in CONTENT_PROCESSOR_PERSONA
        assert "Never reveal" in CONTENT_PROCESSOR_PERSONA

    def test_persona_scientific_tone(self):
        assert "Scientific tone" in CONTENT_PROCESSOR_PERSONA

    def test_persona_no_bias(self):
        assert "No bias" in CONTENT_PROCESSOR_PERSONA
        assert "inclusive" in CONTENT_PROCESSOR_PERSONA

    def test_persona_udl_compliance(self):
        assert "UDL" in CONTENT_PROCESSOR_PERSONA
        assert "Multiple means of representation" in CONTENT_PROCESSOR_PERSONA
        assert "Multiple means of engagement" in CONTENT_PROCESSOR_PERSONA
        assert "Multiple means of action" in CONTENT_PROCESSOR_PERSONA

    def test_grammar_preserves_human_voice(self):
        prompt = GRAMMAR_CHECK_PROMPT.format(language="English")
        assert "NOT make the text sound AI-generated" in prompt
        assert "human writing patterns" in prompt

    def test_bias_detection_covers_dimensions(self):
        assert "Gender bias" in BIAS_DETECTION_PROMPT
        assert "Cultural/racial bias" in BIAS_DETECTION_PROMPT
        assert "Socioeconomic bias" in BIAS_DETECTION_PROMPT
        assert "Ability bias" in BIAS_DETECTION_PROMPT

    def test_udl_enhancement_elements(self):
        assert "REPRESENTATION" in UDL_ENHANCEMENT_PROMPT
        assert "ENGAGEMENT" in UDL_ENHANCEMENT_PROMPT
        assert "ACTION/EXPRESSION" in UDL_ENHANCEMENT_PROMPT


class TestContentProcessorInit:
    """Test ContentProcessor initialization (without Vertex AI)."""

    def test_parse_json_safe_valid(self):
        processor = ContentProcessor.__new__(ContentProcessor)
        result = processor._parse_json_safe('{"score": 85, "issues": []}')
        assert result["score"] == 85
        assert result["issues"] == []

    def test_parse_json_safe_with_markdown(self):
        processor = ContentProcessor.__new__(ContentProcessor)
        text = '```json\n{"score": 90, "issues": []}\n```'
        result = processor._parse_json_safe(text)
        assert result["score"] == 90

    def test_parse_json_safe_invalid(self):
        processor = ContentProcessor.__new__(ContentProcessor)
        result = processor._parse_json_safe("not json at all")
        assert "raw_response" in result
        assert result["overall_score"] == -1
