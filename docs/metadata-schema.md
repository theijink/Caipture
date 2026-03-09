# Caipture - Metadata Schema Specification

Version: 0.2.0
Status: Draft
Applies to: Canonical per-item metadata (`photo_item.json`)

---

# 1. Purpose

This document defines the canonical internal metadata schema used by Caipture.

The schema is designed to:

- preserve evidence and provenance
- represent uncertainty explicitly
- support human correction workflows
- provide deterministic input for export mapping

This schema is independent from EXIF/IPTC/XMP. External standards are export targets, not source-of-truth formats.

---

# 2. Canonical Location

Canonical file path:

```text
storage/jobs/<job_id>/metadata/photo_item.json
```

Only this file is authoritative for structured item metadata.

---

# 3. Type Conventions

## 3.1 Timestamp

All timestamps use UTC ISO-8601 format, for example:

```text
2026-03-09T10:15:30Z
```

## 3.2 Confidence

`confidence` is a float in `[0.0, 1.0]`.

## 3.3 Relative Paths

All artifact paths are relative to `storage/jobs/<job_id>/`.

## 3.4 Null and Missing Rules

- Required fields must always exist.
- Optional fields may be omitted.
- Use `null` only when field existence is required but value is unknown.
- Do not invent placeholder values (for example `"unknown"`) unless explicitly defined enum value.

---

# 4. Top-Level Object

## 4.1 Required Fields

- `schema_version` (string)
- `item_id` (string)
- `job_id` (string)
- `created_at` (timestamp)
- `updated_at` (timestamp)
- `status` (enum)
- `inputs` (object)
- `derived` (object)
- `historical_metadata` (object)
- `digitization_metadata` (object)
- `review` (object)

## 4.2 Optional Fields

- `export_mapping` (object)
- `revisions` (array)

## 4.3 Status Enum

Allowed values:

```text
uploaded
validation_failed
queued
processing
review_required
completed
failed
```

---

# 5. JSON Shape (Normative)

```json
{
  "schema_version": "0.2.0",
  "item_id": "item_20260309_0001",
  "job_id": "job_20260309_0001",
  "created_at": "2026-03-09T10:15:30Z",
  "updated_at": "2026-03-09T10:16:10Z",
  "status": "review_required",
  "inputs": {},
  "derived": {},
  "historical_metadata": {},
  "digitization_metadata": {},
  "review": {},
  "export_mapping": {},
  "revisions": []
}
```

---

# 6. `inputs` Object

## 6.1 Required Members

- `front_image` (object)
- `back_image` (object)

## 6.2 Optional Members

- `context_images` (array)

## 6.3 FileRef Type

`FileRef` object:

- `path` (required string)
- `sha256` (required string, lowercase hex)
- `mime_type` (optional string)
- `bytes` (optional integer)

Example:

```json
"inputs": {
  "front_image": {
    "path": "inputs/front.jpg",
    "sha256": "f4c3...",
    "mime_type": "image/jpeg"
  },
  "back_image": {
    "path": "inputs/back.jpg",
    "sha256": "8a9b..."
  },
  "context_images": [
    {
      "path": "inputs/context_001.jpg",
      "sha256": "11aa..."
    }
  ]
}
```

---

# 7. `derived` Object

Holds references to generated artifacts.

Known keys (all optional, implementation may extend):

- `front_cropped`
- `front_rectified`
- `front_normalized`
- `back_ocr_text`
- `context_ocr_texts` (array)
- `validation_report`
- `ocr_report`

All values are relative paths (or arrays of relative paths).

---

# 8. `historical_metadata` Object

Holds interpreted historical context fields.

## 8.1 Common Interpretation Type

Most interpreted fields should follow this shape:

- `value` (type varies)
- `raw_text` (optional string)
- `confidence` (required float 0..1)
- `sources` (required array of SourceRef)

`SourceRef`:

- `source_type` (enum)
- `source_ref` (string path/id)
- `excerpt` (optional string)

`source_type` enum:

```text
back_note
album_caption
context_image
ocr_text
rule_engine
vision_model
llm_inference
manual_entry
```

## 8.2 `date` Field

Type:

```json
"date": {
  "raw_text": "Summer 1934",
  "from": "1934-06-01",
  "to": "1934-08-31",
  "precision": "season",
  "confidence": 0.78,
  "sources": []
}
```

Constraints:

- `precision` enum: `year|month|day|season|range|unknown`
- if both `from` and `to` exist, `from <= to`
- for `precision=day`, `from` and `to` should be same date

## 8.3 `location` Field

Type:

