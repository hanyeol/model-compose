# Image Drawing Component

The image drawing component draws shapes, text, and bitmaps onto existing images. It wraps Pillow's `ImageDraw` API so workflows can annotate detection boxes, render captions, overlay skeletons, mark keypoints, and other visual overlays without writing Python. Each action returns a new image with the requested drawing composited on top.

## Basic Configuration

```yaml
component:
  type: image-drawing
  action:
    method: rectangle
    image: ${input.image}
    x: 10
    y: 10
    width: 200
    height: 120
    outline: red
    line_width: 3
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `image-drawing` |
| `driver` | string | `native` | Drawing backend. Currently only `native` (Pillow) is supported. |
| `actions` | array | `[]` | List of drawing actions |

### Common Action Configuration

All image drawing actions share these common settings:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `method` | string | **required** | Drawing method: `point`, `line`, `arc`, `chord`, `pieslice`, `ellipse`, `circle`, `rectangle`, `polygon`, `regular-polygon`, `text`, `multiline-text`, `bitmap` |
| `image` | string / array | **required** | Base image(s) — a single image or a list of images |
| `batch_size` | integer / string | `null` | Number of input images to process in a single batch |
| `output` | any | `null` | Output variable mapping |

### Common Field Semantics

Most methods share the same drawing-related fields:

| Field | Type | Meaning |
|-------|------|---------|
| `x`, `y` | number | Coordinates (top-left corner for bounding-box methods, center for `circle` / `regular-polygon`, anchor point for `text` / `multiline-text` / `bitmap`) |
| `width`, `height` | number | Bounding-box dimensions in pixels (rectangle-like methods) |
| `radius` | number | Circle radius, corner radius, or bounding-circle radius depending on the method |
| `points` | list | Sequence of `(x, y)` pairs for point-list methods (`point`, `line`, `polygon`) |
| `fill` | color | Interior fill color (or the pixel color for `point` / `line` / `text`). Accepts a name (`"red"`), hex string (`"#ff0000"`, `"#00000080"`), RGB tuple `[r, g, b]`, or RGBA tuple `[r, g, b, a]`. `null` means no fill. |
| `outline` | color | Outline color for closed shapes. `null` means no outline. |
| `line_width` | integer | Outline thickness in pixels (or line thickness for `line`). |

Coordinates use Pillow's convention: origin `(0, 0)` at the upper-left, `x` increases to the right, `y` increases downward. Angles are in degrees, measured clockwise from the 3 o'clock position.

## Drawing Methods

### Point

Draw one or more individual pixels:

```yaml
component:
  type: image-drawing
  action:
    method: point
    image: ${input.image}
    points: [[10, 20], [30, 40], [50, 60]]
    fill: red
    output: ${output}
```

**Point Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `points` | list | **required** | List of `(x, y)` pairs to plot |
| `fill` | color | `null` | Pixel color |

### Line

Draw a straight line or connected polyline:

```yaml
component:
  type: image-drawing
  action:
    method: line
    image: ${input.image}
    points: [[0, 0], [100, 100], [200, 50]]
    fill: blue
    line_width: 3
    joint: curve
    output: ${output}
```

**Line Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `points` | list | **required** | Vertex points connected in order |
| `fill` | color | `null` | Line color |
| `line_width` | integer | `1` | Line thickness in pixels |
| `joint` | string | `null` | Segment joint style; `curve` rounds corners between segments |

### Arc

Draw a circular arc inside a bounding box:

```yaml
component:
  type: image-drawing
  action:
    method: arc
    image: ${input.image}
    x: 20
    y: 20
    width: 100
    height: 100
    start: 0
    end: 90
    fill: green
    line_width: 2
    output: ${output}
```

**Arc Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `x` | number | **required** | X coordinate of the bounding-box top-left corner |
| `y` | number | **required** | Y coordinate of the bounding-box top-left corner |
| `width` | number | **required** | Bounding-box width in pixels |
| `height` | number | **required** | Bounding-box height in pixels |
| `start` | number | **required** | Starting angle in degrees (clockwise from 3 o'clock) |
| `end` | number | **required** | Ending angle in degrees (clockwise from 3 o'clock) |
| `fill` | color | `null` | Arc color |
| `line_width` | integer | `1` | Arc line thickness in pixels |

### Chord

Draw an arc whose endpoints are connected by a straight line, forming a closed shape:

```yaml
component:
  type: image-drawing
  action:
    method: chord
    image: ${input.image}
    x: 20
    y: 20
    width: 100
    height: 100
    start: 0
    end: 120
    fill: "#ffcc00"
    outline: black
    line_width: 2
    output: ${output}
