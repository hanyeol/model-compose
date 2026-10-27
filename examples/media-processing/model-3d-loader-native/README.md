# Model 3D Loader (Native) Example

This example loads 3D model files (GLB, OBJ, PLY, STL, GLTF, DAE, 3MF, OFF, ...) into the pipeline as a `Model3DStreamResource`, using trimesh for parsing and re-export.

## Overview

`model-3d-loader` is the pipeline entry point for 3D assets — the counterpart to `document-loader` for PDFs, `subtitle-loader` for subtitle tracks, and `music-score-loader` for MIDI/MusicXML. Its `native` driver uses trimesh, so any format trimesh can parse becomes a valid input, and the loader re-exports it in the format you request (defaulting to GLB).

Use this component to:

1. **Feed AI pipelines**: Produce a canonical GLB from an arbitrary input format before passing it to a mesh-consuming model (e.g. `image-to-3d-hi3d` for refinement).
2. **Normalize input formats**: Accept whatever the user uploads (`.obj`, `.fbx`, `.ply`) and emit a single consistent format downstream.
3. **Compose with datasets**: Point `source` at a list of asset paths and get a batched list of meshes back.

## Preparation

### Prerequisites

- model-compose installed and available in your PATH.
- Python environment where `trimesh` can be installed (first run installs it automatically).
- No GPU required.

### Why Native vs Blender

- **Native (this example)**: trimesh handles common exchange formats cleanly. No external software. Format support is bounded by trimesh (GLB/GLTF/OBJ/PLY/STL/DAE/3MF/OFF and a few others).
- **Blender** (see `../model-3d-loader-blender/`): Opens `.blend` scenes and runs modifiers before export. Required when the input is a Blender project file or when you need to select a specific object/collection from a larger scene.

## How to Run

1. **Start the service:**
   ```bash
   model-compose up
   ```

2. **Run the workflow:**

   **Using API:**
   ```bash
   # Minimal — load a .obj as GLB
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "file=@/path/to/model.obj" \
     -F 'input={"file": "@file"}' \
     -o output.glb

   # Explicit output format
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "file=@/path/to/model.glb" \
     -F 'input={"file": "@file", "format": "ply"}' \
     -o output.ply
   ```

   **Using Web UI:**
   - Open http://localhost:8081
   - Upload a 3D model file
   - Pick an output format (defaults to `glb`)
   - Click "Run Workflow"

## Configuration Reference

### Component Fields

| Field    | Description                                                          | Default  |
|----------|----------------------------------------------------------------------|----------|
| `type`   | Must be `model-3d-loader`.                                           | —        |
| `driver` | Must be `native` (or omitted — `native` is the default driver).      | `native` |

### Action Fields

| Field        | Description                                                                                      | Default |
|--------------|--------------------------------------------------------------------------------------------------|---------|
| `source`     | 3D model source (path, URL, upload stream, or raw bytes). Lists are batched.                     | —       |
| `format`     | Output format: `glb`, `gltf`, `obj`, `ply`, `fbx`, `stl`.                                        | `glb`   |
| `batch_size` | Number of sources processed per batch when the input is a list.                                  | `1`     |

## Notes

- **GLB default**: Produces a single binary with embedded textures. The easiest format for downstream consumers that expect a single file.
- **`.fbx` export via trimesh is limited**: FBX is a proprietary format and trimesh's writer covers only geometry. For scenes with armature or complex materials, use the Blender driver.
- **No animation support**: trimesh is geometry-focused. Animation data in the input (keyframes, armatures) is dropped. Use the Blender driver with `include_animations: true` when animation data must survive.
- **Error on unsupported export format**: trimesh raises `ValueError` if it cannot export the requested format for the loaded mesh type (e.g. STL from a scene with multiple geometries). The driver surfaces this with a clear error.
- **Chaining example**: `model-3d-loader` → `model-3d-converter` (format change) → `model-3d-renderer` (image preview) is a common pipeline when previewing user-uploaded 3D assets.
