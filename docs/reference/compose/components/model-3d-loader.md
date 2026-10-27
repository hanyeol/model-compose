# 3D Model Loader Component

The 3D model loader component ingests 3D asset files (`.glb`, `.gltf`, `.obj`, `.ply`, `.stl`, `.fbx`, `.blend`) into a pipeline as a `Model3DStreamResource`. The `native` driver uses trimesh for exchange formats; the `blender` driver drives a headless Blender process so `.blend` scenes, modifiers, object selection, and animation data become accessible. Both re-export to a format the rest of the pipeline consumes (default `glb`).

Think of it as the 3D counterpart to `document-loader`, `subtitle-loader`, and `music-score-loader`: a pipeline entry point that normalizes arbitrary source inputs into a canonical streaming resource.

## Basic Configuration

```yaml
component:
  type: model-3d-loader
  # driver defaults to `native` (trimesh).
  action:
    source: ${input.file as file}
    format: glb
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `model-3d-loader` |
| `driver` | string | `native` | Backend implementation. One of `native` (trimesh) or `blender` (headless Blender). |
| `actions` | array | `[]` | List of load actions |

### Blender-driver Component Settings

Only used when `driver: blender`:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `binary` | string | `null` | Path to the blender executable. Auto-discovered from `PATH` or platform-standard install locations when omitted. |
| `timeout` | number \| string | `120.0` | Timeout in seconds for each blender subprocess. |

### Action Configuration (common)

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `source` | file \| file[] \| string \| string[] | **required** | 3D model source(s) — path, URL, upload stream, raw bytes, or interpolated variable (e.g. `${input.file as file}`). Lists are batched. |
| `format` | string \| string[] | `glb` | Output format emitted into the pipeline. One of `glb`, `gltf`, `obj`, `ply`, `fbx`, `stl`. |
| `batch_size` | integer \| string | `null` | Number of sources processed per batch. When unset, defaults to `1`. |

### Blender-driver Action Fields

Available only on the `blender` driver:

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `object_name` | string | `null` | Specific object or collection to export. The whole scene is exported when omitted. Matches `bpy.data.objects[name]` first, then falls back to `bpy.data.collections[name]`. |
| `apply_modifiers` | boolean \| string | `true` | Apply modifiers (Subdivision, Mirror, Array, Solidify, ...) before export. The output mesh is the fully evaluated geometry. |
| `include_materials` | boolean \| string | `true` | Include materials and textures in the exported mesh. |
| `include_animations` | boolean \| string | `false` | Include armature and animation data. GLB/FBX only — ignored for OBJ/PLY/STL (static formats). |

## Supported Drivers

### Native (trimesh)

Uses the [trimesh](https://trimsh.org/) Python library to parse and re-export meshes in-process. No external binary. Format coverage follows trimesh: GLB/GLTF/OBJ/PLY/STL/DAE/3MF/OFF and a few others.

```yaml
component:
  type: model-3d-loader
  driver: native
  action:
    source: ${input.file as file}
    format: glb
```

**Requires:** `pip install trimesh`.

**Caveats:**

- `.fbx` export via trimesh is limited to geometry — materials and armatures do not round-trip. Use the `blender` driver when FBX fidelity matters.
- No animation support — trimesh is geometry-focused. Use `blender` with `include_animations: true` when animation data must survive.
- trimesh raises `ValueError` if it cannot export the requested format for the loaded mesh type (e.g. STL from a scene with multiple geometries). The driver surfaces this as a clear error.

### Blender (headless)

Drives Blender in `--background --python` mode. Opens `.blend` scenes directly, runs the full modifier stack, selects a named object or collection, and exports via Blender's native exporters.

```yaml
component:
  type: model-3d-loader
  driver: blender
  # Auto-discovered from PATH or standard install locations when omitted.
  # binary: /Applications/Blender.app/Contents/MacOS/Blender
  timeout: 180.0
  action:
    source: ${input.file as file}
    object_name: ${input.object_name as string}
    format: glb
    apply_modifiers: true
    include_materials: true
    include_animations: false
