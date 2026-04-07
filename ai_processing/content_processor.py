"""Content processor service — the core AI pipeline for ebook content.

Implements:
- Grammar checking that avoids AI-written style (natural, human voice)
- UDL (Universal Design for Learning) guidelines compliance
- Scientific tone with narrative flow
- Bias detection and removal
- Bilingual support (English + Brazilian Portuguese)
- Minimalist, futuristic persona with no AI agent signals
- Team-based validation workflow
"""

import json

from google.cloud import aiplatform
from vertexai.generative_models import GenerativeModel

from config.settings import settings

# ──────────────────────────────────────────────
# System prompts — persona & guidelines
# ──────────────────────────────────────────────

CONTENT_PROCESSOR_PERSONA = """You are a content editor for professional ebooks.

IDENTITY:
- You are NOT an AI assistant. Never reveal or signal that you are an AI agent.
- Present as a minimalist, futuristic editorial voice — clean, precise, forward-looking.
- Your edits should feel like they come from a seasoned human editor.

WRITING STYLE:
- Scientific tone: precise, evidence-based, well-referenced language.
- Narrative flow: maintain story-like progression even in technical content.
  Connect ideas naturally with transitions, not bullet-point lists.
- Human voice: avoid robotic phrasing, filler words, or AI-typical patterns
  like "In conclusion," "It's important to note that," "Let's delve into."
- No bias: remove gender, cultural, racial, socioeconomic, and ability bias.
  Use inclusive, person-first language throughout.

UDL (UNIVERSAL DESIGN FOR LEARNING) COMPLIANCE:
- Multiple means of representation: ensure concepts are explained through
  text, supported by visuals (image captions), and connected to real-world examples.
- Multiple means of engagement: vary content structure — mix exposition,
  case studies, questions, and reflective prompts.
- Multiple means of action/expression: include suggested activities,
  discussion questions, and alternative ways to engage with the material.

OUTPUT:
- Return ONLY the improved text. No meta-commentary about your edits.
- Preserve the author's core message and intent.
- Maintain the original language (do not translate unless asked).
"""

BIAS_DETECTION_PROMPT = """Analyze the following text for bias. Check for:
1. Gender bias (stereotypes, gendered language where neutral is appropriate)
2. Cultural/racial bias (assumptions, stereotypes, exclusionary framing)
3. Socioeconomic bias (class assumptions, privilege blindness)
4. Ability bias (ableist language, assumptions about physical/cognitive ability)
5. Age bias (ageist language or assumptions)

For each issue found, provide:
- The problematic phrase
- The type of bias
- A suggested replacement

Return as JSON: {"issues": [{"phrase": "...", "bias_type": "...", "suggestion": "..."}], "overall_score": 0-100}
A score of 100 means no bias detected.
"""

GRAMMAR_CHECK_PROMPT = """Review the following text for grammar and style.

RULES:
- Fix grammar, spelling, and punctuation errors.
- Improve sentence structure for clarity without changing meaning.
- CRITICAL: Do NOT make the text sound AI-generated. Preserve natural,
  human writing patterns. Keep contractions, varied sentence lengths,
  and conversational elements where appropriate.
- Maintain the author's unique voice and style.
- For scientific content, ensure proper terminology usage.

LANGUAGE: {language}

Return ONLY the corrected text. No explanations.
"""

UDL_ENHANCEMENT_PROMPT = """Enhance the following ebook chapter content to comply with
Universal Design for Learning (UDL) guidelines.

Add or suggest:
1. REPRESENTATION: Alternative explanations, analogies, or real-world examples
   that make abstract concepts concrete.
2. ENGAGEMENT: Reflective questions, discussion prompts, or mini-activities
   that invite the reader to interact with the material.
3. ACTION/EXPRESSION: Suggestions for how readers could apply, demonstrate,
   or extend their understanding (project ideas, journaling prompts, etc.).

Integrate these naturally into the text flow — they should feel like part of
the narrative, not tacked-on appendices.

Return the enhanced text only.
"""