```

**Chord Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `x`, `y`, `width`, `height` | number | **required** | Bounding box |
| `start` | number | **required** | Starting angle in degrees |
| `end` | number | **required** | Ending angle in degrees |
| `fill` | color | `null` | Interior fill color |
| `outline` | color | `null` | Outline color |
| `line_width` | integer | `1` | Outline thickness in pixels |

### Pieslice

Draw a pie slice — an arc with both endpoints connected to the bounding-box center:

```yaml
component:
  type: image-drawing
  action:
    method: pieslice
    image: ${input.image}
    x: 20
    y: 20
    width: 100
    height: 100
    start: 30
    end: 150
    fill: orange
    outline: black
    output: ${output}
```

**Pieslice Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `x`, `y`, `width`, `height` | number | **required** | Bounding box |
| `start` | number | **required** | Starting angle in degrees |
| `end` | number | **required** | Ending angle in degrees |
| `fill` | color | `null` | Interior fill color |
| `outline` | color | `null` | Outline color |
| `line_width` | integer | `1` | Outline thickness in pixels |

### Ellipse

Draw an ellipse inscribed in a bounding box:

```yaml
component:
  type: image-drawing
  action:
    method: ellipse
    image: ${input.image}
    x: 20
    y: 20
    width: 200
    height: 100
    outline: blue
    line_width: 2
    output: ${output}
```

**Ellipse Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `x`, `y`, `width`, `height` | number | **required** | Bounding box |
| `fill` | color | `null` | Interior fill color |
| `outline` | color | `null` | Outline color |
| `line_width` | integer | `1` | Outline thickness in pixels |

### Circle

Draw a circle centered at `(x, y)`:

```yaml
component:
  type: image-drawing
  action:
    method: circle
    image: ${input.image}
    x: 100
    y: 100
    radius: 40
    outline: red
    line_width: 2
    output: ${output}
```

**Circle Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `x` | number | **required** | X coordinate of the circle center |
| `y` | number | **required** | Y coordinate of the circle center |
| `radius` | number | **required** | Circle radius in pixels |
| `fill` | color | `null` | Interior fill color |
| `outline` | color | `null` | Outline color |
| `line_width` | integer | `1` | Outline thickness in pixels |

### Rectangle

Draw an axis-aligned rectangle. If `radius` is set, corners are rounded:

```yaml
component:
  type: image-drawing
  action:
    method: rectangle
    image: ${input.image}
    x: 10
    y: 10
    width: 200
    height: 120
    radius: 12
    outline: "#00aaff"
    line_width: 3
    corners: [true, true, false, false]
    output: ${output}
```

**Rectangle Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `x` | number | **required** | X coordinate of the top-left corner |
| `y` | number | **required** | Y coordinate of the top-left corner |
| `width` | number | **required** | Rectangle width in pixels |
| `height` | number | **required** | Rectangle height in pixels |
| `radius` | number | `null` | Corner radius in pixels. When set, the rectangle is drawn with rounded corners. |
| `fill` | color | `null` | Interior fill color |
| `outline` | color | `null` | Outline color |
| `line_width` | integer | `1` | Outline thickness in pixels |
| `corners` | list | `null` | Per-corner rounding flags `[top-left, top-right, bottom-right, bottom-left]`. Only applied when `radius` is set. |

This is the most common method for object/face detection bounding-box overlays. When drawing many boxes on the same image, use multiple actions or precompute per-box parameters via variables.

### Polygon

Draw an arbitrary closed polygon:

```yaml
component:
  type: image-drawing
  action:
    method: polygon
    image: ${input.image}
    points: [[10, 10], [100, 30], [80, 100], [20, 90]]
    fill: "#00ff0080"
    outline: black
    line_width: 2
    output: ${output}
