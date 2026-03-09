# Caipture — Metadata Schema Specification

Version: 0.1
Status: Draft
Applies to: Photo Item Metadata

---

# 1. Purpose

This document defines the **canonical metadata schema** used by Caipture to represent historical photograph information.

The schema serves several goals:

* store structured metadata derived from photographs
* preserve original contextual evidence
* track provenance and confidence
* support reproducible processing pipelines
* allow human corrections without losing earlier interpretations
* provide mappings to archival metadata standards

The schema is intentionally **separate from EXIF/IPTC/XMP** so that historical uncertainty and provenance can be represented correctly.

---

# 2. Design Principles

## 2.1 Canonical Internal Representation

Caipture maintains its own canonical metadata representation.

External metadata standards are used only for export.

This allows:

* uncertain dates
* multiple evidence sources
* competing interpretations
* provenance tracking

---

## 2.2 Evidence Preservation

All extracted evidence must be preserved.

Examples:

* raw OCR text
* album captions
* handwritten notes
* model-generated interpretations

The system must never overwrite or discard evidence.

---

## 2.3 Confidence Tracking

Each interpreted field must include a **confidence value**.

Confidence values range from:

```text
0.0 – 1.0
```

Meaning:

* `1.0` very high certainty
* `0.7` likely correct
* `0.5` uncertain guess
* `<0.5` weak hypothesis

---

## 2.4 Provenance

Each metadata field must record its source.

Example sources:

* `back_note`
* `album_caption`
* `vision_model`
* `manual_entry`
* `ocr_text`

---

## 2.5 Historical Date Support

Historical photographs often have imprecise dates.

The schema must support:

* exact date
* year only
* month range
* seasonal range
* approximate date

Examples:

```text
1934
June 1934
Summer 1934
circa 1934
1930–1935
```

---

# 3. Metadata Object Structure

Each processed photograph corresponds to one metadata document.

Top-level structure:

```json id="json1"
{
  "schema_version": "0.1.0",
  "item_id": "string",
  "job_id": "string",
  "created_at": "timestamp",
  "status": "processing_state",
  "inputs": {},
  "derived": {},
  "historical_metadata": {},
  "digitization_metadata": {},
  "review": {},
  "export_mapping": {}
}
```

---

# 4. Identification Fields

## 4.1 schema_version

Defines the version of the metadata schema.

Example:

```json id="json2"
"schema_version": "0.1.0"
```

---

## 4.2 item_id

Stable identifier for the photograph.

Example:

```json id="json3"
"item_id": "photo_000124"
```

---

## 4.3 job_id

Identifier for the processing job that produced this metadata.

Example:

```json id="json4"
"job_id": "job_20260308_000124"
```

---

# 5. Processing Status

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

Example:

```json id="json5"
"status": "review_required"
```

---

# 6. Input References

The `inputs` section references raw uploaded files.

Example:

```json id="json6"
"inputs": {
  "front_image": {
    "path": "inputs/front.jpg",
    "sha256": "hash"
  },
  "back_image": {
    "path": "inputs/back.jpg",
    "sha256": "hash"
  },
  "context_images": [
    {
      "path": "inputs/album_page.jpg",
      "sha256": "hash"
    }
  ]
}
```

Purpose:

* maintain traceability
* allow reproducibility
* verify file integrity

---

# 7. Derived Artifacts

Derived artifacts are outputs of processing steps.

Example:

```json id="json7"
"derived": {
  "front_cropped": "derived/front_cropped.jpg",
  "front_rectified": "derived/front_rectified.jpg",
  "back_ocr_text": "derived/back_ocr.txt",
  "context_ocr_text": "derived/context_ocr.txt"
}
```

Derived artifacts must be immutable.

---

# 8. Historical Metadata

The `historical_metadata` section stores interpreted contextual data.

Fields include:

* date
* location
* people
* description
* event

---

## 8.1 Date Object

Example:

```json id="json8"
"date": {
  "raw_text": "Summer 1934",
  "from": "1934-06-01",
  "to": "1934-08-31",
  "precision": "season",
  "confidence": 0.78,
  "sources": ["back_note", "album_caption"]
}
```

### Fields

| Field      | Description                 |
| ---------- | --------------------------- |
| raw_text   | original textual reference  |
| from       | earliest possible date      |
| to         | latest possible date        |
| precision  | year/month/day/season/range |
| confidence | confidence value            |
| sources    | evidence sources            |

