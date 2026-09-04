from fastapi import FastAPI
from pydantic import BaseModel
from typing import List

from models import ScannedLabelData
from rules.compliance import run_compliance_checks, ComplianceViolation

# Create the FastAPI application instance
# Swagger docs are automatically available at /docs
app = FastAPI(
    title="LegalLabel Backend",
    description="Backend API for the LegalLabel SIH 2026 project",
    version="0.1.0"
)


# ---------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------
# These describe the *shape* of each endpoint's response so that
# Swagger (/docs) can show exactly what a caller should expect back.
# They do not contain any decision logic themselves — the actual
# Legal Metrology decisions still live entirely in
# rules/compliance.py.
# ---------------------------------------------------------------------

class VerificationResponse(BaseModel):
    """
    Response returned by POST /api/v1/verify-label.
    Simply confirms that the label data was received and validated.
    """
    status: str
    message: str
    data: ScannedLabelData


class ComplianceResponse(BaseModel):
    """
    Response returned by POST /api/v1/check-compliance.

    - status: "compliant", "verification_required", or
      "potential_non_compliance" (decided by the Rules Engine).
    - summary: short human-readable explanation of the result.
    - violations: fields that were detected but look invalid.
    - verification_required: fields that were not detected by the
      OCR/AI pipeline and need manual verification against the
      physical label (not treated as a confirmed violation).
    """
    status: str
    summary: str
    violations: List[ComplianceViolation]
    verification_required: List[ComplianceViolation]


# ---------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------

@app.get("/health")
def health_check():
    """
    Health check.

    Confirms that the LegalLabel backend server is up and reachable.
    Useful for quick demo checks and uptime monitoring.
    """
    return {
        "status": "ok",
        "service": "LegalLabel Backend"
    }


@app.post("/api/v1/verify-label", response_model=VerificationResponse)
def verify_label(label_data: ScannedLabelData):
    """
    Verify and echo back scanned label data.

    Accepts the structured label data produced by the CV/OCR + AI
    pipeline, validates it against the ScannedLabelData schema, and
    returns it unchanged as confirmation. This endpoint does NOT run
    any Legal Metrology checks — use POST /api/v1/check-compliance
    for that.
    """
    return VerificationResponse(
        status="received",
        message="Label data received successfully",
        data=label_data
    )


@app.post("/api/v1/check-compliance", response_model=ComplianceResponse)
def check_compliance(label_data: ScannedLabelData):
    """
    Run the Legal Metrology Rules Engine on scanned label data.

    Accepts the structured label data produced by the CV/OCR + AI
    pipeline and runs it through the deterministic Legal Metrology
    Rules Engine (rules/compliance.py). All compliance decisions are
    made by fixed Python logic — no AI/LLM is involved in deciding
    compliance.

    Returns a ComplianceResponse with:
    - status: "compliant" / "verification_required" / "potential_non_compliance"
    - summary: a short explanation of the result
    - violations: fields detected but flagged as invalid
    - verification_required: fields not detected by OCR/AI, needing
      manual verification against the physical label

    NOTE: This is a prototype rules engine and does not represent a
    complete or legally certified Legal Metrology check.
    """
    result = run_compliance_checks(label_data)
    return result