# 音乐乐谱渲染器示例

此示例演示如何使用 model-compose 的 `music-score-renderer` 组件将 MusicXML 乐谱（`.xml`/`.musicxml`/`.mxl`）按页光栅化为图像。输出为逐页的列表 — SVG 字符串、单页 PDF 或指定 DPI 的 PNG，底层均由 [Verovio](https://www.verovio.org/) 完成渲染。

当您拥有一份 MusicXML 乐谱（手写、从记谱软件导出，或由上游步骤如 [`music-score-loader`](../music-score-loader/) 产生），并希望获得可视化渲染结果 — 用于审阅界面、PDF 交付物或缩略图流水线 — 而不想自行接入 Verovio 时，使用此示例。

## 概述

此示例提供 3 个工作流：

1. **将乐谱渲染为 SVG**（默认）—— 每页一个 SVG。无损缩放，最适合 Web 查看器。
2. **将乐谱渲染为 PDF** —— 每页一个单页 PDF，采用近似 A4 的 Verovio 尺寸。若需单一文档请在外部合并。
3. **将乐谱渲染为 PNG** —— 每页一个指定 DPI 的 PNG。适用于缩略图或无法显示 SVG 的客户端。

## 准备工作

### 前置条件

- 已安装 model-compose 并在您的 PATH 中可用
- Python 依赖会在首次运行时自动安装：
  - `verovio` —— 渲染引擎（始终安装）
  - `svglib`、`reportlab` —— 仅在声明了 `pdf` 动作时安装
  - `resvg-py` —— 仅在声明了 `png` 动作时安装

### 设置

导航到此示例目录：
```bash
cd examples/media-processing/music-score-renderer
```

## 运行方式

1. **启动服务：**
   ```bash
   model-compose up
   ```

   服务启动后：
   - API 端点：http://localhost:8080/api
   - Web UI：http://localhost:8081

2. **运行工作流：**

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 从下拉菜单中选择工作流
   - 上传 MusicXML 文件（`.xml`、`.musicxml` 或压缩的 `.mxl`）
   - 点击 "Run Workflow"

   **使用 CLI：**
   ```bash
   # 将每页渲染为 SVG（默认）
   model-compose run render-score-svg --input '{"score": "/path/to/score.musicxml"}'

   # 将每页渲染为单页 PDF
   model-compose run render-score-pdf --input '{"score": "/path/to/score.musicxml"}'

   # 以 300 DPI 将每页渲染为 PNG
   model-compose run render-score-png --input '{"score": "/path/to/score.musicxml"}'
   ```

   **使用 API：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=render-score-svg" \
     -F "score=@/path/to/score.musicxml"
   ```

## 组件详情

### Music Score Renderer 组件

- **类型**：`music-score-renderer`
- **用途**：使用 Verovio 的雕版排版将 MusicXML 乐谱转换为逐页图像序列（SVG、PDF 或 PNG）。
- **驱动**：
  - `verovio` —— 基于 Verovio 的渲染（默认）

页面尺寸以 **Verovio 单位**表示，其中 1 单位 ≈ 0.1 mm。默认值（`page_width: 2100`、`page_height: 2970`）对应该单位下的 A4 尺寸。`scale` 为百分比（100 = Verovio 默认大小），`margin` 既可以是单个标量（四边统一），也可以是显式指定 `top`/`right`/`bottom`/`left` 的对象。

若要从 MIDI 文件或已有乐谱生成 MusicXML 输入本身，可将 [`music-score-loader`](../music-score-loader/) 置于上游 —— 但请注意加载器输出的是结构化的 `MusicScore` 数据，若需从 MIDI 源进行渲染，中间还需额外加入 MusicXML 序列化步骤。

## 工作流详情

### 1. 将乐谱渲染为 SVG

**ID**：`render-score-svg`

每页生成一个 SVG。SVG 无损缩放，且是 Verovio 的原生输出 —— 另外两种格式都是由它派生而来。

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `score` | file | 是 | - | 要渲染的 MusicXML 文件（`.xml`、`.musicxml` 或 `.mxl`） |

#### 输出

按页序排列的 SVG 文件列表（`page-1.svg`、`page-2.svg`、…），内容类型为 `image/svg+xml`。

---

### 2. 将乐谱渲染为 PDF

**ID**：`render-score-pdf`

每页生成一个单页 PDF。YAML 中设置了近似 A4 的页面尺寸（`page_width: 2100`、`page_height: 2970`）以及四边统一的 60 单位边距。

PDF 生成经由 `svglib` + `reportlab`：Verovio 的每个 SVG 页面被转换为 ReportLab 绘图，再以独立 PDF 输出。若需单一多页 PDF，请在外部用 `pdfunite` 或 `pypdf` 等工具合并。

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `score` | file | 是 | - | 要渲染的 MusicXML 文件 |

#### 输出

按页序排列的 PDF 文件列表（`page-1.pdf`、`page-2.pdf`、…），内容类型为 `application/pdf`。

---

### 3. 将乐谱渲染为 PNG

**ID**：`render-score-png`

通过 `resvg-py` 按配置的 DPI 对 Verovio 的每个 SVG 页面进行光栅化，每页生成一个 PNG。适用于缩略图、预览，或任何无法渲染 SVG 的环境。

示例设置 `dpi: 300` 以获得印刷质量的光栅化，并使用非对称边距（`top: 80`、`right: 60`、`bottom: 80`、`left: 60`）来展示按边对象形式。

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `score` | file | 是 | - | 要渲染的 MusicXML 文件 |

#### 输出

按页序排列的 PNG 图像列表（`page-1.png`、`page-2.png`、…）。

---

### 动作选项参考

三个动作共享相同的选项集合，仅 `format` 和若干按格式区分的默认值不同。

| 选项 | 类型 | 默认值 | 适用范围 | 说明 |
|--------|------|---------|------------|-------------|
| `source` | file / file 列表 | 必填 | 全部 | MusicXML 输入；路径、上传流或原始字节 |
| `format` | `svg` \| `pdf` \| `png` | `svg` | 全部 | 每页的输出格式 |
| `page_width` | 数字 | `2100` | 全部 | 页面宽度（Verovio 单位，1 单位 ≈ 0.1 mm） |
| `page_height` | 数字 | `2970` | 全部 | 页面高度（Verovio 单位） |
| `scale` | 数字 | `100` | 全部 | 渲染缩放百分比；100 为 Verovio 默认大小 |
| `margin` | 数字或 `{top,right,bottom,left}` | `50` | 全部 | 标量应用于四边，对象可逐边指定 |
| `dpi` | 数字 | `150` | 仅 `png` | 光栅化分辨率。在 `svg` 和 `pdf` 下被忽略 |
