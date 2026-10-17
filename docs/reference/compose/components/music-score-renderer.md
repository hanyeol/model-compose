# Music Score Renderer Component

The music score renderer component takes a **MusicXML score** and engraves it into one or more **page images** — SVG for the web, PDF for print, or PNG for raster output. Use it to visualize scores produced by upstream tools, build score-review UIs, or embed engraved pages in generated documents.

Rendering is delegated to [Verovio](https://www.verovio.org/), an open-source music engraver. SVG is Verovio's native output; PDF is produced by converting the SVG with svglib + reportlab, and PNG by rasterizing the SVG with resvg-py.

For symbolic score **parsing** (score → `MusicScore`), use [`music-score-loader`](music-score-loader.md). This component is purely for rendering already-symbolic data to a visual format.

## Basic Configuration

```yaml
component:
  type: music-score-renderer
  action:
    source: ${input.score as file}
    format: svg
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `music-score-renderer` |
| `driver` | string | `verovio` | Rendering backend (currently only `verovio`) |
| `actions` | array | `[]` | List of render actions |

### Action Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `source` | any | **required** | MusicXML source: file path, upload stream, raw bytes, or variable reference |
| `format` | string | `svg` | Output format: `svg`, `pdf`, or `png` |
| `page_width` | float | `2100.0` | Page width in Verovio units (1 unit = 0.1 mm; 2100 ≈ A4 width) |
| `page_height` | float | `2970.0` | Page height in Verovio units (2970 ≈ A4 height) |
| `scale` | integer | `100` | Rendering scale percent; `100` is Verovio's default size |
| `margin` | object \| float | `null` | Page margins; a scalar applies to all four sides, or set `top`/`right`/`bottom`/`left` individually. Each side defaults to 50 units when omitted. |
| `dpi` | integer | `150` | Resolution of PNG rasterization. Ignored for `svg` and `pdf`. |
| `batch_size` | integer | `null` | Number of sources rendered per batch |
| `output` | string | `null` | Output template applied to the rendered pages |

## Supported Drivers

### Verovio

Renders MusicXML through the Verovio toolkit. Verovio handles the engraving (note layout, slurs, beams, dynamics) and produces one SVG per page; PDF and PNG are derived from that SVG.

```yaml
component:
  type: music-score-renderer
  driver: verovio
```

**Auto-installed dependencies:** `verovio`, `svglib`, `reportlab`, `resvg-py`

#### Supported Input Formats

| Format | Extensions | Notes |
|--------|------------|-------|
| MusicXML | `.xml`, `.musicxml` | Verovio's native MusicXML import |
| MusicXML (compressed) | `.mxl` | ZIP container; Verovio unwraps it automatically |

MIDI is **not** supported as input — Verovio only produces MIDI output, not consumes it. Convert MIDI to MusicXML upstream (e.g. with music21 or a DAW export) if you need to render MIDI data.

#### Supported Output Formats

| Format | Backend | Notes |
|--------|---------|-------|
| `svg` | Verovio (native) | Vector output; one SVG per page. Best for web display and further vector editing. |
| `pdf` | svglib + reportlab | One single-page PDF per score page. Suitable for print; vector preserved. |
| `png` | resvg-py | Raster output at `dpi` DPI. Pixel size = (`page_width` / 10 mm) × DPI / 25.4 per axis. |

## Output Format

The action returns a **list of `StreamResource` objects** — one entry per rendered page, in page order. Each entry has a `filename` (`page-1.svg`, `page-2.pdf`, …) and a content type matching the output format (`image/svg+xml`, `application/pdf`, `image/png`).

For single-input renders the batch dimension collapses, so the action's `${result}` is directly the per-page list. For batched inputs, `${result}` is a list of per-page lists.

```python
# Single input, format=svg, 3-page score
result = [
    BytesStreamResource(..., filename="page-1.svg"),   # image/svg+xml
    BytesStreamResource(..., filename="page-2.svg"),
    BytesStreamResource(..., filename="page-3.svg"),
]

# Batched inputs (two scores), format=pdf
result = [
    [BytesStreamResource(..., filename="page-1.pdf"), BytesStreamResource(..., filename="page-2.pdf")],
    [BytesStreamResource(..., filename="page-1.pdf")],
]
```

### Page Layout

- `page_width` and `page_height` set the **engraving canvas** — Verovio uses them to decide how many measures/systems fit on a page, so taller pages mean fewer pages overall.
- `scale` is independent: it zooms the engraving uniformly (notes, staves, text). Doubling `scale` without changing page size will push content off the page unless margins are enlarged too.
- `margin` carves white space inside the canvas. Combined example:

```yaml
action:
  source: ${input.score as file}
  format: svg
  page_width: 2100     # 210 mm (A4 width)
  page_height: 2970    # 297 mm (A4 height)
  scale: 100
  margin:
    top: 80
    right: 60
    bottom: 80
    left: 60
```

### PNG Resolution

For PNG output, `dpi` controls the final pixel density. The output pixel count is:

```
pixel_width  = (page_width  / 10 mm) × dpi / 25.4
pixel_height = (page_height / 10 mm) × dpi / 25.4
```

Common values:

| DPI | Use case |
|-----|----------|
| 96 | Screen display (CSS default) |
| 150 | Default; readable on retina/HiDPI screens |
| 300 | Print quality |

## Example Workflow

Render a MusicXML score to three PNG pages at print resolution:

```yaml
workflow:
  job:
    component: score-renderer
    action: render-pages
    input:
      source: ${input.score as file}

components:
  - id: score-renderer
    type: music-score-renderer
    action:
      id: render-pages
      source: ${input.source as file}
      format: png
      dpi: 300
      page_width: 2100
      page_height: 2970
      margin: 60
```

## Related Components

- [`music-score-loader`](music-score-loader.md) — Parses the same MusicXML files into a `MusicScore` for programmatic use (vs this component's visual output)
- [`image-processor`](image-processor.md) — For post-processing PNG output (resize, crop, format conversion)
- [`document-loader`](document-loader.md) — To embed rendered PDF pages into a document pipeline

## Known Limitations

- **MIDI input is not supported** — Verovio cannot parse MIDI. Use `music-score-loader` to read MIDI into a `MusicScore`, or convert MIDI → MusicXML upstream.
- **ABC, MEI, Humdrum, and PAE** are accepted by the Verovio toolkit but not currently exposed by this component.
- The **page layout is Verovio's choice** — the component does not expose fine-grained engraving options (beam angles, slur shapes, spacing rules). Advanced typesetting should edit the MusicXML directly or use dedicated engraving software.
- **PDF/PNG rendering goes through SVG** — advanced SVG features that svglib/resvg don't fully support (filters, complex gradients) may render differently than in a browser.
