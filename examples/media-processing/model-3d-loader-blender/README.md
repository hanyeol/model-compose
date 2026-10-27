# Model 3D Loader (Blender) Example

This example opens a `.blend` scene (or `.fbx`/`.obj`/`.glb`/`.ply`/`.stl`) in a headless Blender session, optionally selects one object or collection, applies modifiers, and exports the result as GLB — ready to feed into mesh-consuming AI pipelines.

## Overview

The Blender driver extends `model-3d-loader` beyond trimesh's reach:

1. **`.blend` native support**: Open Blender scenes directly. Trimesh cannot parse these.
2. **Object selection**: Pick a single named object or collection from a larger scene. Trimesh exports whatever the file contains, with no selection granularity.
3. **Modifiers**: Apply Subdivision Surface, Mirror, Array, Solidify, and other modifiers before export. The output mesh is the fully evaluated geometry.
4. **Materials and animation**: Preserve PBR materials and (optionally) armature + animation data in GLB/FBX output.

This component is for cases where the AI pipeline needs to consume a specific asset from a human-authored scene — e.g. a game studio hands you a `.blend` with 50 characters, and you want to run Hi3D refinement on just the hero.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH.
- **Blender installed on the host machine**. Download from https://blender.org (free, GPL). Tested with Blender 4.0+.
  - macOS: install the `.dmg`; the driver auto-discovers `/Applications/Blender.app/Contents/MacOS/Blender`.
  - Linux: install via package manager or the official tarball; the driver checks `blender` on PATH plus `/usr/bin/blender` and `/usr/local/bin/blender`.
  - Windows: install the `.msi` or portable zip; set `binary` to the executable path if it is not on PATH.
- No GPU required (headless mode uses CPU for export).

### Install Discovery

The driver tries, in order:

1. `component.binary` if explicitly set.
2. `shutil.which("blender")` (PATH).
3. Platform-specific standard install paths (`/Applications/Blender.app/...`, `C:\Program Files\Blender Foundation\...`, `/usr/bin/blender`, `/usr/local/bin/blender`).

If none match, startup fails with a clear error pointing to the install page.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```
   > First invocation spawns a Blender subprocess (~1-3 seconds boot). Subsequent calls each spawn their own subprocess; peak RAM is bounded per call.

2. **Run the workflow:**

   **Using API:**
   ```bash
   # Minimal — load a .blend scene, export the entire scene as GLB
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "file=@/path/to/scene.blend" \
     -F 'input={"file": "@file"}' \
     -o scene.glb

   # Export only the "Hero" object with modifiers applied
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "file=@/path/to/scene.blend" \
     -F 'input={"file": "@file", "object_name": "Hero"}' \
     -o hero.glb

   # Export a collection, preserve animation, output as FBX
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "file=@/path/to/scene.blend" \
     -F 'input={"file": "@file", "object_name": "Characters", "format": "fbx", "include_animations": true}' \
     -o characters.fbx

   # Convert an .fbx to a clean GLB with modifiers applied
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "file=@/path/to/model.fbx" \
     -F 'input={"file": "@file"}' \
     -o output.glb
   ```

   **Using Web UI:**
   - Open http://localhost:8081
   - Upload a `.blend` (or `.fbx`/`.obj`/`.glb`/`.ply`/`.stl`)
   - Optionally set `object_name`, `format`, `include_animations`
   - Click "Run Workflow"

## Configuration Reference

### Component Fields

| Field     | Description                                                                                 | Default   |
|-----------|---------------------------------------------------------------------------------------------|-----------|
| `type`    | Must be `model-3d-loader`.                                                                  | —         |
| `driver`  | Must be `blender`.                                                                          | —         |
| `binary`  | Path to the blender executable. Auto-discovered when omitted.                               | (auto)    |
| `timeout` | Timeout in seconds for each blender subprocess.                                             | `120.0`   |

### Action Fields

| Field                | Description                                                                                               | Default |
|----------------------|-----------------------------------------------------------------------------------------------------------|---------|
| `source`             | 3D model source (`.blend`, `.fbx`, `.obj`, `.glb`, `.ply`, `.stl`). Path, URL, upload, or raw bytes.      | —       |
| `format`             | Output format: `glb`, `gltf`, `obj`, `ply`, `fbx`, `stl`.                                                 | `glb`   |
| `object_name`        | Specific object or collection in the scene to export. Whole scene when omitted.                          | (whole) |
| `apply_modifiers`    | Apply modifiers (Subdivision, Mirror, Array, ...) before export.                                          | `true`  |
| `include_materials`  | Include materials and textures in the exported mesh.                                                      | `true`  |
| `include_animations` | Include armature and animation data (GLB/FBX only).                                                       | `false` |
| `batch_size`         | Number of sources processed per batch when the input is a list. Blender runs sequentially regardless.    | `1`     |

## Notes

- **Blender boot time dominates small jobs**: Each invocation launches a fresh Blender process (~1-3s). Batching sources into a single component call does not amortize this cost — Blender is launched once per source. For high-throughput use, batch at the workflow level and reuse the controller.
- **Object or collection, not both**: `object_name` matches `bpy.data.objects[name]` first, then falls back to `bpy.data.collections[name]`. If both exist with the same name, the object wins. Rename one to avoid ambiguity.
- **Modifier evaluation**: `apply_modifiers: true` runs the full modifier stack in Blender before export. The output mesh may be heavier than the authored geometry (subdivision increases polygon count significantly).
- **FBX round-tripping**: Blender's FBX importer and exporter are both lossy. Transform baking and unit conversion can shift pivots, scales, and rotations between round-trips. Use GLB when exchanging with other DCC tools.
- **Animation export requires GLB or FBX**: `include_animations: true` is ignored for OBJ/PLY/STL (static formats).
- **Timeout tuning**: Default 120s covers small scenes. Large production scenes with heavy subdivision modifiers may exceed this — raise `component.timeout` as needed.
- **Pipeline example**: `model-3d-loader` (Blender) → `image-to-3d-hi3d` (refinement with reference image) → `model-3d-renderer` (preview) is a natural flow for AI-assisted asset polish.
