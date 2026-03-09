# Caipture

Caipture is a self-hosted pipeline for digitizing historical photographs and reconstructing their context using computer vision, OCR, and AI-assisted metadata extraction.

The project is designed to convert physical photo collections into structured digital archive assets while preserving provenance, reproducibility, and privacy. Caipture processes images of photo prints and album pages, extracts contextual information (such as handwritten notes), and produces corrected images with structured metadata.

The system is intended for personal archives, small heritage collections, and experimental AI-assisted digitization workflows.

---

## Goals

- Digitize historical photographs with reproducible processing pipelines
- Extract contextual metadata from handwritten notes and album captions
- Preserve provenance and processing history
- Maintain privacy by keeping raw archives local
- Provide structured metadata suitable for archival standards
- Enable automated processing while allowing human verification

---

## Core Pipeline

A typical processing flow:

1. **Upload**
   - User uploads front and back images of a photograph
   - Optional album or contextual images can be added

2. **Image Processing**
   - Detect photo boundaries
   - Crop and rectify the image
   - Produce an archival-quality output

3. **Text Extraction**
   - OCR on photo back or album pages
   - Extract raw contextual text

4. **Metadata Interpretation**
   - Convert OCR output into structured metadata
   - Estimate dates, locations, and subjects
   - Track confidence and provenance

5. **Review**
   - Human validation of uncertain fields
   - Corrections and annotations

6. **Export**
   - Final corrected image
   - Embedded metadata (EXIF / IPTC / XMP)
   - Structured sidecar JSON

---

## Architecture Overview

Caipture uses a modular architecture composed of containerized services.

Typical components:

- Web interface for upload and review
- Image processing workers
- OCR processing workers
- Metadata interpretation services
- Export and archival tools
- AI gateway for external model access
- Job queue and orchestration layer

All services are containerized and designed to run locally.

---

## Security Model

Caipture separates responsibilities into trust zones:

- **Development zone**
  - Source code and CI pipelines
  - OpenClaw or coding assistants operate here

- **Processing zone**
  - Image processing and metadata pipeline

- **Archive zone**
  - Raw uploads and processed images

- **AI gateway**
  - Controlled outbound access to language models

Only minimal contextual data is sent to external AI services.

---

## Repository Structure
```
caipture/
├── docs/ # Design documents and architecture
├── services/ # Individual service implementations
├── tests/ # Unit and integration tests
├── deploy/ # Container and deployment configuration
├── scripts/ # Development and operational scripts
```

Detailed documentation is located in the `docs/` directory.

---

## Technology Stack

Planned core technologies:

- Python
- OpenCV
- Tesseract OCR
- FastAPI (web/API layer)
- Podman containers
- ExifTool for metadata writing

Optional components:

- Vision-language models
- OpenClaw automation
- GitHub CI/CD pipelines

---

## Development

The project is designed to run in a containerized environment.

Local development should support both:

- macOS (development workstation)
- Linux (target deployment on Raspberry Pi)

All services should be configurable via environment variables.

---

## License

Caipture is released under the **Apache License 2.0**.

---

## Status

Early design and proof-of-concept stage.

Initial goals:

- Define metadata schema
- Implement minimal processing pipeline
- Validate architecture on development environment
- Deploy proof-of-concept on Raspberry Pi