```

**Polygon Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `points` | list | **required** | Vertex points |
| `fill` | color | `null` | Interior fill color |
| `outline` | color | `null` | Outline color |
| `line_width` | integer | `1` | Outline thickness in pixels |

Use `polygon` for segmentation masks, pose skeleton outlines, or any hand-authored shape.

### Regular Polygon

Draw a regular polygon (equal sides) inscribed in a circle:

```yaml
component:
  type: image-drawing
  action:
    method: regular-polygon
    image: ${input.image}
    x: 100
    y: 100
    radius: 40
    sides: 6
    rotation: 30
    outline: purple
    line_width: 2
    output: ${output}
```

**Regular Polygon Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `x` | number | **required** | X coordinate of the inscribing-circle center |
| `y` | number | **required** | Y coordinate of the inscribing-circle center |
| `radius` | number | **required** | Radius of the inscribing circle in pixels |
| `sides` | integer | **required** | Number of polygon sides (`>= 3`) |
| `rotation` | number | `0` | Polygon rotation in degrees |
| `fill` | color | `null` | Interior fill color |
| `outline` | color | `null` | Outline color |
| `line_width` | integer | `1` | Outline thickness in pixels |

Use for stars (`sides: 5` with rotation), hexagon tiles, triangular markers, or diamond shapes (`sides: 4, rotation: 45`).

### Text

Render single-line (or `\n`-embedded) text at an anchor point:

```yaml
component:
  type: image-drawing
  action:
    method: text
    image: ${input.image}
    x: 20
    y: 20
    text: "Face (0.98)"
    fill: white
    font:
      path: /usr/share/fonts/DejaVuSans-Bold.ttf
      size: 24
    anchor: la
    stroke_width: 2
    stroke_fill: black
    output: ${output}
```

**Text Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `x` | number | **required** | X coordinate of the text anchor point |
| `y` | number | **required** | Y coordinate of the text anchor point |
| `text` | string | **required** | Text to render |
| `fill` | color | `null` | Text color |
| `font` | object | `null` | Font settings (see below). Falls back to Pillow's default font when omitted. |
| `anchor` | string | `null` | Two-character anchor code (e.g. `la`, `mm`, `rd`). See Pillow's [text anchors](https://pillow.readthedocs.io/en/stable/handbook/text-anchors.html). |
| `spacing` | integer | `4` | Line spacing in pixels for embedded newlines |
| `align` | string | `left` | Horizontal alignment for embedded newlines: `left`, `center`, `right` |
| `stroke_width` | integer | `0` | Text stroke (outline) width in pixels — improves legibility on busy backgrounds |
| `stroke_fill` | color | `null` | Text stroke color |

**Font Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `path` | string | `null` | Path to a TrueType font file. When omitted, Pillow's built-in default font is used. |
| `size` | integer | `null` | Font size in pixels |
| `index` | integer | `0` | Face index when the font file contains multiple faces |
| `encoding` | string | `unic` | Font encoding passed to Pillow's `ImageFont` |

Text is the go-to method for detection class labels, timestamps, watermarks, or captions. Combine with a filled `rectangle` behind the text for readable label backgrounds.

### Multiline Text

Render multi-line text with explicit line spacing and alignment:

```yaml
component:
  type: image-drawing
  action:
    method: multiline-text
    image: ${input.image}
    x: 20
    y: 20
    text: |
      Line one
      Line two
      Line three
    fill: white
    font:
      path: /usr/share/fonts/DejaVuSans.ttf
      size: 18
    spacing: 6
    align: center
    output: ${output}
```

**Multiline Text Configuration:** Identical fields to `text`, but `spacing` and `align` are the primary controls for how lines are laid out.

### Bitmap

Stamp a bitmap (mask) at `(x, y)`, colored by `fill` where the mask is non-zero:

```yaml
component:
  type: image-drawing
  action:
    method: bitmap
    image: ${input.image}
    x: 30
    y: 30
    bitmap: ${input.icon_mask}
    fill: red
    output: ${output}
