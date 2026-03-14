# ADR 0005 - Subject-First Upload, Optional Back, and In-Page Job Actions

## Status
Accepted

## Context
Field usage showed that a physical back photo is not always available. Requiring `back.png` blocked practical digitization sessions and forced low-quality placeholders. The dashboard also opened intermediate pages for approve/upload actions, which interrupted operator flow.

## Decision
1. Canonical upload input is now `subject_image` (required).
2. `back_image` is optional.
3. Manual metadata hints (`date`, `location`, `comment`) are accepted at upload and fused with OCR evidence.
4. Dashboard actions (`approve`, `delete`) are executed in place via async POST calls; no post-action blank pages.
5. Queue and dashboard keep newest operational evidence visible first (recent journal entries newest on top).

## Consequences
- Better usability for mobile and ad-hoc capture sessions.
- Metadata quality improves when OCR is weak by allowing manual evidence.
- Deleting a job now removes both queue records and job storage artifacts in one operation.
- Existing internals still store input under `front_input` for backward compatibility; UI and API semantics are `subject`.

## Follow-up
- Add authenticated access controls before exposing dashboard beyond trusted LAN.
- Add model-assisted OCR fallback provider for difficult handwriting when enabled.
