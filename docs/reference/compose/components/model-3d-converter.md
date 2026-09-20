# 3D Model Converter Component

The 3D model converter component transcodes 3D asset files between formats (glTF/GLB, OBJ, STL, PLY, DAE, OFF, 3MF). Conversion is performed by trimesh — a pure-Python library that loads a mesh or scene from the input and re-exports it in the requested target format.

## Basic Configuration

```yaml
component:
  type: model-3d-converter
  driver: native
  action:
    model_3d: ${input.model_3d as model-3d}
    format: glb
```

## Configuration Options

### Component Settings

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `type` | string | **required** | Must be `model-3d-converter` |
| `driver` | string | `native` | Conversion backend driver. Currently only `native` (trimesh-based). |
| `actions` | array | `[]` | List of conversion actions |

### Action Configuration

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `model_3d` | string \| string[] | **required** | 3D model source(s) — file path, URL, or interpolated variable (e.g. `${input.model_3d as model-3d}`) |
| `format` | string \| string[] | `glb` | Output format. One of `glb`, `gltf`, `obj`, `stl`, `ply`, `dae`, `off`, `3mf`. |
| `batch_size` | integer \| string | `null` | Number of input sources per batch. When unset, all sources are processed together. |

## Supported Drivers

### Native (trimesh)

Uses the [trimesh](https://trimsh.org/) Python library to load and re-export meshes. Runs in-process; no external binary is required. glTF export uses `embed_buffers=True` so the resulting `.gltf` is a single self-contained file (buffers embedded as base64) rather than a JSON accompanied by separate `.bin` sidecars.

```yaml
component:
  type: model-3d-converter
  driver: native
  action:
    model_3d: ${input.model_3d as model-3d}
    format: glb
```

**Requires:** `pip install trimesh`.

## Supported Formats

| Format | Extension | Notes |
|--------|-----------|-------|
| glTF (binary) | `.glb` | Self-contained; preserves materials, textures, scene graph. Recommended default. |
| glTF (JSON) | `.gltf` | Single self-contained file (buffers embedded). |
| Wavefront OBJ | `.obj` | Geometry only; no scene graph. |
| Stereolithography | `.stl` | Geometry only; drops materials, UVs, and textures. |
| Polygon File Format | `.ply` | Suits point clouds and vertex-colored meshes. |
| Collada | `.dae` | XML-based scene format. |
| Object File Format | `.off` | Simple geometry format. |
| 3D Manufacturing Format | `.3mf` | Print-oriented format. |

Not every input feature survives every output format. For example, converting a textured GLB to STL drops materials and UVs because STL has no concept of them; convert to GLB/glTF instead to preserve them.

## Output Format

The action returns a single 3D model source (or a list of them when `model_3d` is a list). Downstream jobs consume it as a `model-3d` value — file path, streamed binary, or gradio's Model3D viewer:

```yaml
output:
  model_3d: ${output as model-3d}          # streamed binary
  model_3d: ${output as model-3d;path}     # spooled file path
```

## Integration with Workflows

### Single File Conversion

```yaml
workflows:
  - id: convert
    job:
      component: converter
      input:
        model_3d: ${input.model_3d as model-3d}
        format: ${input.format as select/glb,gltf,obj,stl,ply,dae,off,3mf | glb}
      output:
        model_3d: ${output as model-3d;path}

components:
  - id: converter
    type: model-3d-converter
    action:
      model_3d: ${input.model_3d}
      format: ${input.format}
```

### Batch Conversion

Convert multiple 3D files in one action by passing a list:

```yaml
components:
  - id: converter
    type: model-3d-converter
    action:
      model_3d: ${input.model_3ds as model-3d[]}
      format: glb
      batch_size: 4
```

### Pipe Output of an image-to-3D Model into a Converter

Feed a generated 3D mesh straight into the converter to normalize its format:

```yaml
workflows:
  - id: generate-and-normalize
    jobs:
      - id: generate
        component: image-to-3d
        output:
          model_3d: ${output as model-3d}

      - id: convert
        component: converter
        input:
          model_3d: ${jobs.generate.output.model_3d}
          format: glb
        depends_on: [generate]
        output:
          model_3d: ${output as model-3d}
```

## Best Practices

1. **Prefer GLB as an interchange format**: It carries geometry, materials, textures, and scene graph in a single binary file — the smoothest fit for viewers, MCP tool outputs, and downstream conversion.
2. **Watch for lossy target formats**: STL, OFF, and OBJ drop most non-geometry data. When materials or textures matter, convert to GLB or glTF.
3. **glTF vs. GLB**: Export to `.glb` unless a downstream consumer specifically needs the JSON form. `.gltf` is emitted as a self-contained JSON with embedded buffers, but GLB is smaller and simpler.
4. **Trimesh capability boundaries**: The converter can only export what trimesh's exporter supports for the given input mesh type — for example, exporting a point cloud to `.obj` will fail. Choose a target format compatible with the input's contents.