```

**Bitmap Configuration:**

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `x` | number | **required** | X coordinate where the bitmap's top-left corner is stamped |
| `y` | number | **required** | Y coordinate where the bitmap's top-left corner is stamped |
| `bitmap` | string | **required** | Bitmap image; non-zero pixels form the mask |
| `fill` | color | `null` | Color applied through the bitmap mask |

Use for icons, glyphs, or sprite-style stamps whose mask is a separate image.

## Multiple Actions Configuration

Chain multiple drawings by feeding one action's output as the next action's input:

```yaml
workflows:
  - id: annotate-detection
    jobs:
      - id: draw-box
        component: image-drawing
        action: draw-face-box
        input:
          image: ${input.photo}
        output:
          annotated: ${output}

      - id: draw-label
        component: image-drawing
        action: draw-face-label
        input:
          image: ${jobs.draw-box.output.annotated}
        depends_on: [ draw-box ]

components:
  - id: image-drawing
    type: image-drawing
    actions:
      - id: draw-face-box
        method: rectangle
        image: ${input.image}
        x: ${input.box.x}
        y: ${input.box.y}
        width: ${input.box.width}
        height: ${input.box.height}
        outline: "#00ff00"
        line_width: 3
        output: ${output}

      - id: draw-face-label
        method: text
        image: ${input.image}
        x: ${input.box.x}
        y: ${input.box.y - 24}
        text: "Face"
        fill: white
        font:
          path: /usr/share/fonts/DejaVuSans-Bold.ttf
          size: 20
        stroke_width: 2
        stroke_fill: black
        output: ${output}
```

## Usage Examples

### Detection Box Overlay

Draw a bounding box + label for a single detection:

```yaml
workflows:
  - id: annotate-face
    jobs:
      - id: box
        component: image-drawing
        action: face-box
        input:
          image: ${input.photo}
          box: ${input.face.bounding_box}
        output:
          boxed: ${output}

      - id: label
        component: image-drawing
        action: face-label
        input:
          image: ${jobs.box.output.boxed}
          box: ${input.face.bounding_box}
          score: ${input.face.score}
        depends_on: [ box ]

components:
  - id: image-drawing
    type: image-drawing
    actions:
      - id: face-box
        method: rectangle
        image: ${input.image}
        x: ${input.box.x}
        y: ${input.box.y}
        width: ${input.box.width}
        height: ${input.box.height}
        outline: "#00ff00"
        line_width: 3
        output: ${output}

      - id: face-label
        method: text
        image: ${input.image}
        x: ${input.box.x}
        y: ${input.box.y - 22}
        text: "Face ${input.score}"
        fill: white
        font:
          path: /usr/share/fonts/DejaVuSans-Bold.ttf
          size: 18
        stroke_width: 2
        stroke_fill: black
        output: ${output}
```

For batch annotation across many detections, either loop the drawing action per detection in a workflow, or wrap the drawing calls in a workflow-level `for-each` if your pipeline supports it.

### Keypoint / Landmark Overlay

Mark facial landmarks or pose keypoints with small circles:

```yaml
component:
  type: image-drawing
  action:
    method: circle
    image: ${input.image}
    x: ${input.landmark.x}
    y: ${input.landmark.y}
    radius: 3
    fill: "#ff0044"
    output: ${output}
```

### Segmentation Mask Outline

Trace a segmentation polygon over an image:

```yaml
component:
  type: image-drawing
  action:
    method: polygon
    image: ${input.image}
    points: ${input.segmentation.contour}
    fill: "#00ff0040"
    outline: "#00ff00"
    line_width: 2
    output: ${output}
```

`fill` uses an alpha value to keep the underlying pixels visible through the mask overlay.

### Skeleton / Pose Edges

Draw connecting lines between pose keypoints:

```yaml
component:
  type: image-drawing
  action:
    method: line
    image: ${input.image}
    points:
      - [ ${input.pose.left_shoulder.x}, ${input.pose.left_shoulder.y} ]
      - [ ${input.pose.left_elbow.x},    ${input.pose.left_elbow.y}    ]
      - [ ${input.pose.left_wrist.x},    ${input.pose.left_wrist.y}    ]
    fill: cyan
    line_width: 3
    joint: curve
    output: ${output}
