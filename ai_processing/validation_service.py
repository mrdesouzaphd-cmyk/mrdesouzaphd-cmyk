"""Standalone FastAPI service for the ebook-validation-workflow Cloud Run service.

This is a separate service from the main backend, matching the
Cloud Assist architecture diagram. It handles team-based content
validation as an independent microservice.
"""

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from ai_processing.validation_workflow import ValidationWorkflow

app = FastAPI(
    title="Ebook Validation Workflow",
    description="Team-based content validation service for the Content-to-Ebook Agent.",
)

workflow = None


def get_workflow() -> ValidationWorkflow:
    global workflow
    if workflow is None:
        workflow = ValidationWorkflow()
    return workflow


class ValidateRequest(BaseModel):
    content_id: str
    text: str
    language: str = "en"


class ValidateRoleRequest(BaseModel):
    role: str
    text: str
    language: str = "en"


@app.post("/validate")
def validate_content(req: ValidateRequest):
    """Run full team-based validation on content.

    Executes all 5 validation roles sequentially:
    editor -> accessibility_reviewer -> bias_auditor -> subject_expert -> final_approver
    """
    wf = get_workflow()
    report = wf.validate_content(
        content_id=req.content_id,
        text=req.text,
        language=req.language,
    )
    return report.to_dict()


@app.post("/validate/role")
def validate_single_role(req: ValidateRoleRequest):
    """Run validation for a single team role."""
    wf = get_workflow()
    try:
        result = wf.validate_single_role(
            role=req.role,
            text=req.text,
            language=req.language,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return {
        "role": result.role,
        "status": result.status.value,
        "feedback": result.feedback,
        "score": result.score,
        "suggestions": result.suggestions,
    }


@app.get("/health")
def health():
    return {"status": "healthy", "service": "ebook-validation-workflow"}
