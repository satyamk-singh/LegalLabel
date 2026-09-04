"""
Shared Pydantic models for the LegalLabel backend.

This file defines the structured data contract for a scanned product
label, matching the exact JSON produced by the CV/OCR + AI pipeline.

All fields are Optional (with safe defaults) because OCR/AI extraction
may leave some fields missing, null, empty, or zero depending on what
was readable on the physical label.
"""

from pydantic import BaseModel
from typing import List, Optional


class Manufacturer(BaseModel):
    """
    Represents a manufacturer, packer, or importer entity on the label.
    The same shape is reused for the "manufacturer", "packer", and
    "importer" fields since they share the same structure.
    """
    name: Optional[str] = None
    address_raw: Optional[str] = None
    premises_or_street: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    pincode: Optional[str] = None
    relationship: Optional[str] = None


class ConsumerCare(BaseModel):
    """
    Consumer/customer care contact details declared on the label.
    """
    contact_person: Optional[str] = None
    address: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None


class NutritionalInformation(BaseModel):
    """
    Nutritional information panel, typically declared per serving size
    (see the "per" field, e.g. "100 g").
    """
    per: Optional[str] = None
    energy_kcal: Optional[float] = None
    protein_g: Optional[float] = None
    carbohydrate_g: Optional[float] = None
    total_sugars_g: Optional[float] = None
    added_sugars_g: Optional[float] = None
    total_fat_g: Optional[float] = None
    saturated_fat_g: Optional[float] = None
    trans_fat_g: Optional[float] = None
    sodium_mg: Optional[float] = None


class ScannedLabelData(BaseModel):
    """
    Represents the full structured product label data extracted by the
    CV/OCR + AI pipeline. This is the data that gets validated on the
    way in, and later checked against Legal Metrology rules.
    """
    commodity_name: Optional[str] = None
    brand_name: Optional[str] = None
    category: Optional[str] = None
    fssai_license_number: Optional[str] = None
    batch_number: Optional[str] = None

    net_quantity_raw: Optional[str] = None
    net_quantity_value: Optional[float] = None
    net_quantity_unit: Optional[str] = None
    number_of_units: Optional[int] = None
    has_misleading_qualifier: Optional[bool] = None

    mrp_raw: Optional[str] = None
    mrp_value: Optional[float] = None
    unit_sale_price_raw: Optional[str] = None
    unit_sale_price_value: Optional[float] = None
    is_price_smudged_or_altered: Optional[bool] = None
    has_reduction_sticker: Optional[bool] = None

    mfg_date_raw: Optional[str] = None
    expiry_date_raw: Optional[str] = None
    has_when_packed_legend: Optional[bool] = None

    manufacturer: Optional[Manufacturer] = None
    packer: Optional[Manufacturer] = None
    importer: Optional[Manufacturer] = None

    consumer_care: Optional[ConsumerCare] = None

    is_veg: Optional[bool] = None
    barcode: Optional[str] = None

    ingredients: Optional[List[str]] = None

    nutritional_information: Optional[NutritionalInformation] = None

    allergen_info: Optional[str] = None
    storage_instructions: Optional[str] = None

    pdp_area_sq_cm: Optional[float] = None
    numeral_height_mm: Optional[float] = None
    letter_height_mm: Optional[float] = None
    is_blown_or_molded: Optional[bool] = None
    is_contrasting_color: Optional[bool] = None

    language: Optional[str] = None
    dimensions_raw: Optional[str] = None

    is_fast_food_hotel: Optional[bool] = None
    is_dpco_drug: Optional[bool] = None
    is_institutional_consumer: Optional[bool] = None
    is_bulk_agriculture: Optional[bool] = None