```

### Text Watermark

Add a caption or watermark:

```yaml
component:
  type: image-drawing
  action:
    method: text
    image: ${input.photo}
    x: 20
    y: 20
    text: "© Studio Example"
    fill: "#ffffffcc"
    font:
      path: /usr/share/fonts/DejaVuSans.ttf
      size: 28
    stroke_width: 2
    stroke_fill: "#00000066"
    output: ${watermarked}
```

### Label Pill Background

Render a rounded-rectangle label background under text:

```yaml
component:
  type: image-drawing
  actions:
    - id: label-background
      method: rectangle
      image: ${input.image}
      x: 20
      y: 20
      width: 160
      height: 32
      radius: 16
      fill: "#000000cc"
      output: ${bg}

    - id: label-text
      method: text
      image: ${bg}
      x: 32
      y: 26
      text: "Person 0.94"
      fill: white
      font:
        path: /usr/share/fonts/DejaVuSans-Bold.ttf
        size: 16
      anchor: lt
      output: ${output}
```

Chain both actions in a workflow so the text is drawn on top of the pill background.

## Variable Interpolation

All numeric and color fields accept variable references and cast expressions:

```yaml
component:
  type: image-drawing
  action:
    method: rectangle
    image: ${input.image}
    x: ${input.box.x as integer}
    y: ${input.box.y as integer}
    width: ${input.box.width as integer}
    height: ${input.box.height as integer}
    radius: ${input.box.radius as integer | 0}
    outline: ${input.box.color | "#00ff00"}
    line_width: ${input.line_width as integer | 2}
```

`points` can be provided either as a literal list or as a reference to a variable resolving to a list of `[x, y]` pairs:

```yaml
component:
  type: image-drawing
  action:
    method: polygon
    image: ${input.image}
    points: ${jobs.segment.output.contour}  # e.g. [[10,10],[100,30],[80,100]]
    fill: "#00ff0040"
    outline: "#00ff00"
```

## Coordinate System and Colors

- **Origin**: `(0, 0)` at the top-left corner of the image. `x` increases to the right; `y` increases downward.
- **Angles**: measured in degrees, clockwise from the 3 o'clock position (Pillow's convention).
- **Colors**: accept CSS-style names (`"red"`), hex strings (`"#ff0000"`, `"#ff000080"` for RGBA), RGB tuples `[r, g, b]`, or RGBA tuples `[r, g, b, a]` with each channel in `0–255`.
- **Coordinates that fall outside the image** are clipped naturally by Pillow — no error is raised.

## Best Practices

1. **Draw backgrounds before text**: For label pills, filled `rectangle` → `text` in that order so the text is legible.
2. **Use `stroke_width` for text on busy backgrounds**: A 1–2 pixel dark stroke around white text stays readable over any photo.
3. **Match line thickness to image resolution**: `line_width: 2` on a 4K image is nearly invisible; scale thickness with image size or use variables.
4. **Prefer `rectangle` with `radius` over separate rounded shapes**: Rounded rectangles are a single method call and stay crisp at any radius.
5. **Chain via workflow, not a mega-action**: Each drawing action produces a new image; feed it as the next action's `image` to layer effects predictably.
6. **Feed detection outputs directly**: `x`, `y`, `width`, `height` mirror common `bounding_box` shapes, so detection component outputs can be piped in without reshaping.
7. **Use variable defaults for optional visual style**: Expose `color`, `line_width`, `radius` via input variables so the same workflow can produce different visual themes.

## Common Use Cases

- **Object / face detection overlays**: Draw bounding boxes and class labels on frames.
- **Keypoint / landmark annotation**: Mark facial landmarks, hand joints, or pose keypoints with circles.
- **Segmentation mask outlines**: Trace polygonal regions returned by segmentation models.
- **Pose skeletons**: Connect keypoints with lines to visualize skeletons.
- **Watermarks and captions**: Overlay text on rendered outputs.
- **Region highlights**: Highlight regions of interest with translucent filled shapes.
- **Chart annotations**: Add arcs, pie slices, or custom polygons on top of chart images.

> For image transformations (resize, crop, filters, mosaic, overlay), see the [`image-processor`](image-processor.md) component. For measuring image properties, see [`image-analyzer`](image-analyzer.md). For PNG compression, see [`image-compressor`](image-compressor.md).
