# 动作生成 (Kimodo) 模型任务示例

此示例使用 NVIDIA 的 Kimodo 扩散模型从文本提示生成 3D 人体动作序列，通过 model-compose 的内置模型任务功能在本地运行。Kimodo 是一个运动学动作扩散模型，基于约 700 小时的光学动作捕捉数据训练，输出为关节位置、旋转矩阵和足部接触标签的序列，可直接用于 3D 动画工具或基于物理的仿真。

## 概述

此示例公开一个 `generate` 工作流。它接受自然语言提示并返回 NPZ 文件形式的动作序列。

响应负载包含以下项目：

- `posed_joints` — 世界空间中的关节位置，形状 `[T, J, 3]`
- `global_rot_mats` / `local_rot_mats` — 每个关节的旋转矩阵，形状 `[T, J, 3, 3]`
- `foot_contacts` — 左脚跟、左脚趾、右脚跟、右脚趾的二进制标签，形状 `[T, 4]`
- `root_positions`、`smooth_root_pos`、`global_root_heading`
- `fps` — 模型生成时使用的帧率

`T` 是帧数，`J` 是所选骨架的关节数。

## 准备工作

### 前置条件

- 已安装 model-compose 并在您的 PATH 中可用
- **强烈推荐 NVIDIA GPU**。Kimodo 在 RTX 3090 / 4090 / A100 上经过测试。Mac / CPU 情况请参考下方 [系统要求](#系统要求)。
- 首次运行时需要互联网访问（检查点和文本编码器从 Hugging Face 下载）
- ~20–30 GB 磁盘空间（Kimodo 检查点 + LLM2Vec-Llama-3-8B 文本编码器权重）

### 环境配置

1. 导航到此示例目录：
   ```bash
   cd examples/model-tasks/motion-generation-kimodo
   ```

2. 无需额外的环境配置 — Kimodo 及其 PyTorch 依赖项将在首次启动时自动安装。

## 运行方法

1. **启动服务：**
   ```bash
   model-compose up
   ```

2. **生成动作：**

   **使用 API：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{
       "input": {
         "prompt": "a person walks forward, then waves with the right hand",
         "duration": 6.0,
         "diffusion_steps": 20,
         "seed": 42
       }
     }' \
     --output motion.npz
   ```

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 输入动作提示并调整 duration / diffusion steps
   - 点击 "Run Workflow" 并下载生成的 NPZ

   **使用 CLI：**
   ```bash
   model-compose run generate --input '{"prompt": "a person jumps and lands"}' --output motion.npz
   ```

3. **查看或可视化 NPZ** — 使用任何能够加载 NumPy 归档的工具。例如：通过 SMPL / SOMA 导入器加载到 Blender、将 G1 骨架输出送入 MuJoCo，或将 SMPL-X 输出传递给下游重定向流水线。

## 组件详情

### Kimodo 动作生成组件
- **Type**：具有 `motion-generation` 任务的模型组件
- **Driver / Family**：`custom` / `kimodo`
- **Preset**：`Kimodo-SOMA-RP-v1.1`（SOMA 77 关节骨架，基于 700 小时 Bones Rigplay 训练）
- **Model**：`nvidia/Kimodo-SOMA-RP-v1.1`（从 `preset` 自动推导；需要时用 `model:` 覆盖）
- **Device**：推荐 `cuda`
- **Output Format**：NPZ 文件 (`application/x-npz`)
- **Concurrency**：1（一次仅处理一个请求）

### 模型信息：Kimodo
- **开发者**：NVIDIA Toronto AI Lab（参见 [Kimodo 项目页面](https://research.nvidia.com/labs/sil/projects/kimodo/)）
- **类型**：基于 Transformer 的动作扩散模型，使用 DDIM 采样和无分类器引导
- **可用预设**：
  - `Kimodo-SOMA-RP-v1.1` *(默认)* — SOMA 骨架，Bones Rigplay 1
  - `Kimodo-SOMA-SEED-v1.1` — SOMA 骨架，BONES-SEED 子集
  - `Kimodo-G1-RP-v1` — Unitree G1 机器人骨架
  - `Kimodo-G1-SEED-v1` — Unitree G1，BONES-SEED 子集
  - `Kimodo-SMPLX-RP-v1` — SMPL-X 骨架（research 许可）
- **CFG 类型**：`nocfg`、`regular`、`separated` *(默认)*。在 `separated` 下，`cfg_weight` 可以是 `[text, constraint]` 两元素对。
- **文本编码器**：LLM2Vec-Llama-3-8B。可强制在 CPU 上运行以降低显存 — 参见 [降低显存使用](#降低显存使用)。

## 工作流详情

### "Generate" 工作流（默认）

**描述**：从自然语言提示生成动作序列。

#### 输入参数

| 参数              | 类型    | 必需 | 默认值  | 描述 |
|-------------------|---------|------|---------|------|
| `prompt`          | text    | 是   | —       | 对所需动作的自然语言描述 |
| `duration`        | number  | 否   | `4.0`   | 动作持续时间（秒） |
| `num_samples`     | integer | 否   | `1`     | 要生成的动作变体数量 |
| `diffusion_steps` | integer | 否   | `10`    | DDIM 去噪步数；步数越多质量越好但速度越慢 |
| `cfg_weight`      | number  | 否   | `2.0`   | 无分类器引导权重；使用 `separated` CFG 时为 `[text, constraint]` 两元素列表 |
| `post_processing` | boolean | 否   | `true`  | 对输出应用足部滑动和约束清理 |
| `seed`            | integer | 否   | —       | 用于可复现性的随机种子 |

#### 输出格式

| 字段 | 类型                 | 描述 |
|------|---------------------|------|
| —    | `application/x-npz` | 包含 `posed_joints`、`global_rot_mats`、`local_rot_mats`、`foot_contacts`、`root_positions`、`smooth_root_pos`、`global_root_heading`、`fps` 的 NPZ 归档 |

## 系统要求

### 最低要求

- **GPU**：推荐 NVIDIA GPU。Kimodo 在 RTX 3090 / 4090 / A100 上进行测试，全 GPU 推理约 ~17 GB 显存，或低显存环境下 `<3 GB 显存 + CPU 文本编码器`。
- **RAM**：推荐 32 GB（文本编码器强制在 CPU 上时是 8B 参数模型）
- **磁盘空间**：Kimodo 检查点和 LLM2Vec 文本编码器缓存 ~20–30 GB
- **互联网**：仅初次从 Hugging Face 下载时需要

### Apple Silicon / Mac

Kimodo **在 macOS 上没有官方支持**。上游项目仅测试 CUDA。使用 `device: cpu` 运行是可行的但非常慢（每次生成需要几分钟），因为 8B 参数文本编码器也必须在 CPU 上运行。使用 `device: mps` 运行可能在不支持的运算符上失败 — model-compose 会接受该配置，但 Kimodo 本身可能在推理时报错。

### 性能说明

- 首次运行从 Hugging Face 下载 Kimodo 检查点 + LLM2Vec 权重
- 未量化的文本编码器占用大部分显存；使用 `text_encoder_device: cpu` 可将 GPU 使用量降至 ~3 GB 以下，但文本编码会变慢
- 每个组件单一并发请求以防止显存耗尽

## 自定义

### 降低显存使用

```yaml
component:
  text_encoder_device: cpu    # 将 LLM2Vec 保持在 CPU 上；GPU 使用量降至 <3 GB
  text_encoder_fp32: false    # 默认 bf16 更快且占用更少内存
```

### 切换骨架 / 数据集

```yaml
component:
  # model 自动推导为 nvidia/<preset>；仅在托管镜像时覆盖。
  preset: Kimodo-G1-RP-v1     # Unitree G1 机器人骨架
```

可用的预设列在 [模型信息](#模型信息kimodo) 下。

### 调整无分类器引导

```yaml
component:
  cfg_type: separated         # nocfg | regular | separated

actions:
  - method: generate
    params:
      cfg_weight: [2.0, 2.0]  # 在 `separated` 下为 [text, constraint]
```

对 `nocfg` / `regular` 使用单个数字，对 `separated` 使用两元素列表（与 Kimodo 的 `--cfg_weight` CLI 行为一致）。

### 每个提示生成多个变体

```yaml
actions:
  - method: generate
    params:
      num_samples: 4
```

Kimodo 返回批量张量；生成的 NPZ 沿前导轴携带所有样本。

## 限制

- **暂不支持约束**：Kimodo 的全身关键帧、2D 路径点和末端执行器约束轨道需要 Python 侧约束对象，在此示例中未通过 DSL 公开。目前仅支持基于文本的生成。约束支持可能在 DSL 表面设计完成后作为后续补充。

## 相关示例

- **[image-to-3d-pixal3d](../image-to-3d-pixal3d/)**：从单张图像生成 3D 网格
- **[talking-head-sonic](../talking-head-sonic/)**：从肖像和音频生成说话头视频
- **[music-generation-yue2](../music-generation-yue2/)**：使用 YuE2 的本地音乐生成