```json
"location": {
  "raw_text": "Enschede",
  "normalized": {
    "name": "Enschede, Overijssel, Netherlands",
    "country_code": "NL",
    "lat": 52.2215,
    "lon": 6.8937
  },
  "confidence": 0.74,
  "sources": []
}
```

`normalized` members are optional except `name` when present.

## 8.4 `people` Field

Type: array of objects:

- `name` (required string)
- `role` (required enum)
- `confidence` (required float)
- `sources` (required array)

`role` enum:

```text
subject
possible_subject
photographer
unknown_person
```

## 8.5 `description` Field

Type:

- `text` (required string)
- `confidence` (required float)
- `sources` (required array)

## 8.6 Optional Fields

- `event`
- `keywords`
- `collection`

Optional fields should follow the same provenance/confidence pattern.

---

# 9. `digitization_metadata` Object

Required fields:

- `digitized_at` (timestamp)
- `pipeline_version` (string)
- `config_version` (string)

Optional fields:

- `operator` (string)
- `capture_device` (string)
- `tools` (object map of component -> version)
- `run_id` (string)

Example:

```json
"digitization_metadata": {
  "digitized_at": "2026-03-09T10:15:30Z",
  "pipeline_version": "0.2.0",
  "config_version": "dev-2026-03-09",
  "operator": "twan",
  "tools": {
    "opencv": "4.10.0",
    "tesseract": "5.4.0"
  }
}
```

---

# 10. `review` Object

Required fields:

- `required` (boolean)
- `reasons` (array of strings)
- `status` (enum)

Optional fields:

- `approved_by` (string or null)
- `approved_at` (timestamp or null)
- `changes` (array)
- `notes` (string)

`review.status` enum:

```text
not_required
pending
approved
rejected
```

`changes[]` item:

- `field_path` (string)
- `before` (any)
- `after` (any)
- `changed_by` (string)
- `changed_at` (timestamp)

---

# 11. `export_mapping` Object

Optional object populated by export stage.

Structure:

- `exif` object map
- `iptc` object map
- `xmp` object map
- `exported_at` timestamp
- `export_profile` string

This section is derived, never canonical source.

---

# 12. `revisions` Object

Optional append-only history of canonical edits.

`revisions[]` item:

- `revision` (integer)
- `timestamp` (timestamp)
- `actor` (string)
- `reason` (string)
- `changes_summary` (string)

---

# 13. Validation Rules

Minimum validator checks:

1. required fields present
2. enum values valid
3. confidence values within range
4. all referenced artifact paths are relative and within job directory
5. status value compatible with review/export fields
6. date range consistency
7. source provenance present for interpreted fields

Validation must run before export.

---

# 14. Configuration-Coupled Rules

The following behavior is configuration-driven and must not be hard-coded:

- thresholds for auto-approval and review-required
- allowed source types extensions
- export profile selection
- mapping profile from canonical fields to EXIF/IPTC/XMP

Schema structure remains stable while policy thresholds come from configuration files.

---

# 15. Example Complete Document

```json
{
  "schema_version": "0.2.0",
  "item_id": "item_20260309_0001",
  "job_id": "job_20260309_0001",
  "created_at": "2026-03-09T10:15:30Z",
  "updated_at": "2026-03-09T10:17:10Z",
  "status": "review_required",
  "inputs": {
    "front_image": {
      "path": "inputs/front.jpg",
      "sha256": "f4c3..."
    },
    "back_image": {
      "path": "inputs/back.jpg",
      "sha256": "8a9b..."
    }
  },
  "derived": {
    "front_rectified": "derived/front_rectified.jpg",
    "back_ocr_text": "derived/back_ocr.txt"
  },
  "historical_metadata": {
    "date": {
      "raw_text": "Summer 1934",
      "from": "1934-06-01",
      "to": "1934-08-31",
      "precision": "season",
      "confidence": 0.78,
      "sources": [
        {
          "source_type": "ocr_text",
          "source_ref": "derived/back_ocr.txt",
          "excerpt": "Summer 1934"
        }
      ]
    },
    "location": {
      "raw_text": "Enschede",
      "normalized": {
        "name": "Enschede, Overijssel, Netherlands",
        "country_code": "NL",
        "lat": 52.2215,
        "lon": 6.8937
      },
      "confidence": 0.74,
      "sources": [
        {
          "source_type": "back_note",
          "source_ref": "inputs/back.jpg"
        }
      ]
    },
    "people": []
  },
  "digitization_metadata": {
    "digitized_at": "2026-03-09T10:15:30Z",
    "pipeline_version": "0.2.0",
    "config_version": "dev-2026-03-09"
  },
  "review": {
    "required": true,
    "reasons": ["date_precision_not_day", "location_confidence_below_threshold"],
    "status": "pending"
  }
}
```