---

## 8.2 Location Object

Example:

```json id="json9"
"location": {
  "raw_text": "Enschede",
  "normalized": {
    "name": "Enschede, Overijssel, Netherlands",
    "lat": 52.2215,
    "lon": 6.8937
  },
  "confidence": 0.74,
  "sources": ["back_note"]
}
```

---

## 8.3 People

Example:

```json id="json10"
"people": [
  {
    "name": "Jan de Vries",
    "role": "possible_subject",
    "confidence": 0.62,
    "sources": ["album_caption"]
  }
]
```

Possible roles:

```text
subject
possible_subject
photographer
unknown_person
```

---

## 8.4 Description

Example:

```json id="json11"
"description": {
  "text": "Family standing in front of a brick house.",
  "confidence": 0.55,
  "sources": ["vision_model"]
}
```

---

## 8.5 Event (Optional)

Example:

```json id="json12"
"event": {
  "name": "Family vacation",
  "confidence": 0.4,
  "sources": ["album_caption"]
}
```

---

# 9. Digitization Metadata

This section describes the digitization process.

Example:

```json id="json13"
"digitization_metadata": {
  "digitized_at": "2026-03-08T14:32:10Z",
  "device": "iPhone 15 Pro",
  "operator": "twan",
  "pipeline_version": "0.1.0"
}
```

---

# 10. Review Metadata

Example:

```json id="json14"
"review": {
  "required": true,
  "reasons": [
    "date_precision_low",
    "person_confidence_low"
  ],
  "approved_by": null,
  "approved_at": null
}
```

Purpose:

* enforce human validation
* record review history

---

# 11. Export Mapping

This section maps internal metadata to external formats.

Example:

```json id="json15"
"export_mapping": {
  "exif": {
    "DateTimeDigitized": "2026:03:08 14:32:10"
  },
  "iptc": {
    "CaptionAbstract": "Family standing in front of a brick house."
  },
  "xmp": {
    "photos:HistoricalDateFrom": "1934-06-01",
    "photos:HistoricalDateTo": "1934-08-31"
  }
}
```

Mapping occurs during export.

---

# 12. Confidence Thresholds

Recommended thresholds:

| Range   | Meaning                  |
| ------- | ------------------------ |
| ≥0.9    | safe automation          |
| 0.6–0.9 | human review recommended |
| <0.6    | weak hypothesis          |

---

# 13. Schema Versioning

The schema must support version evolution.

Rules:

* schema_version must be recorded
* backward compatibility preferred
* migrations must be documented

---

# 14. Validation

Metadata documents must pass validation checks before export.

Validation includes:

* schema compliance
* required fields present
* confidence values within range
* date ranges valid

---

# 15. Storage

Metadata files must be stored with job artifacts.

Example:

```id="json16"
storage/jobs/<job_id>/metadata/photo_item.json
```

---

# 16. Future Extensions

Possible schema extensions:

* face clusters
* duplicate detection
* timeline reconstruction
* collection grouping
* improved provenance tracking

These extensions must maintain backward compatibility.

---

# 17. Example Full Metadata Document

```json id="json17"
{
  "schema_version": "0.1.0",
  "item_id": "photo_000124",
  "job_id": "job_20260308_000124",
  "created_at": "2026-03-08T14:32:10Z",
  "status": "review_required",

  "inputs": {
    "front_image": {
      "path": "inputs/front.jpg",
      "sha256": "..."
    },
    "back_image": {
      "path": "inputs/back.jpg",
      "sha256": "..."
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
      "sources": ["back_note"]
    },
    "location": {
      "raw_text": "Enschede",
      "normalized": {
        "name": "Enschede, Netherlands",
        "lat": 52.2215,
        "lon": 6.8937
      },
      "confidence": 0.74,
      "sources": ["back_note"]
    },
    "people": [],
    "description": {
      "text": "Family standing in front of a house.",
      "confidence": 0.55,
      "sources": ["vision_model"]
    }
  },

  "digitization_metadata": {
    "digitized_at": "2026-03-08T14:32:10Z",
    "device": "iPhone",
    "pipeline_version": "0.1.0"
  },

  "review": {
    "required": true,
    "reasons": ["low_description_confidence"]
  }
}
```
