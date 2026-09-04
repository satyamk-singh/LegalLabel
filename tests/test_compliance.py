"""
Tests for the POST /api/v1/check-compliance endpoint.

These tests use the CURRENT ScannedLabelData schema (models.py) and
the CURRENT rules engine (rules/compliance.py, v3), which returns:
    status, summary, violations, verification_required

Run with (from the LegalLabel project root, with .venv active):
    pytest
"""

from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_check_compliance_with_fully_valid_label():
    """
    A label where every relevant field was detected and is valid
    should be reported as fully compliant, with nothing in either
    the violations list or the verification_required list.
    """
    valid_label = {
        "commodity_name": "Whole Wheat Flour Snack",
        "brand_name": "HealthyBite",
        "fssai_license_number": "12345678901234",
        "mrp_raw": "Rs. 50.00",
        "mrp_value": 50.0,
        "net_quantity_raw": "200 g",
        "net_quantity_value": 200.0,
        "net_quantity_unit": "g",
        "mfg_date_raw": "15/01/2026",
        "expiry_date_raw": "15/07/2026",
        "manufacturer": {
            "name": "ABC Foods Pvt Ltd",
            "address_raw": "Plot 12, Industrial Area, Pune"
        },
        "consumer_care": {
            "phone": "1800-123-4567",
            "email": "care@healthybite.example"
        },
        "is_price_smudged_or_altered": False,
        "has_misleading_qualifier": False,
        "has_reduction_sticker": False
    }

    response = client.post("/api/v1/check-compliance", json=valid_label)

    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "compliant"
    assert data["violations"] == []
    assert data["verification_required"] == []


def test_check_compliance_with_missing_ocr_fields():
    """
    A minimal payload where MRP, net quantity, dates, manufacturer,
    consumer care, and FSSAI details were simply not picked up by
    OCR/AI should NOT be reported as a compliance violation — it
    should only ask for manual verification.
    """
    minimal_label = {
        "commodity_name": "Unknown Snack Pack"
    }

    response = client.post("/api/v1/check-compliance", json=minimal_label)

    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "verification_required"
    assert data["violations"] == []
    assert len(data["verification_required"]) > 0


def test_check_compliance_with_invalid_mrp():
    """
    MRP text was detected, but it does not contain a valid positive
    number. This should be flagged as an actual high-severity
    violation on the "mrp" field.
    """
    label_with_bad_mrp = {
        "commodity_name": "Sample Product",
        "mrp_raw": "price not printed",
        "mrp_value": 0
    }

    response = client.post("/api/v1/check-compliance", json=label_with_bad_mrp)

    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "potential_non_compliance"

    mrp_violations = [v for v in data["violations"] if v["field"] == "mrp"]
    assert len(mrp_violations) == 1
    assert mrp_violations[0]["severity"] == "high"


def test_check_compliance_with_invalid_net_quantity():
    """
    Net quantity text was detected, but it does not contain a valid
    positive number (and has no unit either). This should be flagged
    as an actual violation related to net quantity.
    """
    label_with_bad_quantity = {
        "commodity_name": "Sample Product",
        "net_quantity_raw": "quantity unclear"
    }

    response = client.post("/api/v1/check-compliance", json=label_with_bad_quantity)

    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "potential_non_compliance"

    net_quantity_violations = [
        v for v in data["violations"] if "net_quantity" in v["field"]
    ]
    assert len(net_quantity_violations) > 0


def test_check_compliance_with_multiple_actual_violations():
    """
    When several fields are detected but invalid at the same time, the
    engine should return ALL of the actual violations, not just the
    first one it finds.
    """
    label_with_multiple_issues = {
        "commodity_name": "Sample Product",
        "mrp_raw": "unclear",
        "net_quantity_raw": "unclear",
        "is_price_smudged_or_altered": True,
        "has_misleading_qualifier": True
    }

    response = client.post("/api/v1/check-compliance", json=label_with_multiple_issues)

    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "potential_non_compliance"

    violation_fields = {v["field"] for v in data["violations"]}
    assert "mrp" in violation_fields
    assert "net_quantity_value" in violation_fields
    assert "net_quantity_unit" in violation_fields
    assert "is_price_smudged_or_altered" in violation_fields
    assert "has_misleading_qualifier" in violation_fields

    # All five distinct issues should be present at once.
    assert len(data["violations"]) >= 5


def test_check_compliance_with_reduction_sticker():
    """
    A detected price reduction sticker is only a prompt for manual
    verification (that it doesn't obscure the original MRP) — it
    should appear in verification_required, not in violations. With
    no other actual issues present, the overall status should be
    "verification_required".
    """
    label_with_reduction_sticker = {
        "commodity_name": "Sample Product",
        "has_reduction_sticker": True
    }

    response = client.post("/api/v1/check-compliance", json=label_with_reduction_sticker)

    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "verification_required"
    assert data["violations"] == []

    sticker_notes = [
        v for v in data["verification_required"]
        if v["field"] == "has_reduction_sticker"
    ]
    assert len(sticker_notes) == 1
    assert sticker_notes[0]["severity"] == "low"