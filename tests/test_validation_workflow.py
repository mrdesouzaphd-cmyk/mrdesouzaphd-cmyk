"""Tests for the team-based validation workflow."""

from ai_processing.validation_workflow import (
    ROLE_PROMPTS,
    ValidationReport,
    ValidationResult,
    ValidationStatus,
    ValidationWorkflow,
)


class TestValidationRoles:
    """Verify all 5 team roles are defined with proper prompts."""

    def test_all_roles_defined(self):
        expected_roles = [
            "editor",
            "accessibility_reviewer",
            "bias_auditor",
            "subject_expert",
            "final_approver",
        ]
        for role in expected_roles:
            assert role in ROLE_PROMPTS, f"Missing role: {role}"

    def test_editor_checks_ai_style(self):
        assert "AI-sounding phrases" in ROLE_PROMPTS["editor"]

    def test_accessibility_reviewer_checks_udl(self):
        prompt = ROLE_PROMPTS["accessibility_reviewer"]
        assert "UDL" in prompt
        assert "representation" in prompt
        assert "engagement" in prompt

    def test_bias_auditor_comprehensive(self):
        prompt = ROLE_PROMPTS["bias_auditor"]
        assert "Gender bias" in prompt
        assert "Cultural" in prompt
        assert "Ableist" in prompt

    def test_final_approver_gate(self):
        prompt = ROLE_PROMPTS["final_approver"]
        assert "approved" in prompt
        assert "rejected" in prompt


class TestValidationReport:
    """Test the ValidationReport data model."""

    def test_report_approved_when_all_pass(self):
        report = ValidationReport(
            content_id="test-123",
            results=[
                ValidationResult(
                    role="editor",
                    status=ValidationStatus.APPROVED,
                    feedback="Good",
                    score=90,
                ),
                ValidationResult(
                    role="bias_auditor",
                    status=ValidationStatus.APPROVED,
                    feedback="Clean",
                    score=95,
                ),
            ],
        )
        assert report.is_approved is True
        assert report.overall_score == 92.5

    def test_report_not_approved_if_any_fails(self):
        report = ValidationReport(
            content_id="test-456",
            results=[
                ValidationResult(
                    role="editor",
                    status=ValidationStatus.APPROVED,
                    feedback="Good",
                    score=90,
                ),
                ValidationResult(
                    role="bias_auditor",
                    status=ValidationStatus.NEEDS_REVISION,
                    feedback="Issues found",
                    score=40,
                ),
            ],
        )
        assert report.is_approved is False

    def test_report_to_dict(self):
        report = ValidationReport(
            content_id="test-789",
            results=[
                ValidationResult(
                    role="editor",
                    status=ValidationStatus.APPROVED,
                    feedback="Perfect",
                    score=100,
                    suggestions=[],
                ),
            ],
        )
        d = report.to_dict()
        assert d["content_id"] == "test-789"
        assert d["is_approved"] is True
        assert len(d["results"]) == 1
        assert d["results"][0]["role"] == "editor"

    def test_empty_report_score_zero(self):
        report = ValidationReport(content_id="empty")
        assert report.overall_score == 0
        assert report.is_approved is True  # vacuously true


class TestWorkflowParsing:
    """Test the validation workflow's response parsing."""

    def test_parse_valid_result(self):
        wf = ValidationWorkflow.__new__(ValidationWorkflow)
        response = '{"score": 85, "status": "approved", "feedback": "Great work", "suggestions": ["Minor tweak"]}'
        result = wf._parse_result("editor", response)
        assert result.role == "editor"
        assert result.status == ValidationStatus.APPROVED
        assert result.score == 85
        assert len(result.suggestions) == 1

    def test_parse_invalid_result(self):
        wf = ValidationWorkflow.__new__(ValidationWorkflow)
        result = wf._parse_result("editor", "not json")
        assert result.status == ValidationStatus.NEEDS_REVISION
        assert result.score == 0
