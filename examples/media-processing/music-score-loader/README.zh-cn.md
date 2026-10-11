# 音乐乐谱加载器示例

此示例演示如何使用 model-compose 的 `music-score-loader` 组件将符号化音乐文件——MIDI (`.mid`/`.midi`) 和 MusicXML (`.xml`/`.musicxml`/`.mxl`)——解析为统一的 JSON 乐谱结构，其中包含每个音符的时间、音高、力度，以及轨道级别的速度和拍号元数据。

当您以文件形式持有参考旋律或主旋律乐谱，并希望下游组件（音高校正、合成、对齐）将其作为结构化数据而非不透明二进制数据进行消费时，使用此组件。

## 概述

此示例提供 4 个工作流：

1. **加载乐谱文件**（默认）——根据文件头或扩展名自动检测格式，并自动选择第一个确实包含音符的轨道。
2. **加载指定轨道** ——通过显式 `track` 索引进行选择。Type-1 MIDI 文件中轨道 0 常常仅存放速度/元数据时需要，多声部 MusicXML 乐谱同样需要。
3. **强制 MIDI 格式** ——跳过自动检测并将输入解析为 MIDI。适用于文件头被剥离或扩展名非标准的情况。
4. **强制 MusicXML 格式** ——同样跳过自动检测并解析为 MusicXML。既接受未压缩的 XML 变体，也接受压缩的 `.mxl` ZIP 容器。

## 准备工作

### 前置条件

- 已安装 model-compose 并在您的 PATH 中可用
- Python 依赖会在首次运行时自动安装：
  - `mido`（`local` 驱动用于 MIDI 解析）。MusicXML 解析使用 Python 标准库，无需额外安装。

### 设置

导航到此示例目录：
```bash
cd examples/media-processing/music-score-loader
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
   - 上传 MIDI 或 MusicXML 文件
   - 点击 "Run Workflow"

   **使用 CLI：**
   ```bash
   # 自动检测格式与轨道（默认）
   model-compose run load-score --input '{"score": "/path/to/melody.mid"}'

   # 选择特定轨道 —— 当 Type-1 MIDI 的轨道 0 仅为元数据时很有用
   model-compose run load-score-track --input '{
     "score": "/path/to/melody.mid",
     "track": 1
   }'

   # 将扩展名未知的文件视为 MIDI
   model-compose run load-score-as-midi --input '{"score": "/path/to/melody.bin"}'

   # 将压缩的 .mxl 归档显式视为 MusicXML
   model-compose run load-score-as-musicxml --input '{"score": "/path/to/melody.mxl"}'
   ```

   **使用 API：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=load-score" \
     -F "score=@/path/to/melody.mid"
   ```

## 组件详情

### Music Score Loader 组件

- **类型**：`music-score-loader`
- **用途**：将 MIDI/MusicXML 文件解析为统一的乐谱结构（音符 + 速度 + 拍号），使下游组件无需格式特定逻辑即可消费。
- **驱动**：
  - `local` ——基于标准库 + `mido` 的解析（默认）

若要从*音频*（而非符号化乐谱）中进行音高估计，请改用 [`pitch-estimator`](../../model-tasks/pitch-estimation/)。若要在音高校正中将此加载器的输出用作参考旋律，请参见 [`music-pitch-corrector`](../music-pitch-corrector/)。

## 工作流详情

### 1. 加载乐谱文件

**ID**：`load-score`

通过文件的魔术字节自动检测格式（`MThd` → MIDI，`<?xml` → MusicXML，`PK` → 压缩的 `.mxl`），当头部不明确时回退到扩展名。未提供 `track` 时，每个包含 `note_on` 事件的 MIDI 轨道都会被合并（跳过仅含速度映射的轨道），MusicXML 则取第一个 `<part>`。

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `score` | file | 是 | - | 要解析的 MIDI 或 MusicXML 文件 |

#### 示例输出

```json
{
  "notes": [
    { "start_time": 0.0, "end_time": 0.5, "pitch": 60, "velocity": 0.787 },
    { "start_time": 1.0, "end_time": 1.5, "pitch": 64, "velocity": 0.630 }
  ],
  "tempo": 120.0,
  "time_signature": [4, 4],
  "format": "midi",
  "duration": 1.5
}
```

- `pitch` 为 MIDI 编号（中央 C = 60）。
- `velocity` 归一化到 [0, 1]；MusicXML 缺乏通用的动态标记，回退为固定的 mezzo-forte 值。
- `tempo` 只报告速度映射中的第一个值；若需要在曲目中段处理速度变化，请自行重新解析文件。

---

### 2. 加载指定轨道

**ID**：`load-score-track`

通过基于 0 的索引精确选择一条轨道（MIDI）或声部（MusicXML）。越界索引会抛出错误，而不是默默回退。

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `score` | file | 是 | - | 要解析的 MIDI 或 MusicXML 文件 |
| `track` | number | 否 | `0` | 基于 0 的轨道或声部索引 |

常见场景：
- **Type-1 MIDI（多轨）**：轨道 0 通常只含速度/拍号 — 使用 `track=1` 以到达旋律。
- **MusicXML 主旋律乐谱**：通常是单个 `<part>`，`track=0` 正确。
- **多声部 MusicXML 乐谱**：更高索引用于选择其他声部（如低音、和声）。

#### 示例输出

与 *加载乐谱文件* 结构相同，但范围限定在所选轨道。

---

### 3. 强制 MIDI 格式

**ID**：`load-score-as-midi`

跳过格式嗅探，将输入作为 Standard MIDI File 解析。若文件实际并非 MIDI，会立刻报错——相比于误检测后静默出错，当您已明确知道输入契约时，这种显式失败往往更可取。

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `score` | file | 是 | - | 要作为 MIDI 解析的文件 |

---

### 4. 强制 MusicXML 格式

**ID**：`load-score-as-musicxml`

跳过格式嗅探，将输入作为 MusicXML 解析。既接受未压缩的输入（`.xml`/`.musicxml`），也接受压缩的输入（`.mxl` ZIP）——对于 `.mxl`，加载器会读取 `META-INF/container.xml` 中的 rootfile 指针，若该文件缺失，则回退到第一个非元数据 XML 条目。

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `score` | file | 是 | - | 要作为 MusicXML 解析的文件 |

仅支持 `score-partwise` 布局 —— `score-timewise` 会以错误形式被拒绝（实际使用中不到 5% 的文件使用 timewise 布局）。