```

**Requires:** [Blender](https://blender.org) installed on the host. Tested with Blender 4.0+.

**Binary discovery:**

1. `component.binary` if explicitly set.
2. `shutil.which("blender")` (`PATH`).
3. Platform-specific standard install paths:
   - macOS: `/Applications/Blender.app/Contents/MacOS/Blender`
   - Windows: `C:\Program Files\Blender Foundation\Blender\blender.exe`
   - Linux: `/usr/bin/blender`, `/usr/local/bin/blender`

Startup fails with a clear error pointing to the install page when none match.

**Caveats:**

- Blender boot time dominates small jobs (~1-3s per invocation). Batching sources into one component call does not amortize this cost — Blender is launched once per source. For high throughput, batch at the workflow level and reuse the controller.
- Blender's FBX importer and exporter are both lossy. Transform baking and unit conversion can shift pivots, scales, and rotations between round-trips. Use GLB when exchanging with other DCC tools.
- `apply_modifiers: true` evaluates the full modifier stack before export. Output polygon count can grow significantly (e.g. Subdivision).

## Supported Formats

### Input

| Format | Extension | Native (trimesh) | Blender |
|--------|-----------|------------------|---------|
| glTF (binary) | `.glb` | ✓ | ✓ |
| glTF (JSON) | `.gltf` | ✓ | ✓ |
| Wavefront OBJ | `.obj` | ✓ | ✓ |
| Polygon File Format | `.ply` | ✓ | ✓ |
| Stereolithography | `.stl` | ✓ | ✓ |
| Autodesk FBX | `.fbx` | partial (geometry only) | ✓ |
| Blender scene | `.blend` | — | ✓ |

### Output

Both drivers emit one of: `glb`, `gltf`, `obj`, `ply`, `fbx`, `stl`. The default `glb` is self-contained with embedded textures — the smoothest fit for downstream consumers that expect a single file.

## Output Format

The action returns a `Model3DStreamResource` for a single source, or a list of them when `source` is a list. Downstream jobs consume it as a `model-3d` value — streamed binary, spooled file path, or the gradio Model3D viewer:

```yaml
output:
  model_3d: ${output as model-3d}          # streamed binary
  model_3d: ${output as model-3d;path}     # spooled file path
```

## Integration with Workflows

### Single-file Load (Native)

```yaml
workflows:
  - id: load
    job:
      component: loader
      input:
        source: ${input.file as file}
        format: ${input.format as select/glb,gltf,obj,ply,fbx,stl | glb}
      output:
        model_3d: ${output as model-3d}

components:
  - id: loader
    type: model-3d-loader
    action:
      source: ${input.source}
      format: ${input.format}
```

### Blender Scene with Object Selection

Pick a specific hero mesh out of a 50-character `.blend` and export it as GLB:

```yaml
components:
  - id: loader
    type: model-3d-loader
    driver: blender
    action:
      source: ${input.file as file}
      object_name: ${input.object_name as string}
      format: glb
      apply_modifiers: true
      include_materials: true
```

### Pipe into AI Refinement

Normalize an arbitrary input into GLB, then feed it into a mesh-consuming model for refinement:

```yaml
workflows:
  - id: load-and-refine
    jobs:
      - id: load
        component: loader
        input:
          source: ${input.file as file}
        output:
          model_3d: ${output as model-3d}

      - id: refine
        component: hi3d
        input:
          model_3d: ${jobs.load.output.model_3d}
          image: ${input.reference_image}
        depends_on: [load]
        output:
          model_3d: ${output as model-3d}

components:
  - id: loader
    type: model-3d-loader
  - id: hi3d
    type: model
    task: image-to-3d
    family: hi3d
```

### Batch Load

Load several assets in one action by passing a list:

```yaml
components:
  - id: loader
    type: model-3d-loader
    action:
      source: ${input.files as file[]}
      format: glb
      batch_size: 4
```

Note: with the `blender` driver, `batch_size` controls bookkeeping only — Blender still runs one subprocess per source.

## Best Practices

1. **Pick the driver by input format**: Use `native` for exchange formats (GLB/OBJ/PLY/STL/GLTF). Switch to `blender` when the input is `.blend`, when you need to apply modifiers before export, when you want to select a specific object or collection, or when animation data must survive.
2. **Prefer GLB as the pipeline-internal format**: Self-contained binary with embedded textures — the smoothest handoff for downstream consumers, MCP tool outputs, and 3D viewers.
3. **Pass `${input.file as file}`, not raw bytes**: The loader uses the stream's `filename` to recover the input extension when spooling uploads. Passing raw bytes loses the extension, which breaks Blender's extension-based import dispatch.
4. **Raise `timeout` for heavy scenes (Blender)**: The default 120s covers small scenes. Production scenes with heavy Subdivision modifiers can exceed this — bump `component.timeout` as needed.
5. **Chain with converter/renderer for user-upload previews**: `model-3d-loader` → `model-3d-converter` (format normalization) → `model-3d-renderer` (image preview) is a common flow when previewing user-uploaded 3D assets.
