# 音乐合成器示例

本示例演示 `music-synthesizer` 组件 —— 一个基于节拍时间线的音序器，仅凭一份乐谱（score）就能渲染出立体声 WAV，无需任何音频输入。整首作品由一份 JSON 乐谱描述，包含轨道、以节拍为锚点的事件、母线整形和侧链闪避。

## 概览

本示例暴露单个工作流 **Bake Soundtrack From Score**，由两步管道组成：

1. **Load Score** —— `file-store` 作业读取 compose 文件旁的乐谱 JSON，并按字段解析。
2. **Bake** —— `music-synthesizer` 作业将每个字段原样传给 `sequence` 动作，并返回 WAV 流。

合成器所理解的所有参数（bpm、beats、seed、tracks、master、sidechain）都写在乐谱 JSON 中，因此无需修改 compose 文件，只要把 `score.json` 换成别的乐谱，就能烘焙不同的曲目。

内置的 `score.json` 是一段 32 拍、128 BPM 的演示：4 拍前置计数、kick/hat/snare 律动、8 拍军鼓推进、whoosh 过渡、两小节 drop、由 kick 驱动的 pad/hats/fx 侧链闪避，最后以淡出收尾。

## 准备

### 前置条件

- 已安装 model-compose 并加入 PATH
- 首次运行时会自动安装以下 Python 依赖：
  - `numpy`、`scipy`（`native` 驱动使用）

### 设置

进入示例目录：
```bash
cd examples/media-processing/music-synthesizer
```

## 运行方式

1. **启动服务：**
   ```bash
   model-compose up
   ```

   服务将启动：
   - API 端点：http://localhost:8080/api
   - Web UI：http://localhost:8081

