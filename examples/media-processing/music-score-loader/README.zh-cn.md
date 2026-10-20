# 音乐乐谱加载器示例

此示例演示如何使用 model-compose 的 `music-score-loader` 组件将符号化音乐文件——MIDI (`.mid`/`.midi`) 和 MusicXML (`.xml`/`.musicxml`/`.mxl`)——解析为模仿 MusicXML `<score-partwise>` 结构的 `MusicScore`：按声部分组的音符（含每个声部的歌词和谱号）以及乐谱级别的速度、拍号/调号和和声。

当您以文件形式持有参考旋律或主旋律乐谱，并希望下游组件（音高校正、合成、对齐）将其作为结构化数据而非不透明二进制数据进行消费时，使用此组件。

## 概述

此示例提供 4 个工作流：

1. **加载乐谱文件**（默认）——根据文件头或扩展名自动检测格式，返回乐谱的所有声部。
2. **加载指定声部** ——通过显式 `part` 索引进行选择。MIDI 将每个 `(track, channel)` 组合视为一个独立声部，多声部 MusicXML 乐谱可用此方式选取单一声部。
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

   # 选择特定声部 —— 当文件包含多个声部且只需要其中一个时很有用
   model-compose run load-score-track --input '{
     "score": "/path/to/melody.mid",
     "part": 1
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
- **用途**：将 MIDI/MusicXML 文件解析为 `MusicScore`（按声部的音符/歌词/谱号 + 乐谱级别的速度、拍号/调号、和声），使下游组件无需格式特定逻辑即可消费。
- **驱动**：
  - `local` ——基于标准库 + `mido` 的解析（默认）

若要从*音频*（而非符号化乐谱）中进行音高估计，请改用 [`pitch-estimator`](../../model-tasks/pitch-estimation/)。若要在音高校正中将此加载器的输出用作参考旋律，请参见 [`music-pitch-corrector`](../music-pitch-corrector/)。

## 工作流详情

### 1. 加载乐谱文件

**ID**：`load-score`

通过文件的魔术字节自动检测格式（`MThd` → MIDI，`<?xml` → MusicXML，`PK` → 压缩的 `.mxl`），当头部不明确时回退到扩展名。返回文件中的所有声部 — MIDI 中每个有音符活动的 `(track, channel)` 组合对应一个声部。

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `score` | file | 是 | - | 要解析的 MIDI 或 MusicXML 文件 |

#### 示例输出

```json
{
  "format": "midi",
  "duration": 1.5,
  "parts": [
    {
      "id": "T0_C0",
      "part_name": "Melody",
      "part_abbreviation": null,
      "midi_channel": 0,
      "midi_program": null,
      "notes": [
        { "start_time": 0.0, "end_time": 0.5, "pitch": 60, "velocity": 0.787 },
        { "start_time": 1.0, "end_time": 1.5, "pitch": 64, "velocity": 0.630 }
      ],
      "lyrics": [],
      "clefs": []
    }
  ],
  "tempos":          [{ "time": 0.0, "beats_per_minute": 120.0 }],
  "time_signatures": [{ "time": 0.0, "beats": 4, "beat_type": 4 }],
  "key_signatures":  [],
  "harmonies":       []
}
```

- `pitch` 为 MIDI 编号（中央 C = 60）。
- `velocity` 归一化到 [0, 1]；MusicXML 缺乏通用的动态标记，回退为固定的 mezzo-forte 值。
- `tempos`、`time_signatures`、`key_signatures` 依次列出每个变化点。
- `harmonies`、`clefs` 以及歌词的 `syllabic`/`number` 仅 MusicXML 支持。MIDI 加载时为空或 `null`。

---

### 2. 加载指定声部

**ID**：`load-score-track`

通过基于 0 的索引精确选择一个声部。越界索引会抛出错误，而不是默默回退。

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|-----------|------|----------|---------|-------------|
| `score` | file | 是 | - | 要解析的 MIDI 或 MusicXML 文件 |
| `part` | number | 否 | `0` | 基于 0 的声部索引 |

常见场景：
- **多通道 MIDI**：每个有音符活动的 `(track, channel)` 为独立声部 — 用索引选取需要的那一个。
- **MusicXML 主旋律乐谱**：通常是单个 `<part>`，`part=0` 正确。
- **多声部 MusicXML 乐谱**：更高索引用于选择其他声部（如低音、和声）。

#### 示例输出

与 *加载乐谱文件* 结构相同，但 `parts` 范围限定在所选索引。

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
