"""
LegalLabel Compliance Rules Engine (v3)

This module contains deterministic, rule-based checks that look at the
structured label data produced by the CV/OCR + AI pipeline
(ScannedLabelData) and flag things that may need attention.

DESIGN PRINCIPLES (please read before editing):

1. This engine NEVER decides that a product is "illegal". All logic
   here is deterministic Python (plain if/else checks) — there is no
   LLM or AI involved in making a compliance decision.

2. Every check function distinguishes between two very different
   outcomes, which are kept in two SEPARATE lists on the result:

     - violations            : something WAS detected by OCR/AI, and
                                it looks wrong (invalid / incomplete /
                                suspicious). These are the "actual"
                                issues.

     - verification_required : the OCR/AI pipeline simply did NOT
                                detect this field at all. This is NOT
                                a claim that the physical label is
                                missing that information — the
                                scan/extraction may have failed. These
                                are always low severity and only mean
                                "please check the physical label
                                manually".

   Mixing these two together would make it look like a missing OCR
   read is the same thing as a real problem on the label, which is
   exactly what this version fixes.

3. Ingredients, nutritional information, and allergen information are
   intentionally NOT checked here. Legal Metrology rules (quantity,
   pricing, manufacturer/packer/importer details, dates, etc.) are a
   different concern from food-safety/nutrition labelling.

4. This is still a prototype rule set. To add a new rule later, write
   a new `_check_xxx()` function that returns a
   (violations, verification_required) tuple, and register it in
   `_ALL_CHECKS`.
"""

import re
from typing import List, Optional, Tuple

from pydantic import BaseModel

from models import ScannedLabelData, Manufacturer, ConsumerCare


class ComplianceViolation(BaseModel):
    """
    Represents a single flagged item — used for BOTH the `violations`
    list and the `verification_required` list.

    severity meanings used in this module:
      - "high"   : data was detected but is clearly invalid.
                    (always goes into `violations`)
      - "medium" : data was detected but looks incomplete/questionable.
                    (always goes into `violations`)
      - "low"    : the field was not detected at all by OCR/AI and
                    simply requires manual verification against the
                    physical label.
                    (always goes into `verification_required`)
    """
    field: str
    issue: str
    severity: str  # "high", "medium", or "low"


class ComplianceResult(BaseModel):
    """
    The overall result returned by the rules engine after checking a
    label's data.

    status is one of:
      - "compliant"              : no actual issues, nothing missing.
      - "verification_required"  : no actual issues, but some fields
                                    were not detected and need a human
                                    to check the physical label.
      - "potential_non_compliance": at least one actual (medium/high)
                                    issue was detected.
    """
    status: str
    summary: str
    violations: List[ComplianceViolation]
    verification_required: List[ComplianceViolation]


# A single check function returns this shape: (violations, verification_required)
CheckOutcome = Tuple[List[ComplianceViolation], List[ComplianceViolation]]


def _no_issues() -> CheckOutcome:
    """Shorthand for a check that found nothing to report."""
    return [], []


def _one_violation(field: str, issue: str, severity: str) -> CheckOutcome:
    """Shorthand for a check that found exactly one actual issue."""
    return [ComplianceViolation(field=field, issue=issue, severity=severity)], []


def _one_verification_note(field: str, issue: str) -> CheckOutcome:
    """Shorthand for a check that found exactly one 'not detected' note."""
    return [], [ComplianceViolation(field=field, issue=issue, severity="low")]


# ---------------------------------------------------------------------
# Small helper functions used by multiple checks below
# ---------------------------------------------------------------------

# Text values that OCR/AI sometimes produces which really mean "nothing
# was detected here", even though the field isn't a Python None.
_BLANK_EQUIVALENTS = {"", "n/a", "na", "none", "null", "-", "nil"}


def _is_blank(value: Optional[str]) -> bool:
    """
    Returns True if a string field should be treated as "not detected".
    Handles None, empty strings, whitespace-only strings, and common
    OCR placeholder values like "N/A" or "-".
    """
    if value is None:
        return True
    return value.strip().lower() in _BLANK_EQUIVALENTS


