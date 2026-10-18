# Music Score Renderer Example

This example demonstrates how to use model-compose with the `music-score-renderer` component to rasterize a MusicXML score (`.xml`/`.musicxml`/`.mxl`) into one image per page. The output is a list of pages — SVG strings, single-page PDFs, or PNGs at a chosen DPI — all driven by [Verovio](https://www.verovio.org/) under the hood.

Use this when you have a MusicXML score (hand-authored, exported from a notation editor, or produced by an earlier step like [`music-score-loader`](../music-score-loader/)) and need a visual rendering — for a review UI, a PDF deliverable, or a thumbnail pipeline — without wiring up Verovio yourself.

## Overview

This example provides 3 workflows:

1. **Render Score as SVG** (default) — one SVG per page. Scales losslessly, best for web viewers.
2. **Render Score as PDF** — one single-page PDF per page, in A4-ish Verovio dimensions. Join externally if you need a single document.
3. **Render Score as PNG** — one raster PNG per page at a chosen DPI. Good for thumbnails or clients that cannot display SVG.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH
- Python dependencies are automatically installed on first run:
  - `verovio` — the rendering engine (always installed)
  - `svglib`, `reportlab` — only when a `pdf` action is declared
  - `resvg-py` — only when a `png` action is declared

### Setup

Navigate to this example directory:
```bash
cd examples/media-processing/music-score-renderer
```

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

   The service will start:
   - API endpoint: http://localhost:8080/api
   - Web UI: http://localhost:8081

2. **Run workflows:**

   **Using Web UI:**
   - Open the Web UI: http://localhost:8081
   - Select a workflow from the dropdown
   - Upload a MusicXML file (`.xml`, `.musicxml`, or compressed `.mxl`)
   - Click "Run Workflow"

   **Using CLI:**
   ```bash
   # Render each page as SVG (default)
   model-compose run render-score-svg --input '{"score": "/path/to/score.musicxml"}'

   # Render each page as a single-page PDF
   model-compose run render-score-pdf --input '{"score": "/path/to/score.musicxml"}'

   # Render each page as PNG at 300 DPI
   model-compose run render-score-png --input '{"score": "/path/to/score.musicxml"}'
   ```

   **Using API:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=render-score-svg" \
     -F "score=@/path/to/score.musicxml"
   ```

## Component Details

### Music Score Renderer Component

- **Type**: `music-score-renderer`
- **Purpose**: Convert a MusicXML score into a per-page image sequence (SVG, PDF, or PNG) using Verovio's engraving layout.
- **Drivers**:
  - `verovio` — Verovio-based rendering (default)

Page geometry is expressed in **Verovio units**, where 1 unit ≈ 0.1 mm. The defaults (`page_width: 2100`, `page_height: 2970`) match A4 at that scale. `scale` is a percent (100 = Verovio's default size), and `margin` can be either a single scalar (same value for all four sides) or an object with explicit `top`/`right`/`bottom`/`left`.

To produce the MusicXML input itself from a MIDI file or an existing score, use [`music-score-loader`](../music-score-loader/) upstream — though note that the loader emits structured `MusicScore` data, so you would still need a MusicXML serialization step if you want to render output from a MIDI source.

## Workflow Details

### 1. Render Score as SVG

**ID**: `render-score-svg`

Produces one SVG per page. SVG scales losslessly and is the native output of Verovio — the other two formats are derived from this one.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `score` | file | Yes | - | MusicXML file to render (`.xml`, `.musicxml`, or `.mxl`) |

#### Output

A list of SVG files in page order (`page-1.svg`, `page-2.svg`, …), each with content type `image/svg+xml`.

---

### 2. Render Score as PDF

**ID**: `render-score-pdf`

Produces one single-page PDF per page. The YAML sets A4-ish page dimensions (`page_width: 2100`, `page_height: 2970`) and a uniform 60-unit margin.

PDF generation goes through `svglib` + `reportlab`: each Verovio SVG page is converted into a ReportLab drawing and emitted as its own PDF. If you need a single multi-page PDF, combine the outputs externally (e.g. with `pdfunite` or `pypdf`).

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `score` | file | Yes | - | MusicXML file to render |

#### Output

A list of PDF files in page order (`page-1.pdf`, `page-2.pdf`, …), each with content type `application/pdf`.

---

### 3. Render Score as PNG

**ID**: `render-score-png`

Produces one PNG per page by rasterizing each Verovio SVG with `resvg-py` at the configured DPI. Useful for thumbnails, previews, or anywhere SVG rendering is not available.

The example sets `dpi: 300` for a print-quality raster and uses an asymmetric margin (`top: 80`, `right: 60`, `bottom: 80`, `left: 60`) to illustrate the per-side object form.

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `score` | file | Yes | - | MusicXML file to render |

#### Output

A list of PNG images in page order (`page-1.png`, `page-2.png`, …).

---

### Action Options Reference

All three actions share the same option surface — only `format` and a few per-format defaults differ.

| Option | Type | Default | Applies to | Description |
|--------|------|---------|------------|-------------|
| `source` | file / list of files | required | all | MusicXML input; path, upload stream, or raw bytes. |
| `format` | `svg` \| `pdf` \| `png` | `svg` | all | Output format for each page. |
| `page_width` | number | `2100` | all | Page width in Verovio units (1 unit ≈ 0.1 mm). |
| `page_height` | number | `2970` | all | Page height in Verovio units. |
| `scale` | number | `100` | all | Rendering scale percent; 100 is Verovio's default size. |
| `margin` | number or `{top,right,bottom,left}` | `50` | all | Scalar applies to all four sides; object sets each independently. |
| `dpi` | number | `150` | `png` only | Rasterization resolution. Ignored for `svg` and `pdf`. |
