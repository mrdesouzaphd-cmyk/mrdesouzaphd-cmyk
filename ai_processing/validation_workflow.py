"""Team-based validation workflow for ebook content.

Implements a multi-stage review pipeline where different "team roles"
validate content before it's finalized for the ebook. Each role is
simulated via specialized Vertex AI prompts, ensuring diverse perspectives.

Roles:
- Editor: Grammar, style, flow, human voice
- Accessibility Reviewer: UDL compliance, inclusive language
- Bias Auditor: Bias detection across all dimensions
- Subject Matter Expert: Scientific accuracy, terminology
- Final Approver: Overall quality gate
"""

import json
from dataclasses import dataclass, field
from enum import Enum

from vertexai.generative_models import GenerativeModel

from config.settings import settings


class ValidationStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    NEEDS_REVISION = "needs_revision"
    REJECTED = "rejected"


@dataclass
class ValidationResult:
    role: str
    status: ValidationStatus
    feedback: str
    score: int  # 0-100
    suggestions: list[str] = field(default_factory=list)


@dataclass
class ValidationReport:
    content_id: str
    results: list[ValidationResult] = field(default_factory=list)

    @property
    def is_approved(self) -> bool:
        return all(r.status == ValidationStatus.APPROVED for r in self.results)

    @property
    def overall_score(self) -> float:
        if not self.results:
            return 0
        return sum(r.score for r in self.results) / len(self.results)

    def to_dict(self) -> dict:
        return {
            "content_id": self.content_id,
            "is_approved": self.is_approved,
            "overall_score": self.overall_score,
            "results": [
                {
                    "role": r.role,
                    "status": r.status.value,
                    "feedback": r.feedback,
                    "score": r.score,
                    "suggestions": r.suggestions,
                }
                for r in self.results
            ],
        }


# ──────────────────────────────────────────────
# Team role prompts
# ──────────────────────────────────────────────

ROLE_PROMPTS = {
    "editor": (
        "You are a senior book editor. Review this text for:\n"
        "- Grammar and punctuation accuracy\n"
        "- Natural, human writing style (flag any AI-sounding phrases)\n"
        "- Narrative flow and transitions between ideas\n"
        "- Sentence variety and readability\n"
        "- Consistency in tone (scientific yet accessible)\n\n"
        "Return JSON: {\"score\": 0-100, \"status\": \"approved\"|\"needs_revision\", "
        "\"feedback\": \"...\", \"suggestions\": [\"...\"]}"
    ),
    "accessibility_reviewer": (
        "You are a UDL (Universal Design for Learning) specialist. Review this text for:\n"
        "- Multiple means of representation (concepts explained in varied ways)\n"
        "- Multiple means of engagement (interactive elements, questions, prompts)\n"
        "- Multiple means of action/expression (application opportunities)\n"
        "- Alt-text quality for any referenced images\n"
        "- Reading level appropriateness\n"
        "- Inclusive language\n\n"
        "Return JSON: {\"score\": 0-100, \"status\": \"approved\"|\"needs_revision\", "
        "\"feedback\": \"...\", \"suggestions\": [\"...\"]}"
    ),
    "bias_auditor": (
        "You are a diversity and inclusion auditor. Review this text for:\n"
        "- Gender bias or stereotypes\n"
        "- Cultural or racial assumptions\n"
        "- Socioeconomic bias\n"
        "- Ableist language or assumptions\n"
        "- Age bias\n"
        "- Geographic or linguistic bias\n"
        "- Any exclusionary framing\n\n"
        "Return JSON: {\"score\": 0-100, \"status\": \"approved\"|\"needs_revision\", "
        "\"feedback\": \"...\", \"suggestions\": [\"...\"]}"
    ),
    "subject_expert": (
        "You are a subject matter expert in education and science. Review this text for:\n"
        "- Scientific accuracy of claims and data\n"
        "- Proper use of terminology\n"
        "- Correct citations and references format\n"
        "- Logical argumentation\n"
        "- Evidence-based conclusions\n\n"
        "Return JSON: {\"score\": 0-100, \"status\": \"approved\"|\"needs_revision\", "
        "\"feedback\": \"...\", \"suggestions\": [\"...\"]}"
    ),
    "final_approver": (
        "You are the final quality gate for ebook publication. Given the text and "
        "previous review feedback, make a final determination:\n"
        "- Is the content ready for professional publication?\n"
        "- Does it maintain a consistent, human editorial voice?\n"
        "- Is it free from AI-generated artifacts?\n"
        "- Would a reader find it engaging and well-structured?\n\n"
        "Return JSON: {\"score\": 0-100, \"status\": \"approved\"|\"needs_revision\"|\"rejected\", "
        "\"feedback\": \"...\", \"suggestions\": [\"...\"]}"
    ),
}


class ValidationWorkflow:
    """Orchestrates team-based content validation using Vertex AI."""

    def __init__(self):
        self.model = GenerativeModel("gemini-1.5-pro")

    def validate_content(
        self, content_id: str, text: str, language: str = "en"
    ) -> ValidationReport:
        """Run full team validation workflow on content.

        Each role reviews sequentially so later roles can see earlier feedback.
        """
        report = ValidationReport(content_id=content_id)
        accumulated_feedback = []

        roles_order = [
            "editor",
            "accessibility_reviewer",
            "bias_auditor",
            "subject_expert",
            "final_approver",
        ]

        for role in roles_order:
            prompt = ROLE_PROMPTS[role]

            # Final approver gets accumulated feedback
            if role == "final_approver" and accumulated_feedback:
                prompt += (
                    "\n\nPrevious reviewer feedback:\n"
                    + "\n".join(accumulated_feedback)
                )

            lang_note = (
                "The text is in English."
                if language == "en"
                else "The text is in Brazilian Portuguese."
            )

            full_prompt = f"{prompt}\n\n{lang_note}\n\n---\n\n{text}"
            response = self.model.generate_content(full_prompt).text
            result = self._parse_result(role, response)
            report.results.append(result)

            accumulated_feedback.append(
                f"[{role}] Score: {result.score}/100 - {result.feedback}"
            )

        return report

    def validate_single_role(
        self, role: str, text: str, language: str = "en"
    ) -> ValidationResult:
        """Run validation for a single role."""
        if role not in ROLE_PROMPTS:
            raise ValueError(f"Unknown role: {role}. Available: {list(ROLE_PROMPTS.keys())}")

        prompt = ROLE_PROMPTS[role]
        lang_note = (
            "The text is in English."
            if language == "en"
            else "The text is in Brazilian Portuguese."
        )
        full_prompt = f"{prompt}\n\n{lang_note}\n\n---\n\n{text}"
        response = self.model.generate_content(full_prompt).text
        return self._parse_result(role, response)

    def _parse_result(self, role: str, response: str) -> ValidationResult:
        """Parse model response into a ValidationResult."""
        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(response[start:end])
                status_str = data.get("status", "needs_revision")
                return ValidationResult(
                    role=role,
                    status=ValidationStatus(status_str),
                    feedback=data.get("feedback", ""),
                    score=data.get("score", 0),
                    suggestions=data.get("suggestions", []),
                )
        except (json.JSONDecodeError, ValueError):
            pass

        return ValidationResult(
            role=role,
            status=ValidationStatus.NEEDS_REVISION,
            feedback=f"Could not parse review response: {response[:200]}",
            score=0,
            suggestions=[],
        )
