from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class LlmGateway:
    enabled: bool

    def summarize_context(self, ocr_text: str) -> dict[str, object]:
        if not self.enabled:
            return {
                "description": "",
                "confidence": 0.0,
                "used_provider": False,
            }

        desc = "Historical photo"
        lower = ocr_text.lower()
        if "family" in lower:
            desc = "Family photo"
        elif "vacation" in lower:
            desc = "Vacation moment"

        return {
            "description": desc,
            "confidence": 0.7,
            "used_provider": False,
        }