2. **运行工作流：**

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 保持 `score_path` 为空以使用内置的 `score.json`，或将其指向另一份乐谱文件
   - 点击 "Run Workflow" 内联预览生成的 WAV

   **使用 CLI：**
   ```bash
   # 烘焙内置的演示乐谱
   model-compose run bake-soundtrack --input '{}'

   # 烘焙 compose 文件旁的另一份乐谱
   model-compose run bake-soundtrack --input '{
     "score_path": "my-score.json"
   }'
   ```

   **使用 API：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=bake-soundtrack"
   ```

## 组件详情

### Music Synthesizer 组件

- **类型**：`music-synthesizer`
- **驱动**：`native`（numpy + scipy）
- **用途**：从以节拍为锚点的轨道/事件乐谱渲染立体声 WAV，然后应用侧链闪避和母线链（soft-clip → 归一化 → silences → fades）。

该动作始终返回 WAV `audio`。对已有音频做后处理请使用 [`audio-processor`](../audio-processor/)；合并多个音频请使用 [`audio-mixer`](../audio-mixer/)。

### File Store 组件

- **类型**：`file-store`
- **驱动**：`local`
- **用途**：从示例目录读取乐谱 JSON。`${output.content as json}` 将原始字节解析为 dict，第二个作业即可按字段名访问。

## 乐谱格式

乐谱 JSON 与 `sequence` 动作的字段一一对应。compose 文件按字段名传入合成器，中间不做重命名。

### 顶层字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `bpm` | number | 是 | 每分钟节拍数；驱动整曲的节拍-时间换算 |
| `beats` | number | 是 | 整曲长度（以节拍为单位） |
| `seed` | integer | 否 | 基于噪声的乐器的可复现随机种子；不指定则输出非确定性 |
| `tracks` | array | 是 | 构成混音的轨道 |
| `master` | object | 否 | 母线整形 —— soft-clip、归一化、silences、fades |
| `sidechain` | object | 否 | 在汇总前应用的、由 kick 驱动的闪避 |

### 轨道字段

| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `id` | string | 必填 | 轨道标识符；`sidechain.trigger` 和 `sidechain.targets` 会引用 |
| `gain` | number | `1.0` | 整个轨道的线性增益系数 |
| `pan` | number -1..1 | `0.0` | 整个轨道的立体声声像 |
| `events` | array | `[]` | 渲染到此轨道的事件 |

### 事件字段

| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `beat` | number \| array \| `{start, end, step, phase}` | 必填 | 事件触发的节拍位置 |
| `instrument` | string | 必填 | 乐器音色 —— `kick`、`snare`、`hat`、`tick`、`tom`、`pop`、`whoosh`、`chord`、`sub-bass`、`sine`、`noise-burst` |
| `length` | number | `null` | 延音类乐器（`chord`、`sine`、`sub-bass`、`whoosh`、`noise-burst`）的节拍长度；对短促打击类无效 |
| `gain` | number | `1.0` | 此事件的线性增益系数 |
| `pan` | number -1..1 | `0.0` | 此事件的立体声声像；与轨道声像叠加 |
| `params` | object | `{}` | 乐器特定的参数 |

`beat` 接受三种形态：
- 单个数字 —— 事件在该节拍触发一次
- 数字数组 —— 事件在每个列出的节拍触发
- `{start, end, step, phase}` 对象 —— 对所有满足位置 `< end` 的 `n`，事件在 `start + n*step + phase` 触发

### 母线字段

| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `soft_clip` | number | `1.2` | soft-clip 阶段的 tanh 驱动量；`0` 关闭削波 |
| `normalize_level` | number \| null | `-1.0` | 归一化后的目标峰值（dBFS）；`null` 关闭归一化 |
| `silences` | array | `[]` | 主控之后应用的硬静音窗口 |
| `fades` | array | `[]` | 主控之后应用的淡入淡出窗口 |

### 侧链字段

| 字段 | 类型 | 默认 | 说明 |
|------|------|------|------|
| `trigger` | string | 必填 | 事件触发闪避包络的轨道 id |
| `targets` | array of strings | 必填 | 每次触发时被衰减的轨道 id 列表 |
| `depth` | number 0..1 | `0.78` | 每次触发的峰值衰减（`0` = 不衰减，`1` = 完全静音） |
| `attack_time` | duration | `2ms` | 达到峰值衰减所需时间 |
| `release_time` | duration | `70ms` | 恢复到单位增益所需时间 |

## 工作流详情

### Bake Soundtrack From Score

**ID**：`bake-soundtrack`

#### 输入参数

| 参数 | 类型 | 必填 | 默认 | 说明 |
|------|------|------|------|------|
| `score_path` | string | 否 | `score.json` | 相对于示例目录的乐谱 JSON 路径 |

#### 输出

| 字段 | 类型 | 说明 |
|------|------|------|
| `audio` | audio | 整曲的立体声 WAV 渲染结果 |

## 自定义

### 烘焙另一份乐谱

把新的 JSON 文件放到 compose 文件旁，并让 `score_path` 指向它。compose 文件是纯粹的管道 —— 乐谱的每个顶层字段都会原样传给 `sequence`，因此切换乐谱无需修改 compose。

```bash
model-compose run bake-soundtrack --input '{"score_path": "my-score.json"}'
```

### 乐器参考

每个事件都要指定 `instrument`。合成器内置 11 种音色：

- **短促打击类**（忽略 `length`）：`kick`、`snare`、`hat`、`tick`、`tom`、`pop`
- **延音类**（`length` 以节拍为单位）：`chord`、`sub-bass`、`sine`、`whoosh`、`noise-burst`

每种音色的 `params` 请参见 [`music-synthesizer` 组件参考](../../../docs/reference/compose/components/music-synthesizer.md)。

### 侧链闪避

内置乐谱在每一次 kick 时对 `pad`、`hats`、`fx` 进行闪避。删除 `sidechain` 块可以让所有轨道保持原始电平，或把 `trigger` 指向别的轨道（例如 `snares`），就能听到军鼓触发的闪避效果。

### 母线链

`master.soft_clip` 驱动 tanh 削波器；数值越大混音越紧凑，但瞬态被压得越明显。`master.normalize_level` 指定最终峰值（dBFS）—— 设为 `null` 则保留原始求和结果。需要在母线上做硬切或尾部淡出，请使用 `silences` 与 `fades`。

## 提示

- **乐谱即一切**：决定输出的所有内容 —— 速度、长度、轨道、母线、侧链 —— 都写在乐谱 JSON 里。烘焙另一首曲子从不需要动 compose 文件。
- **可复现的噪声**：需要在多次运行之间得到确定性的军鼓/hi-hat/whoosh 输出时，请指定 `seed`。
- **节拍模式优于列表**：对于重复律动，`{ start, end, step }` 比长长的节拍列表更好编辑，也更容易用 `phase` 做相位偏移。
- **延音 vs 短促**：`length` 只被延音类音色读取。在 `kick` 上设置它无害，但没有效果。
- **侧链路由需要有效 id**：`trigger` 与 `targets` 的每一项都必须匹配 `tracks` 中已存在的 `id`，否则乐谱校验会失败。

## 故障排查

### 常见问题

1. **`bpm must be positive`** / **`beats must be positive`**：非正的速度或长度不是有效乐谱，两者都需要设置为正数。
2. **`channels must be 1 or 2`**：合成器只输出单声道或立体声 WAV，其他数值会被拒绝。
3. **`Duplicate track ids`**：`tracks[].id` 必须全部唯一 —— 侧链路由与诊断都依赖它。
4. **`Sidechain trigger '...' does not match any track id`** / **`Sidechain targets not found among tracks`**：修正 `sidechain` 块中的 id 拼写错误，或者补上缺失的轨道。
5. **`Beat-pattern step must be positive`**：`{ start, end, step }` 节拍模式需要 `step > 0`。使用 `phase` 做偏移，而不是负 step。
6. **末尾输出为静音**：检查 `master.silences` —— 落在最后一个事件之后的硬静音窗口会让渲染看起来像"被切掉了"。
7. **找不到乐谱文件**：`score_path` 是相对于示例目录解析的（`file-store` 的 `base_path: .`）。除非扩大 `base_path`，否则请传入与 `model-compose.yml` 同目录的文件名，而不是绝对路径。