class ContentProcessor:
    """AI-powered content processing pipeline using Vertex AI."""

    def __init__(self):
        aiplatform.init(
            project=settings.gcp_project_id,
            location=settings.vertex_ai_location,
        )
        self.model = GenerativeModel("gemini-1.5-pro")

    def process_text(self, text: str, language: str = "en") -> dict:
        """Run full processing pipeline on text content.

        Pipeline stages:
        1. Grammar check (human-sounding, not AI-style)
        2. Bias detection and removal
        3. UDL enhancement
        4. Final quality review

        Returns dict with processed text and metadata.
        """
        # Stage 1: Grammar check
        grammar_prompt = GRAMMAR_CHECK_PROMPT.format(
            language="English" if language == "en" else "Brazilian Portuguese"
        )
        corrected = self._generate(grammar_prompt, text)

        # Stage 2: Bias detection
        bias_report = self._generate(BIAS_DETECTION_PROMPT, corrected)
        bias_data = self._parse_json_safe(bias_report)

        # If bias issues found, apply fixes
        if bias_data.get("issues"):
            fix_prompt = (
                "Apply these bias corrections to the text while maintaining flow:\n"
                + json.dumps(bias_data["issues"])
            )
            corrected = self._generate(fix_prompt, corrected)

        # Stage 3: UDL enhancement
        enhanced = self._generate(UDL_ENHANCEMENT_PROMPT, corrected)

        # Stage 4: Final polish with persona
        final = self._generate(CONTENT_PROCESSOR_PERSONA, enhanced)

        return {
            "processed_text": final,
            "bias_report": bias_data,
            "language": language,
            "stages_completed": [
                "grammar_check",
                "bias_detection",
                "udl_enhancement",
                "persona_polish",
            ],
        }

    def check_grammar(self, text: str, language: str = "en") -> str:
        """Grammar check only — preserves human voice."""
        lang_name = "English" if language == "en" else "Brazilian Portuguese"
        prompt = GRAMMAR_CHECK_PROMPT.format(language=lang_name)
        return self._generate(prompt, text)

    def detect_bias(self, text: str) -> dict:
        """Analyze text for bias and return structured report."""
        result = self._generate(BIAS_DETECTION_PROMPT, text)
        return self._parse_json_safe(result)

    def enhance_udl(self, text: str) -> str:
        """Add UDL-compliant elements to text."""
        return self._generate(UDL_ENHANCEMENT_PROMPT, text)

    def describe_image(self, image_bytes: bytes, language: str = "en") -> dict:
        """Generate AI description and caption for an image.

        Returns a description suitable for alt-text (accessibility/UDL)
        and a narrative caption for the ebook.
        """
        from vertexai.generative_models import Image, Part

        lang_instruction = (
            "Respond in English." if language == "en"
            else "Responda em Portugues Brasileiro."
        )

        image_part = Part.from_data(image_bytes, mime_type="image/jpeg")

        description_prompt = (
            f"Describe this image in detail for accessibility purposes (alt-text). "
            f"Be precise, objective, and inclusive. {lang_instruction}"
        )
        description = self.model.generate_content(
            [image_part, description_prompt]
        ).text

        caption_prompt = (
            f"Write a short, engaging caption for this image as it would appear "
            f"in a professional ebook. Use a scientific yet narrative tone. "
            f"Do not sound like an AI. {lang_instruction}"
        )
        caption = self.model.generate_content([image_part, caption_prompt]).text

        return {"description": description, "caption": caption}

    def summarize_video(self, video_uri: str, language: str = "en") -> dict:
        """Generate a summary and key points from a video for ebook inclusion.

        Since videos can't be embedded in EPUB/PDF, we extract:
        - A narrative summary
        - Key visual descriptions
        - A QR code link suggestion
        """
        from vertexai.generative_models import Part

        lang_instruction = (
            "Respond in English." if language == "en"
            else "Responda em Portugues Brasileiro."
        )

        video_part = Part.from_uri(video_uri, mime_type="video/mp4")

        summary_prompt = (
            f"You are editing a professional ebook. This video needs to be "
            f"represented as text content in the book. Provide:\n"
            f"1. A narrative summary of the video content (2-3 paragraphs)\n"
            f"2. Key visual moments described for the reader\n"
            f"3. Main takeaways as a brief list\n\n"
            f"Use a scientific, engaging tone. Do not sound like an AI. "
            f"{lang_instruction}\n\n"
            f"Return as JSON: {{'summary': '...', 'key_visuals': ['...'], 'takeaways': ['...']}}"
        )

        result = self.model.generate_content([video_part, summary_prompt]).text
        return self._parse_json_safe(result)

    def _generate(self, system_prompt: str, user_content: str) -> str:
        """Generate content using Vertex AI with the given prompts."""
        full_prompt = f"{system_prompt}\n\n---\n\n{user_content}"
        response = self.model.generate_content(full_prompt)
        return response.text

    def _parse_json_safe(self, text: str) -> dict:
        """Attempt to parse JSON from model output, with fallback."""
        try:
            # Try to extract JSON from response (model might include markdown)
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except (json.JSONDecodeError, ValueError):
            pass
        return {"raw_response": text, "issues": [], "overall_score": -1}
