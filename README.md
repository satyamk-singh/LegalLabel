# LegalLabel â€” Backend + Legal Metrology Rules Engine



**Smart India Hackathon 2026**



LegalLabel's backend receives structured product label data (extracted by a separate CV/OCR + AI pipeline), validates it, and runs it through a deterministic Legal Metrology compliance Rules Engine. This repository covers **Member 3's** scope: Backend Development, API, and the Legal Metrology Rules Engine.



\---



## 1. Project Overview



LegalLabel helps identify potential Legal Metrology compliance issues on packaged product labels. A separate CV/OCR + AI component scans a physical label and produces structured JSON describing what it detected (product name, MRP, net quantity, manufacturer details, dates, etc.).



This backend:

\- Accepts that structured JSON through a FastAPI API

\- Validates its shape using Pydantic models

\- Runs it through a deterministic, rule-based Compliance Rules Engine

\- Returns a clear, structured compliance result



The Rules Engine's job is narrowly scoped to Legal Metrologyâ€“style checks (pricing, quantity, manufacturer/packer/importer details, dates, consumer care, FSSAI license presence). It does **not** evaluate ingredients, nutritional information, or allergen declarations â€” those are treated as a separate, sector-specific concern outside this engine's current responsibility.



\---



## 2. Architecture / Data Flow



```

Physical Product Label

\&#x20;       â”‚

\&#x20;       â–¼

\&#x20; CV/OCR + AI Pipeline        (separate component â€” not part of this repo)

\&#x20;       â”‚  produces structured JSON

\&#x20;       â–¼

\&#x20; FastAPI Backend             (this repo)

\&#x20;       â”‚  Pydantic validates the incoming structure

\&#x20;       â–¼

\&#x20; Legal Metrology Rules Engine

\&#x20;       â”‚  deterministic Python checks â€” no AI/LLM involved in the decision

\&#x20;       â–¼

\&#x20; Structured Compliance Result

\&#x20;  (status, violations, verification\\_required)

```



**Important architectural principle:** the CV/OCR + AI pipeline is only responsible for *extracting* structured information from a label image. It does not, and should not, decide legal compliance. All compliance decisions in this backend are made by deterministic Python logic in the Rules Engine â€” never by an LLM or any AI model.



\---



## 3. Features



\- FastAPI backend with automatic request validation

\- `ScannedLabelData` Pydantic schema matching the CV/OCR + AI pipeline's structured JSON output

\- Deterministic Legal Metrology Compliance Rules Engine

\- Clear separation between:

&#x20; - **actual violations** â€” data was detected and is invalid/questionable

&#x20; - **verification_required** â€” data was simply not detected by OCR/AI and needs manual verification (not treated as proof the label itself is non-compliant)

\- Returns **all** detected violations in a single response, not just the first one found

\- Three distinct compliance statuses (`compliant`, `verification\\_required`, `potential\\_non\\_compliance`)

\- Pytest test suite (6 passing tests) covering valid labels, missing OCR data, invalid fields, and multiple simultaneous violations

\- Interactive Swagger/OpenAPI documentation, generated automatically by FastAPI

\- Backend verified against real structured JSON produced by the CV/OCR + AI team

\- GitHub-ready `requirements.txt` and `.gitignore`



\---



## 4. Project Structure



```

LegalLabel/

â”œâ”€â”€ main.py                   # FastAPI app and API endpoints

â”œâ”€â”€ models.py                 # Pydantic schema: ScannedLabelData and nested models

â”œâ”€â”€ product\\_label\\_data.json   # Sample structured label JSON for testing/reference

â”œâ”€â”€ requirements.txt          # Python dependencies

â”œâ”€â”€ .gitignore

â”œâ”€â”€ rules/

â”‚   â””â”€â”€ compliance.py         # Deterministic Legal Metrology Rules Engine

â””â”€â”€ tests/

\&#x20;   â””â”€â”€ test\\_compliance.py    # Pytest test suite for the compliance endpoint

```



\---



## 5. API Endpoints



### `GET /health`

Simple health-check endpoint used to confirm the backend is running.



**Response**

```json

{

\&#x20; "status": "ok",

\&#x20; "service": "LegalLabel Backend"

}

```



### `POST /api/v1/verify-label`

Accepts a `ScannedLabelData` JSON payload, validates it, and confirms it was received. Does not run the Rules Engine.



**Response**

```json

{

\&#x20; "status": "received",

\&#x20; "message": "Label data received successfully",

\&#x20; "data": { ... }

}

```



### `POST /api/v1/check-compliance`

Accepts a `ScannedLabelData` JSON payload and runs it through the Legal Metrology Rules Engine.



**Response**

