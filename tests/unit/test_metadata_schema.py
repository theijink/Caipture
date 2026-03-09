from __future__ import annotations

import unittest

from caipture.metadata import validate_metadata_document


class MetadataSchemaTests(unittest.TestCase):
    def test_validator_accepts_minimal_valid_doc(self) -> None:
        doc = {
            "schema_version": "0.2.0",
            "item_id": "item_1",
            "job_id": "job_1",
            "created_at": "2026-03-09T10:00:00Z",
            "updated_at": "2026-03-09T10:00:00Z",
            "status": "completed",
            "inputs": {},
            "derived": {},
            "historical_metadata": {
                "date": {
                    "raw_text": "1934",
                    "from": "1934-01-01",
                    "to": "1934-12-31",
                    "precision": "year",
                    "confidence": 0.7,
                    "sources": [{"source_type": "ocr_text", "source_ref": "derived/back_ocr.txt"}],
                },
                "location": {
                    "raw_text": "Enschede",
                    "normalized": {"name": "Enschede"},
                    "confidence": 0.7,
                    "sources": [{"source_type": "ocr_text", "source_ref": "derived/back_ocr.txt"}],
                },
                "people": [],
            },
            "digitization_metadata": {"digitized_at": "2026-03-09T10:00:00Z"},
            "review": {"required": False, "reasons": [], "status": "approved"},
        }
        self.assertEqual(validate_metadata_document(doc), [])

    def test_validator_rejects_invalid_confidence(self) -> None:
        doc = {
            "schema_version": "0.2.0",
            "item_id": "item_1",
            "job_id": "job_1",
            "created_at": "2026-03-09T10:00:00Z",
            "updated_at": "2026-03-09T10:00:00Z",
            "status": "completed",
            "inputs": {},
            "derived": {},
            "historical_metadata": {
                "date": {
                    "raw_text": "1934",
                    "from": "1934-01-01",
                    "to": "1934-12-31",
                    "precision": "year",
                    "confidence": 9.0,
                    "sources": [{"source_type": "ocr_text", "source_ref": "derived/back_ocr.txt"}],
                }
            },
            "digitization_metadata": {"digitized_at": "2026-03-09T10:00:00Z"},
            "review": {"required": False, "reasons": [], "status": "approved"},
        }
        errors = validate_metadata_document(doc)
        self.assertTrue(any("confidence" in err for err in errors))