def _extract_number(text: Optional[str]) -> Optional[float]:
    """
    Tries to pull the first decimal number out of a raw OCR string,
    e.g. "Rs. 50.00" -> 50.0, "MRP: 199" -> 199.0.
    Returns None if no number could be found.
    """
    if not text:
        return None
    match = re.search(r"\d+(\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group())
    except ValueError:
        return None


def _looks_like_plausible_date(text: Optional[str]) -> bool:
    """
    Very light sanity check for a date-like string. This is NOT a full
    date parser/validator — it only checks that the text roughly looks
    like a date (numbers with separators, or a month name with a
    year), so we can catch obviously broken OCR output without needing
    an extra dependency.
    """
    if not text:
        return False

    # Matches things like 12/06/2026, 12-06-2026, 2026.06.12, etc.
    numeric_date_pattern = r"\d{1,4}\s*[\/\-\.]\s*\d{1,2}\s*[\/\-\.]\s*\d{1,4}"

    # Matches things like "June 2026" or "JUN 2026"
    month_name_pattern = (
        r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{4}"
    )

    return bool(
        re.search(numeric_date_pattern, text)
        or re.search(month_name_pattern, text, re.IGNORECASE)
    )


def _manufacturer_all_blank(entity: Manufacturer) -> bool:
    """
    Returns True only if EVERY field on a Manufacturer/Packer/Importer
    entity is blank. If the AI/OCR pipeline emitted an object where
    every field is "", null, etc., that object should be treated as
    "not detected" rather than "detected but incomplete".
    """
    return all(_is_blank(value) for value in [
        entity.name,
        entity.address_raw,
        entity.premises_or_street,
        entity.city,
        entity.state,
        entity.pincode,
        entity.relationship,
    ])


def _consumer_care_all_blank(cc: ConsumerCare) -> bool:
    """
    Same idea as _manufacturer_all_blank, but for the ConsumerCare
    object.
    """
    return all(_is_blank(value) for value in [
        cc.contact_person,
        cc.address,
        cc.phone,
        cc.email,
        cc.website,
    ])


# ---------------------------------------------------------------------
# Individual rule checks
# ---------------------------------------------------------------------
# Each function checks one concern and returns
# (violations, verification_required) — either list may be empty.
# ---------------------------------------------------------------------

def _check_commodity_name(data: ScannedLabelData) -> CheckOutcome:
    """
    Product/commodity name should be present so the label can be
    identified at all. Not detected -> verification note, not a
    violation.
    """
    if _is_blank(data.commodity_name):
        return _one_verification_note(
            field="commodity_name",
            issue="Commodity/product name was not detected in the extracted data — verify manually against the physical label."
        )
    return _no_issues()


def _check_mrp(data: ScannedLabelData) -> CheckOutcome:
    """
    MRP (Maximum Retail Price) checks:
      - Nothing detected at all -> verification_required (low).
      - Something detected but not a valid positive number ->
        violations (high).
      - Something detected and valid -> no issue.
    """
    raw = data.mrp_raw
    value = data.mrp_value

    raw_blank = _is_blank(raw)
    value_present = value is not None and value > 0

    if raw_blank and not value_present:
        return _one_verification_note(
            field="mrp",
            issue="MRP was not detected in the extracted data — verify manually against the physical label."
        )

    # Something was detected (raw text and/or a value). Make sure it's
    # actually a usable positive number.
    effective_value = value if value_present else _extract_number(raw)
    if effective_value is None or effective_value <= 0:
        return _one_violation(
            field="mrp",
            issue="MRP data was detected but could not be validated as a positive numeric value.",
            severity="high"
        )

    return _no_issues()


def _check_unit_sale_price(data: ScannedLabelData) -> CheckOutcome:
    """
    Unit sale price is not printed on every label, so its absence is
    not flagged at all (neither as a violation nor as a verification
    note). It is only checked when something was actually detected.
    """
    raw = data.unit_sale_price_raw
    value = data.unit_sale_price_value

    if _is_blank(raw) and (value is None or value == 0):
        return _no_issues()

    value_present = value is not None and value > 0
    effective_value = value if value_present else _extract_number(raw)
    if effective_value is None or effective_value <= 0:
        return _one_violation(
            field="unit_sale_price",
            issue="Unit sale price data was detected but could not be validated as a positive numeric value.",
            severity="medium"
        )
    return _no_issues()


def _check_net_quantity(data: ScannedLabelData) -> CheckOutcome:
    """
    Net quantity checks:
      - Nothing detected -> verification_required (low).
      - Detected but not a valid positive number -> violations (high).
      - Detected with a value but no unit -> violations (medium).
      - Valid -> no issue.
    """
    raw = data.net_quantity_raw
    value = data.net_quantity_value
    unit = data.net_quantity_unit

    raw_blank = _is_blank(raw)
    unit_blank = _is_blank(unit)
    value_present = value is not None and value > 0

    if raw_blank and not value_present:
        return _one_verification_note(
            field="net_quantity",
            issue="Net quantity was not detected in the extracted data — verify manually against the physical label."
        )

    violations: List[ComplianceViolation] = []

    effective_value = value if value_present else _extract_number(raw)
    if effective_value is None or effective_value <= 0:
        violations.append(ComplianceViolation(
            field="net_quantity_value",
            issue="Net quantity text was detected but could not be validated as a positive numeric value.",
            severity="high"
        ))

    if unit_blank:
        violations.append(ComplianceViolation(
            field="net_quantity_unit",
            issue="A net quantity value was detected but its unit of measurement (e.g. g, kg, ml, l) is missing.",
            severity="medium"
        ))

    return violations, []


def _check_number_of_units(data: ScannedLabelData) -> CheckOutcome:
    """
    If a "number of units" (e.g. multi-packs) was detected, it should
    be a positive whole number. Not detected at all -> no note, since
    plenty of products are single units.
    """
    if data.number_of_units is not None and data.number_of_units <= 0:
        return _one_violation(
            field="number_of_units",
            issue="Detected 'number of units' is zero or negative, which is not valid.",
            severity="high"
        )
    return _no_issues()


def _check_dates(data: ScannedLabelData) -> CheckOutcome:
    """
    Manufacturing/packing date and expiry/best-before date checks:
      - Not detected -> verification_required (low). Not all products
        require a fixed date (some use "when packed" legends), and
        absence is never treated as proof of a violation.
      - Detected but not date-shaped -> violations (medium).
    """
    violations: List[ComplianceViolation] = []
    verification_required: List[ComplianceViolation] = []

    mfg = data.mfg_date_raw
    if _is_blank(mfg):
        verification_required.append(ComplianceViolation(
            field="mfg_date_raw",
            issue="Manufacturing/packing date was not detected in the extracted data — verify manually.",
            severity="low"
        ))
    elif not _looks_like_plausible_date(mfg):
        violations.append(ComplianceViolation(
            field="mfg_date_raw",
            issue=f"Manufacturing/packing date text ('{mfg}') was detected but does not appear to be a valid date.",
            severity="medium"
        ))

    expiry = data.expiry_date_raw
    if _is_blank(expiry):
        verification_required.append(ComplianceViolation(
            field="expiry_date_raw",
            issue="Expiry/best-before date was not detected in the extracted data — verify manually (note: not all product categories require this).",
            severity="low"
        ))
    elif not _looks_like_plausible_date(expiry):
        violations.append(ComplianceViolation(
            field="expiry_date_raw",
            issue=f"Expiry/best-before date text ('{expiry}') was detected but does not appear to be a valid date.",
            severity="medium"
        ))

    return violations, verification_required


def _check_one_entity(field_name: str, entity: Optional[Manufacturer]) -> CheckOutcome:
    """
    Validates a single Manufacturer/Packer/Importer entity:
      - entity is None -> nothing to report here (the "at least one
        must exist" rule is handled separately, in
        _check_manufacturer_packer_importer).
      - entity exists but EVERY field on it is blank -> treat as "not
        detected" (verification note), not a detected-but-incomplete
        entity.
      - entity exists with SOME data but name or address is missing ->
        violations (medium).
    """
    if entity is None:
        return _no_issues()

    if _manufacturer_all_blank(entity):
        return _one_verification_note(
            field=field_name,
            issue=f"{field_name.capitalize()} details were not detected in the extracted data — verify manually."
        )

    violations: List[ComplianceViolation] = []

    if _is_blank(entity.name):
        violations.append(ComplianceViolation(
            field=f"{field_name}.name",
            issue=f"{field_name.capitalize()} details were detected but the name is missing/blank.",
            severity="medium"
        ))

    if _is_blank(entity.address_raw):
        violations.append(ComplianceViolation(
            field=f"{field_name}.address_raw",
            issue=f"{field_name.capitalize()} details were detected but the address is missing/blank.",
            severity="medium"
        ))

    return violations, []


def _check_manufacturer_packer_importer(data: ScannedLabelData) -> CheckOutcome:
    """
    Legal Metrology rules require at least one of manufacturer, packer,
    or importer details to be declared.

    - If NONE of the three objects were detected at all (all None, or
      present but fully blank) -> a single low-severity verification
      note.
    - Otherwise, validate whichever entities actually have some data,
      individually, via _check_one_entity.
    """
    entities = {
        "manufacturer": data.manufacturer,
        "packer": data.packer,
        "importer": data.importer,
    }

    def _entity_is_effectively_absent(entity: Optional[Manufacturer]) -> bool:
        return entity is None or _manufacturer_all_blank(entity)

    if all(_entity_is_effectively_absent(e) for e in entities.values()):
        return _one_verification_note(
            field="manufacturer_packer_importer",
            issue="No manufacturer, packer, or importer details were detected — at least one is expected under Legal Metrology rules, verify manually."
        )

    violations: List[ComplianceViolation] = []
    verification_required: List[ComplianceViolation] = []

    for field_name, entity in entities.items():
        entity_violations, entity_notes = _check_one_entity(field_name, entity)
        violations.extend(entity_violations)
        verification_required.extend(entity_notes)

    return violations, verification_required


def _check_consumer_care(data: ScannedLabelData) -> CheckOutcome:
    """
    Consumer care details should include at least a way to contact
    (phone or email).
      - Not detected at all, or present but fully blank -> verification
        note (low).
      - Detected with some data but no usable phone/email -> violation
        (medium).
    """
    cc = data.consumer_care

    if cc is None or _consumer_care_all_blank(cc):
        return _one_verification_note(
            field="consumer_care",
            issue="Consumer/customer care details were not detected in the extracted data — verify manually."
        )

    has_contact_method = not _is_blank(cc.phone) or not _is_blank(cc.email)
    if not has_contact_method:
        return _one_violation(
            field="consumer_care",
            issue="Consumer care details were detected but no phone number or email address was found.",
            severity="medium"
        )

    return _no_issues()


def _check_fssai_license(data: ScannedLabelData) -> CheckOutcome:
    """
    FSSAI license number is only relevant for food products, but since
    this prototype has no reliable way to determine that from
    'category' alone, its absence is always a low-severity
    verification note — never a hard Legal Metrology violation.
    """
    if _is_blank(data.fssai_license_number):
        return _one_verification_note(
            field="fssai_license_number",
            issue="FSSAI license number was not detected — verify manually if applicable for this product category."
        )
    return _no_issues()


def _check_pricing_flags(data: ScannedLabelData) -> CheckOutcome:
    """
    Checks boolean flags that the OCR/AI pipeline may set when it
    notices something suspicious about the pricing area of the label.
    These flags come directly from the pipeline's own detection.

    is_price_smudged_or_altered and has_misleading_qualifier are
    actual detected issues (there's nothing to "verify", the pipeline
    already saw it), so they go into `violations`.

    has_reduction_sticker is only a prompt for a human to double-check
    something (that the sticker doesn't obscure the original MRP), not
    a detected problem in itself, so it goes into
    `verification_required` instead.
    """
    violations: List[ComplianceViolation] = []
    verification_required: List[ComplianceViolation] = []

    if data.is_price_smudged_or_altered:
        violations.append(ComplianceViolation(
            field="is_price_smudged_or_altered",
            issue="The price on the label appears smudged or altered — manual verification required.",
            severity="high"
        ))

    if data.has_misleading_qualifier:
        violations.append(ComplianceViolation(
            field="has_misleading_qualifier",
            issue="A potentially misleading qualifying word/phrase was detected near the quantity declaration.",
            severity="medium"
        ))

    if data.has_reduction_sticker:
        verification_required.append(ComplianceViolation(
            field="has_reduction_sticker",
            issue="A price reduction sticker was detected — verify it does not obscure the original MRP declaration.",
            severity="low"
        ))

    return violations, verification_required


# List of all active rule-check functions.
# To add a new rule later, write a new _check_xxx function above and
# add it to this list. Each function must return a
# (violations, verification_required) tuple.
_ALL_CHECKS = [
    _check_commodity_name,
    _check_mrp,
    _check_unit_sale_price,
    _check_net_quantity,
    _check_number_of_units,
    _check_dates,
    _check_manufacturer_packer_importer,
    _check_consumer_care,
    _check_fssai_license,
    _check_pricing_flags,
]


def _build_summary(violations: List[ComplianceViolation], verification_required: List[ComplianceViolation]) -> str:
    """
    Builds a short, judge/human-friendly summary sentence describing
    the overall result.
    """
    if violations and verification_required:
        return (
            "Potential compliance issues were detected. Additional fields may also "
            "require manual verification."
        )
    if violations:
        return "Potential compliance issues were detected."
    if verification_required:
        return (
            "No definite compliance violation was detected. Several label fields "
            "were not detected by OCR/AI and require manual verification."
        )
    return "No potential compliance issues detected by the current prototype rules."


def run_compliance_checks(data: ScannedLabelData) -> ComplianceResult:
    """
    Runs all available rule checks against the given label data and
    returns a structured ComplianceResult containing:
      - violations: actual detected invalid/questionable issues
      - verification_required: fields the OCR/AI pipeline did not
        detect, which need a human to check the physical label

    This is the main entry point that the FastAPI endpoint calls.
    """
    violations: List[ComplianceViolation] = []
    verification_required: List[ComplianceViolation] = []

    for check in _ALL_CHECKS:
        check_violations, check_verification_notes = check(data)
        violations.extend(check_violations)
        verification_required.extend(check_verification_notes)

    if violations:
        status = "potential_non_compliance"
    elif verification_required:
        status = "verification_required"
    else:
        status = "compliant"

    return ComplianceResult(
        status=status,
        summary=_build_summary(violations, verification_required),
        violations=violations,
        verification_required=verification_required
    )