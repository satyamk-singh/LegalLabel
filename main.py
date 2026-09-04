from fastapi import FastAPI

from models import ScannedLabelData
from rules.compliance import (
    run_compliance_checks,
    ComplianceResult
)


app = FastAPI(
    title="LegalLabel Backend",
    description="Backend API for the LegalLabel SIH 2026 project",
    version="0.2.0"
)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "LegalLabel Backend"
    }


@app.post("/api/v1/verify-label")
def verify_label(label_data: ScannedLabelData):
    return {
        "status": "received",
        "message": "Label data received successfully",
        "data": label_data
    }


@app.post(
    "/api/v1/check-compliance",
    response_model=ComplianceResult
)
def check_compliance(label_data: ScannedLabelData):

    result = run_compliance_checks(label_data)

    return result