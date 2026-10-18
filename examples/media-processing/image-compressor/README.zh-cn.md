# Image Compressor 示例

此示例演示了使用 `image-compressor` 组件进行 PNG 压缩，展示其附带的全部三种驱动程序：Pillow（`native`）、`oxipng` 和 `pngquant`。每种驱动程序在大小、速度和依赖项占用之间做出不同的权衡。

## 概述

三个工作流分别封装三种驱动程序：

1. **Compress PNG (Pillow)** — 纯 Pillow DEFLATE 编码。无需额外依赖。
2. **Lossless Shrink (oxipng)** — 在 Pillow 编码的 PNG 之上运行 oxipng，额外实现 10–30% 的无损大小减少。
3. **Lossy Palette Quantization (pngquant)** — 将图像缩减为 ≤256 色自适应调色板，对于照片或梯度密集的图像，在视觉上接近的品质下通常比无损小 50–70%。

所有工作流均以 base64 图像形式返回压缩后的 PNG。

## 准备工作

### 前置条件

- 已安装 model-compose 并在您的 PATH 中可用
- `oxipng` 工作流需要 `pyoxipng` Python 包
- `pngquant` 工作流需要 `pngquant` 二进制文件在 `PATH` 中：
  - macOS: `brew install pngquant`
  - Debian/Ubuntu: `apt install pngquant`

### 环境配置

1. 导航到此示例目录：
   ```bash
   cd examples/media-processing/image-compressor
   ```

2. 无需额外的环境配置 - 所有处理均在本地完成。

## 运行方式

1. **启动服务：**
   ```bash
   model-compose up
   ```

2. **运行工作流：**

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 选择工作流（Compress PNG、Lossless Shrink、Lossy Palette Quantization）
   - 上传图像并调整驱动程序特定参数
   - 点击"运行工作流"按钮
   - 查看并下载压缩后的 PNG

   **使用 API：**
   ```bash
   # Pillow — 最大 DEFLATE 级别
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow_id=compress-native" \
     -F "image=@input.png" \
     -F "compress_level=9"

   # oxipng — 额外无损压缩
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow_id=compress-oxipng" \
     -F "image=@input.png" \
     -F "level=4"

   # pngquant — 有损调色板量化
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow_id=compress-pngquant" \
     -F "image=@input.png" \
     -F "min_quality=65" \
     -F "max_quality=85"
   ```

   **使用 CLI：**
   ```bash
   model-compose run compress-native   --input '{"image": "input.png", "compress_level": 9}'
   model-compose run compress-oxipng   --input '{"image": "input.png", "level": 4}'
   model-compose run compress-pngquant --input '{"image": "input.png", "min_quality": 65, "max_quality": 85}'
   ```

## 组件详情

### Image Compressor 组件
- **类型**：`image-compressor`
- **驱动程序**：`native`（Pillow）、`oxipng`、`pngquant`
- **输出**：压缩后的 PNG 字节（以 base64 图像返回给工作流）

单个 `image-compressor` 组件只能绑定到一个驱动程序，因此此示例声明了三个独立的组件实例 — 每种驱动程序一个 — 并将每个工作流路由到匹配的实例。

## 工作流详情

### "Compress PNG (Pillow)" 工作流

**描述**：使用 Pillow 以 `optimize=True` 将输入图像编码为 PNG。

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `image` | image | 是 | - | 要压缩的图像 |
| `compress_level` | integer | 否 | `9` | DEFLATE 压缩级别（0 = 存储，9 = 最大）|
| `strip_metadata` | boolean | 否 | `true` | 是否剥离附属 PNG 元数据块（tEXt、eXIf、iCCP 等）|

### "Lossless Shrink (oxipng)" 工作流

**描述**：使用 oxipng 对 Pillow 编码的 PNG 重新运行 DEFLATE 过滤器搜索。

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `image` | image | 是 | - | 要压缩的图像 |
| `level` | integer | 否 | `4` | Oxipng 优化级别（0 = 快速，6 = 最佳）|
| `strip_metadata` | boolean | 否 | `true` | 是否剥离附属 PNG 元数据块 |

### "Lossy Palette Quantization (pngquant)" 工作流

**描述**：使用 pngquant 构建 ≤256 色自适应调色板。

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `image` | image | 是 | - | 要压缩的图像 |
| `speed` | integer | 否 | `3` | Pngquant 速度，从 1（最慢/最佳）到 11（最快）|
| `min_quality` | integer | 否 | `65` | 最低可接受质量（0–100）；输出低于此值时编码失败 |
| `max_quality` | integer | 否 | `85` | 编码器目标最高质量（0–100）|
| `strip_metadata` | boolean | 否 | `true` | 是否剥离附属 PNG 元数据块 |

### 输出格式

| 字段 | 类型 | 描述 |
|------|------|------|
| `output` | image (base64) | 压缩后的 PNG |

## 驱动程序选择指南

- **native** — 安全的默认选项；无需额外安装，到处可用，提供合理的大小减少。
- **oxipng** — 在每个字节都重要的无损流水线之后链式使用（图标、截图、UI 资源）。
- **pngquant** — 对照片/梯度密集的 PNG 效果最大；为有损压缩，请检查输出质量。

## 故障排除

### 常见问题

1. **找不到 `pyoxipng`** — 在与 model-compose 相同的环境中安装 Python 包（`pip install pyoxipng`）。
2. **找不到 `pngquant`** — 安装 CLI（`brew install pngquant` 或 `apt install pngquant`）并确保它在 `PATH` 中。
3. **pngquant 编码失败** — 输入无法满足 `min_quality`。降低 `min_quality` 或完全省略以接受 pngquant 生成的任何质量。
4. **输出比预期大** — PNG 压缩收益很大程度上取决于输入。对于照片，考虑使用 pngquant；对于已经优化的 PNG，进一步的收益较小。