```json

{

\&#x20; "status": "compliant | verification\\_required | potential\\_non\\_compliance",

\&#x20; "summary": "Human-readable summary of the result",

\&#x20; "violations": \\\[

\&#x20;   {

\&#x20;     "field": "mrp",

\&#x20;     "issue": "MRP data was detected but could not be validated as a positive numeric value.",

\&#x20;     "severity": "high"

\&#x20;   }

\&#x20; ],

\&#x20; "verification\\_required": \\\[

\&#x20;   {

\&#x20;     "field": "expiry\\_date\\_raw",

\&#x20;     "issue": "Expiry/best-before date was not detected in the extracted data â€” verify manually.",

\&#x20;     "severity": "low"

\&#x20;   }

\&#x20; ]

}

```



\---



## 6. Compliance Result Statuses



| Status | Meaning |

|---|---|

| `compliant` | No actual issues were found, and every relevant field was detected. |

| `verification\\_required` | No actual issues were found, but one or more fields were not detected by the OCR/AI pipeline and need a human to check the physical label. |

| `potential\\_non\\_compliance` | At least one field was detected and failed a Legal Metrology check. |



`verification\\_required` is deliberately kept separate from `violations` so that a missing OCR read is never presented as proof that the physical label itself is non-compliant.



\---



## 7. Rules Engine



The Rules Engine (`rules/compliance.py`) is a set of deterministic, rule-based Python checks â€” there is no LLM or AI model involved in deciding compliance.



For each relevant field, the engine distinguishes between:

\- **Not detected** â€” nothing was extracted for this field â†’ low-severity `verification\\_required` note

\- **Detected but invalid** â€” something was extracted but fails a sanity check (e.g. non-numeric MRP, missing unit on a net quantity) â†’ `violations`, with `medium` or `high` severity

\- **Detected and valid** â€” no issue is raised



Checks currently implemented cover:

\- Commodity/product name presence

\- MRP and unit sale price validity

\- Net quantity value and unit

\- Number of units

\- Manufacturing and expiry/best-before date presence and basic format sanity

\- Manufacturer, packer, and importer detail presence and completeness

\- Consumer care contact details

\- FSSAI license number presence

\- Pricing-related flags (smudged/altered price, misleading qualifiers, reduction stickers)



**Ingredients, nutritional information, and allergen information are intentionally not checked here.** These belong to separate, sector-specific rules (e.g. food safety labelling) and are out of scope for the Legal Metrology Rules Engine implemented in this module.



The engine is structured as a list of small, independent check functions, making it straightforward to extend later with commodity-specific rules, font size/readability checks, label placement checks, or updated government rules â€” without modifying the core engine logic.



\---



## 8. Testing



The project includes a Pytest test suite covering the compliance endpoint, using FastAPI's `TestClient`.



Current test coverage (6 tests, all passing):

\- Fully valid label â†’ `compliant`, no violations, no verification notes

\- Minimal label with missing OCR fields â†’ `verification\\_required`, no violations

\- Detected but invalid MRP â†’ `potential\\_non\\_compliance`, high-severity `mrp` violation

\- Detected but invalid net quantity â†’ `potential\\_non\\_compliance`, related violation(s)

\- Multiple simultaneous invalid fields â†’ all violations returned, not just the first

\- Detected reduction sticker â†’ appears in `verification\\_required`, not `violations`



\---



## 9. Local Setup



```bash

python -m venv .venv

.venv\\\\Scripts\\\\Activate.ps1

pip install -r requirements.txt

```



\---



## 10. Running the Backend



```bash

python -m uvicorn main:app --reload

```



The API will be available at `http://127.0.0.1:8000`.



\---



## 11. Swagger API Documentation



Once the server is running, interactive API documentation (generated automatically by FastAPI) is available at:



```

http://127.0.0.1:8000/docs

```



All endpoints, including `POST /api/v1/check-compliance`, can be tested directly from this interface.



\---



## 12. Team Role â€” Member 3



**Backend Development + API + Legal Metrology Rules Engine**



Responsibilities covered in this repository:

\- Designing and implementing the FastAPI backend

\- Defining the `ScannedLabelData` Pydantic schema to match the structured JSON produced by the CV/OCR + AI pipeline

\- Building the deterministic Legal Metrology Compliance Rules Engine

\- Exposing the Rules Engine through a REST API endpoint

\- Writing automated tests for the compliance logic

\- Preparing the project for version control and collaboration (`requirements.txt`, `.gitignore`)



\---



## 13. Current Limitations / Future Integration



\- The Rules Engine is a first working prototype and does not yet cover every Legal Metrology requirement (e.g. font size/readability checks, label placement checks, commodity-specific rules).

\- Ingredients, nutritional information, and allergen checks are out of scope for this engine and would need a separate, sector-specific rules module.

\- Country-of-origin is not currently part of the structured schema and is therefore not checked.

\- The backend currently has no database layer, authentication, or persistent storage â€” it operates on a single request/response basis.

\- No frontend, dashboard, or complaint-management system is implemented in this repository.

\- Date fields are checked only for basic format plausibility, not full calendar validation.

\- Future work may include integrating the finalized structured JSON contract from the CV/OCR + AI team on an ongoing basis, expanding rule coverage, and connecting this backend to the project's frontend and dashboard components once those are available.


