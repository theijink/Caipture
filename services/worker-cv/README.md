# CV Worker (`services/worker-cv`)

## Purpose

Processes uploaded subject image into corrected output artifacts.

Core steps:

- validate basic image quality constraints
- detect photo boundary/shape
- crop original photo from full upload
- apply perspective correction where detectable
- resize to configured output bounds

## Implementation

- preferred path uses OpenCV contour + perspective transform
- fallback path uses ImageMagick trim/resize
- artifacts:
  - `derived/front_cropped.png`
  - `derived/front_rectified.png`
  - `derived/validation_report.json`

## Run

```bash
PYTHONPATH=src python3 services/worker-cv/main.py
```
