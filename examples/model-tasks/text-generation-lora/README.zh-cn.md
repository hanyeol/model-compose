# 使用多个 LoRA 适配器的文本生成

本示例演示如何将多个 LoRA（低秩适应）适配器与基础语言模型结合使用，以增强不同领域和任务的文本生成能力。

## 概述

此工作流将基础 Llama 2 7B 模型与多个专业 LoRA 适配器结合：

- **Alpaca 适配器**（`tloen/alpaca-lora-7b`）：指令遵循能力
- **Guanaco 适配器**（`plncmm/guanaco-lora-7b`）：对话式和助手式响应

每个适配器可以独立加权，从而对模型的行为进行细粒度控制。

## 功能

- **多适配器支持**：同时加载多个 LoRA 适配器
- **权重控制**：调整每个适配器的影响（0.0 到 2.0+）
- **设备分配**：为每个适配器指定不同的设备
- **精度控制**：为每个适配器设置单独的精度（float16、bfloat16）

## 准备工作

### 先决条件

- 已安装 model-compose 并在 PATH 中可用
- 具有足够 VRAM 的 CUDA 兼容 GPU（推荐：16GB+）
- 带有 transformers、torch 和 peft 的 Python 环境（自动管理）
- 访问门控模型（例如 Llama 2）的 HuggingFace 令牌

### 环境配置

1. 导航到此示例目录：
   ```bash
   cd examples/model-tasks/text-generation-lora
   ```

2. 为门控模型设置 HuggingFace 身份验证：
   ```bash
   export HUGGINGFACE_TOKEN=your_huggingface_token
   ```

   或者，通过 CLI 登录：
   ```bash
   huggingface-cli login
   ```

3. 无需额外配置 - 模型和 LoRA 适配器会自动下载。

## 配置

### 基础模型
```yaml
model: meta-llama/Llama-2-7b-hf
```

### LoRA 适配器
```yaml
peft_adapters:
  - type: lora
    name: alpaca
    model: tloen/alpaca-lora-7b
    weight: 0.7

  - type: lora
    name: assistant
    model: plncmm/guanaco-lora-7b
    weight: 0.8
```

### 参数
- `weight`：适配器影响的缩放因子（默认：1.0）
  - `< 1.0`：减少适配器效果
  - `1.0`：完整适配器效果
  - `> 1.0`：放大适配器效果
- `precision`：模型精度（例如 `float16`、`bfloat16`）

## 如何运行

1. **启动服务：**
   ```bash
   model-compose up
   ```

2. **运行工作流：**

   **使用 API：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{
       "input": {
         "prompt": "Explain quantum computing in simple terms."
       }
     }'
   ```

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 输入您的提示
   - 点击"Run Workflow"按钮

   **使用 CLI：**
   ```bash
   model-compose run --input '{"prompt": "Explain quantum computing in simple terms."}'
   ```

### 示例提示

**指令遵循（Alpaca）：**
```
Below is an instruction that describes a task. Write a response that appropriately completes the request.

### Instruction:
Write a Python function to calculate fibonacci numbers.

### Response:
```

**对话式（Guanaco）：**
```
Human: What are the benefits of using LoRA for fine-tuning?
Assistant:
```

## 工作原理

### LoRA 架构

LoRA 将权重更新分解为低秩矩阵：
```
W = W₀ + ΔW
ΔW = B × A × scaling
```

其中：
- `W₀`：冻结的预训练权重
- `A`：低秩下投影（rank × input_dim）
- `B`：低秩上投影（output_dim × rank）
- `scaling`：lora_alpha / rank

### 多适配器混合

当加载多个适配器时，它们按顺序应用：
```
output = base_model(input)
for adapter in adapters:
    output += adapter.forward(input) × weight
```

`weight` 参数控制每个适配器的贡献。

## 自定义

### 添加您自己的 LoRA

您可以从 HuggingFace Hub 或本地路径添加自定义 LoRA 适配器：

```yaml
peft_adapters:
  # HuggingFace Hub
  - type: lora
    name: my_adapter
    model: username/my-lora-adapter
    weight: 1.0

  # 本地路径
  - type: lora
    name: local_adapter
    model:
      provider: local
      path: ./path/to/lora
    weight: 0.5
```

### 调整适配器权重

微调适配器之间的平衡：

```yaml
peft_adapters:
  - type: lora
    name: alpaca
    weight: 0.3  # 减少指令遵循

  - type: lora
    name: assistant
    weight: 1.2  # 增加对话性
```

## 系统要求

### 最低要求
- **GPU VRAM**：16GB+（Llama-2-7b + 适配器所需）
- **RAM**：16GB 系统 RAM（推荐 32GB+）
- **磁盘空间**：20GB+ 用于模型和适配器存储
- **CUDA**：CUDA 11.8+ 兼容 GPU（NVIDIA）
- **互联网**：用于初始模型和适配器下载

### 性能说明
- 首次运行需要下载基础模型（约 13GB）和适配器（每个约 100MB）
- 模型加载需要 2-5 分钟，具体取决于硬件
- 实际推理速度需要 GPU 加速
- 多个适配器会增加内存使用量和加载时间

## 参考资料

- [PEFT 文档](https://huggingface.co/docs/peft)
- [LoRA 论文](https://arxiv.org/abs/2106.09685)
- [Alpaca 模型](https://github.com/tloen/alpaca-lora)
- [Guanaco 数据集](https://huggingface.co/datasets/timdettmers/openassistant-guanaco)
