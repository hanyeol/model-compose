# Model 3D Loader (Native) 示例

此示例使用 trimesh 将 3D 模型文件（GLB、OBJ、PLY、STL、GLTF、DAE、3MF、OFF 等）加载为管道中的 `Model3DStreamResource`。

## 概述

`model-3d-loader` 是 3D 资产的管道入口 —— 与 PDF 的 `document-loader`、字幕的 `subtitle-loader`、MIDI/MusicXML 的 `music-score-loader` 属于同一类组件。其 `native` 驱动使用 trimesh，因此任何 trimesh 可解析的格式都可作为有效输入，加载器会按您请求的格式（默认 GLB）重新导出。

使用此组件可以：

1. **供给 AI 管道**：在传递给需要网格输入的模型（例如用于精修的 `image-to-3d-hi3d`）之前，将任意输入格式转换为标准 GLB。
2. **归一化输入格式**：接受用户上传的任何格式（`.obj`、`.fbx`、`.ply`），并向下游输出一个一致的格式。
3. **与数据集组合**：将 `source` 指向资产路径列表，即可批量返回网格列表。

## 准备工作

### 前置条件

- 已安装 model-compose 并在 PATH 中可用。
- Python 环境可安装 `trimesh`（首次运行会自动安装）。
- 不需要 GPU。

### Native 与 Blender 的选择

- **Native（本示例）**：trimesh 可以干净地处理常见交换格式。无需外部软件。格式支持范围由 trimesh 决定（GLB/GLTF/OBJ/PLY/STL/DAE/3MF/OFF 及少数其他格式）。
- **Blender**（参见 `../model-3d-loader-blender/`）：可打开 `.blend` 场景并在导出前运行修改器。当输入是 Blender 项目文件，或需要从较大场景中选择特定对象/集合时需要使用。

## 运行方式

1. **启动服务：**
   ```bash
   model-compose up
   ```

2. **运行工作流：**

   **使用 API：**
   ```bash
   # 最小 —— 将 .obj 加载为 GLB
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "file=@/path/to/model.obj" \
     -F 'input={"file": "@file"}' \
     -o output.glb

   # 显式指定输出格式
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "file=@/path/to/model.glb" \
     -F 'input={"file": "@file", "format": "ply"}' \
     -o output.ply
   ```

   **使用 Web UI：**
   - 打开 http://localhost:8081
   - 上传 3D 模型文件
   - 选择输出格式（默认 `glb`）
   - 点击 "Run Workflow"

## 配置参考

### 组件字段

| 字段     | 描述                                                                 | 默认值   |
|----------|----------------------------------------------------------------------|----------|
| `type`   | 必须是 `model-3d-loader`。                                           | —        |
| `driver` | 必须是 `native`（或省略 —— `native` 是默认驱动）。                   | `native` |

### Action 字段

| 字段         | 描述                                                                                             | 默认值  |
|--------------|--------------------------------------------------------------------------------------------------|---------|
| `source`     | 3D 模型源（路径、URL、上传流或原始字节）。列表会被批处理。                                       | —       |
| `format`     | 输出格式：`glb`、`gltf`、`obj`、`ply`、`fbx`、`stl`。                                            | `glb`   |
| `batch_size` | 当输入为列表时每批处理的源数量。                                                                 | `1`     |

## 注意事项

- **默认 GLB**：生成嵌入纹理的单个二进制文件。对期望单一文件的下游消费者是最简单的格式。
- **trimesh 的 `.fbx` 导出有限**：FBX 是专有格式，trimesh 的编写器仅覆盖几何体。对于带有骨架或复杂材质的场景，请使用 Blender 驱动。
- **不支持动画**：trimesh 以几何体为中心。输入中的动画数据（关键帧、骨架）会被丢弃。若必须保留动画数据，请使用 Blender 驱动并设置 `include_animations: true`。
- **不支持的导出格式会报错**：若 trimesh 无法将加载的网格类型导出为请求的格式（例如从包含多个几何体的场景导出 STL），会抛出 `ValueError`。驱动会以清晰的错误信息呈现出来。
- **链式示例**：`model-3d-loader` → `model-3d-converter`（格式转换）→ `model-3d-renderer`（图像预览）是预览用户上传 3D 资产的常见管道。
