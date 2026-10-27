# Model 3D Loader (Blender) 示例

此示例在无头 Blender 会话中打开 `.blend` 场景（或 `.fbx`/`.obj`/`.glb`/`.ply`/`.stl`），可选择一个对象或集合，应用修改器，然后将结果导出为 GLB —— 可以直接供给需要网格输入的 AI 管道。

## 概述

Blender 驱动将 `model-3d-loader` 扩展到了 trimesh 之外：

1. **原生支持 `.blend`**：直接打开 Blender 场景。trimesh 无法解析这些文件。
2. **对象选择**：从较大的场景中挑选一个命名的对象或集合。trimesh 导出文件中包含的所有内容，没有选择粒度。
3. **修改器**：在导出前应用 Subdivision Surface、Mirror、Array、Solidify 等修改器。输出网格是完全求值后的几何体。
4. **材质和动画**：在 GLB/FBX 输出中保留 PBR 材质，并可选择保留骨架 + 动画数据。

此组件适用于 AI 管道需要消费人工创作场景中特定资产的情况 —— 例如：游戏工作室交给你一个包含 50 个角色的 `.blend`，而你只想对主角运行 Hi3D 精修。

## 准备工作

### 前置条件

- 已安装 model-compose 并在 PATH 中可用。
- **在主机上安装 Blender**。从 https://blender.org 下载（免费，GPL）。在 Blender 4.0+ 上测试过。
  - macOS：安装 `.dmg`；驱动会自动探测 `/Applications/Blender.app/Contents/MacOS/Blender`。
  - Linux：通过包管理器或官方 tarball 安装；驱动会检查 PATH 中的 `blender` 及 `/usr/bin/blender`、`/usr/local/bin/blender`。
  - Windows：安装 `.msi` 或便携 zip；若不在 PATH 中，请将 `binary` 设置为可执行文件路径。
- 不需要 GPU（无头模式使用 CPU 导出）。

### 安装路径探测

驱动按以下顺序尝试：

1. 若显式设置了 `component.binary`，则使用该路径。
2. `shutil.which("blender")`（PATH）。
3. 平台特定的标准安装路径（`/Applications/Blender.app/...`、`C:\Program Files\Blender Foundation\...`、`/usr/bin/blender`、`/usr/local/bin/blender`）。

若没有匹配项，启动会失败，并给出指向安装页面的清晰错误信息。

## 运行方式

1. **启动服务：**
   ```bash
   model-compose up
   ```
   > 首次调用会启动一个 Blender 子进程（启动约 1-3 秒）。后续每次调用都启动自己的子进程；每次调用的峰值内存受限。

2. **运行工作流：**

   **使用 API：**
   ```bash
   # 最小 —— 加载 .blend 场景并将整个场景导出为 GLB
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "file=@/path/to/scene.blend" \
     -F 'input={"file": "@file"}' \
     -o scene.glb

   # 只导出 "Hero" 对象，并应用修改器
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "file=@/path/to/scene.blend" \
     -F 'input={"file": "@file", "object_name": "Hero"}' \
     -o hero.glb

   # 导出集合，保留动画，输出为 FBX
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "file=@/path/to/scene.blend" \
     -F 'input={"file": "@file", "object_name": "Characters", "format": "fbx", "include_animations": true}' \
     -o characters.fbx

   # 将 .fbx 转换为应用修改器后的干净 GLB
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "file=@/path/to/model.fbx" \
     -F 'input={"file": "@file"}' \
     -o output.glb
   ```

   **使用 Web UI：**
   - 打开 http://localhost:8081
   - 上传 `.blend`（或 `.fbx`/`.obj`/`.glb`/`.ply`/`.stl`）
   - 可选地设置 `object_name`、`format`、`include_animations`
   - 点击 "Run Workflow"

## 配置参考

### 组件字段

| 字段      | 描述                                                                                   | 默认值    |
|-----------|----------------------------------------------------------------------------------------|-----------|
| `type`    | 必须是 `model-3d-loader`。                                                             | —         |
| `driver`  | 必须是 `blender`。                                                                     | —         |
| `binary`  | blender 可执行文件路径。省略时自动探测。                                               | (auto)    |
| `timeout` | 每个 blender 子进程的超时时间（秒）。                                                  | `120.0`   |

### Action 字段

| 字段                 | 描述                                                                                                      | 默认值  |
|----------------------|-----------------------------------------------------------------------------------------------------------|---------|
| `source`             | 3D 模型源（`.blend`、`.fbx`、`.obj`、`.glb`、`.ply`、`.stl`）。路径、URL、上传或原始字节。                | —       |
| `format`             | 输出格式：`glb`、`gltf`、`obj`、`ply`、`fbx`、`stl`。                                                     | `glb`   |
| `object_name`        | 场景中要导出的特定对象或集合。省略时导出整个场景。                                                        | (整个)  |
| `apply_modifiers`    | 在导出前应用修改器（Subdivision、Mirror、Array 等）。                                                     | `true`  |
| `include_materials`  | 在导出的网格中包含材质和纹理。                                                                            | `true`  |
| `include_animations` | 包含骨架和动画数据（仅 GLB/FBX）。                                                                        | `false` |
| `batch_size`         | 当输入为列表时每批处理的源数量。Blender 无论如何都是串行运行的。                                          | `1`     |

## 注意事项

- **小任务由 Blender 启动时间主导**：每次调用都会启动一个新的 Blender 进程（~1-3 秒）。将多个源打包到单个组件调用中并不会摊销此成本 —— 每个源都要启动一次 Blender。对高吞吐场景，请在工作流层面批处理并复用控制器。
- **对象或集合，二选一**：`object_name` 先匹配 `bpy.data.objects[name]`，然后回退到 `bpy.data.collections[name]`。若两者同名存在，对象优先。为避免歧义，请改名其一。
- **修改器求值**：`apply_modifiers: true` 会在 Blender 中执行完整的修改器栈后再导出。输出网格可能比原始几何体更重（Subdivision 会显著增加多边形数量）。
- **FBX 往返**：Blender 的 FBX 导入器和导出器都是有损的。变换烘焙和单位转换可能在往返之间改变枢轴、缩放和旋转。在与其他 DCC 工具交换时请使用 GLB。
- **动画导出需要 GLB 或 FBX**：`include_animations: true` 对 OBJ/PLY/STL（静态格式）会被忽略。
- **超时调整**：默认 120 秒适用于小场景。带有大量 Subdivision 修改器的大型生产场景可能超时 —— 根据需要调高 `component.timeout`。
- **管道示例**：`model-3d-loader`（Blender）→ `image-to-3d-hi3d`（基于参考图像的精修）→ `model-3d-renderer`（预览）是 AI 辅助资产打磨的自然流程。
