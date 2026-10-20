# 音高校正器示例

此示例演示如何使用 model-compose 的 `music-pitch-corrector` 组件对录制的人声进行离线音高校正——检测音高、将每个音符对齐到歌曲调性，并在保留音色的前提下重新合成。

## 概述

校正分两个阶段运行，便于在中间检查或编辑结果：

1. **plan** —— 从音高轨为每个演唱音符挑选目标音高并生成校正曲线（JSON）。只接受 `pitch`，不接受录音。
2. **apply** —— 沿着曲线对人声进行重新合成。接受录音（`audio`）和曲线。曲线是 plan 唯一的交接物；音频管线中没有任何隐含项。

默认的 `correct-pitch` 工作流一次性运行两个阶段（需要 `audio` 和 `pitch` 两者）。其他工作流则展示分离的路径——plan 系列将曲线输出为 JSON，而 `apply-curve` 接受已编辑的曲线进行重新合成。

`audio` 始终意味着"要重新合成的录音"——绝不是音高估计源。音高估计发生在独立组件（`music-pitch-estimation`）中，所以 `plan` 与引擎无关，也不会悄悄回退到内置估计器。

### 工作流

1. **校正人声音高**（默认）—— 音高估计 → 调性检测 → 曲线规划 → WORLD 重新合成 → 与伴奏混合。目标音高通过将每个演唱音符对齐到检测到的调性来选取。
2. **仅规划校正曲线** —— 与 `correct-pitch` 路径相同，但跳过重新合成；以 JSON 输出曲线，便于在交给 `apply-curve` 之前手工编辑音符目标或跳过特定音符
3. **根据参考旋律校正人声音高** —— 与人声一起上传旋律文件（`.mid`、`.midi`、`.xml`、`.musicxml` 或 `.mxl`）。`music-score-loader` 提取音符，对人声运行音高估计，将每个演唱音符对齐到对应的参考音符，WORLD 重新合成，与伴奏混合。当您已有歌曲的目标旋律（手工 MIDI、乐谱编辑器导出等）并希望将每个演唱音符映射到**对应的参考音符**而非最近的音阶音时使用
4. **根据参考旋律仅规划曲线** —— 相同的旋律加载路径，但不进行重新合成；以 JSON 输出曲线供手工编辑
5. **应用已编辑的曲线** —— 使用已编辑的 `plan-only` 或 `plan-with-melody` 曲线重新合成人声，使曲线编辑真正进入输出

## 准备工作

### 前置条件

- 已安装 model-compose 并在您的 PATH 中可用
- Python 依赖会在首次运行时自动安装：
  - `pyworld`、`librosa`、`numpy`、`soundfile`（由 `world` 驱动使用）
- 如果您的平台没有预构建 wheel，`pyworld` 将从源码构建，因此必须有可用的 C 编译器。

### 设置

进入此示例目录：
```bash
cd examples/media-processing/music-pitch-corrector
```

## 运行方法

1. **启动服务：**
   ```bash
   model-compose up
   ```
   首次启动时会安装 `pyworld`、`librosa` 等依赖；如果 `pyworld` 需要从 sdist 编译，可能需要约一分钟。

2. **打开 Web UI：**
   访问 `http://localhost:8081` 并选择一个工作流。默认表单需要人声文件和伴奏文件。

3. **直接调用 API：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/correct-pitch/runs \
        -F vocal=@vocal.wav \
        -F accompaniment=@backing.wav \
        -F strength=0.8
   ```

## 校正行为

算法调参位于 `params:` 下（默认值合理，可按需覆盖）：

- **params.strength** —— 控制每个音符被拉向目标的程度。`1.0` 为完全校正；`0.6` 保留一些个性
- **params.retune_speed** —— 演唱音符滑向目标的速度。`0ms` 为机器人式 Auto-Tune 效果；`40ms`–`80ms` 听感自然
- **params.tolerance_cents** —— 距离目标在此音分范围内的音符不动。表现力强的演唱可提高；精准的录音室 take 可降低
- **params.preserve_vibrato** —— 仅移动音符中心音高，保留音符内部的颤音。禁用则将所有内容平坦化到目标

## 曲线格式

`plan` 发出的曲线由两部分组成：`notes` 数组（每个检测到的音符一条）和 `frames` 块（逐帧的稠密数组）。你可以在 `plan` 和 `apply` 之间直接编辑 JSON 以覆盖单个音符——更改 `target_pitch`，设为 `target_pitch: null` 以保持某个音符原样，或完全删除某个音符以保留其原始音高。

## 已知限制

- 重新合成的呼吸声和粗糙发声听起来可能比原始更光滑。如果需要恢复质感，可在校正区域下方混入原始干声。
- 和声人声（一个麦克风上两个歌手）会被压缩为主导音高——此组件假设单旋律线。
- 参考旋律文件支持 MIDI 和 MusicXML。其他格式（ABC、MEI、Guido 等）未实现，请先经由转换器处理或直接传入预构建的音符列表。
