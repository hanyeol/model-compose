# 文本嵌入 (llama.cpp) 示例

本示例演示如何使用 model-compose 的内置 `llamacpp` 驱动，通过 llama.cpp 使用 GGUF 格式嵌入模型在本地生成文本嵌入。

## 概述

此工作流提供本地文本嵌入功能：

1. **llama.cpp 后端**：高效运行 GGUF 量化嵌入模型
2. **CPU 友好**：无需 GPU 也能在 CPU 上流畅运行
3. **L2 归一化**：可选归一化嵌入以适用于余弦相似度
4. **无需外部 API**：无 API 依赖的完全离线嵌入

## 准备工作

### 先决条件

- 已安装 model-compose 并在 PATH 中可用
- 已安装 `llama-cpp-python`（请参阅下方安装说明）
- 在 `./models/nomic-embed-text-v1.5.Q4_K_M.gguf` 路径下放置 GGUF 嵌入模型文件

### 安装 llama-cpp-python

```bash
# 仅 CPU
pip install llama-cpp-python

# macOS Metal 加速 (Apple Silicon / AMD GPU)
CMAKE_ARGS="-DLLAMA_METAL=on" pip install llama-cpp-python

# CUDA (NVIDIA GPU)
CMAKE_ARGS="-DLLAMA_CUDA=on" pip install llama-cpp-python
```

### 下载 GGUF 嵌入模型

```bash
mkdir -p models

# 从 HuggingFace 下载 nomic-embed-text-v1.5 Q4_K_M
curl -L -o models/nomic-embed-text-v1.5.Q4_K_M.gguf \
  https://huggingface.co/nomic-ai/nomic-embed-text-v1.5-GGUF/resolve/main/nomic-embed-text-v1.5.Q4_K_M.gguf
```

### 环境配置

1. 导航到此示例目录：
   ```bash
   cd examples/model-tasks/text-embedding-llamacpp
   ```

2. 将 GGUF 嵌入模型文件放置在 `./models/` 目录下。

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
         "text": "The quick brown fox jumps over the lazy dog."
       }
     }'
   ```

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 输入文本
   - 点击 "Run Workflow" 按钮

   **使用 CLI：**
   ```bash
   model-compose run --input '{"text": "The quick brown fox jumps over the lazy dog."}'
   ```

## 组件详情

### Text Embedding Model 组件
- **类型**：具有 text-embedding 任务的 Model 组件
- **驱动**：`llamacpp`
- **模型**：GGUF 量化嵌入模型（默认：nomic-embed-text-v1.5 Q4_K_M）
- **功能**：
  - 通过 llama.cpp 实现 CPU 优化推理
  - 自动激活 `embedding=True` 模式
  - 用于余弦相似度场景的 L2 归一化
  - 批量处理支持
  - 通过 `n_gpu_layers` 进行 GPU 卸载

## 工作流详情

### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|---------|------|------|--------|------|
| `text` | text | 是 | - | 要嵌入的输入文本 |

### 输出格式

| 字段 | 类型 | 描述 |
|-----|------|------|
| `embedding` | JSON 数组 | 浮点嵌入向量 |

## 自定义

### GPU 卸载

```yaml
component:
  type: model
  task: text-embedding
  driver: llamacpp
  model:
    provider: local
    path: ./models/nomic-embed-text-v1.5.Q4_K_M.gguf
    format: gguf
  device: cuda        # macOS 上使用 "metal"
  n_gpu_layers: -1    # -1 = 卸载全部层
  context_length: 2048
  action:
    text: ${input.text}
    params:
      normalize: true
```

### 批量嵌入

```yaml
component:
  action:
    text: ${input.texts}   # 传入字符串列表
    batch_size: 16
    params:
      normalize: true
```

### 不进行归一化

```yaml
component:
  action:
    text: ${input.text}
    params:
      normalize: false    # 返回原始嵌入
```

## 系统要求

### 最低要求 (CPU)
- **RAM**：1GB+（取决于模型大小和量化）
- **磁盘空间**：模型文件大小（nomic-embed Q4_K_M ≈ 80MB）
- **CPU**：任何现代 x86_64 或 ARM64 处理器

### 推荐配置 (GPU)
- **VRAM**：大多数嵌入模型 1GB+
- **GPU**：NVIDIA (CUDA) 或 Apple Silicon (Metal)

## 推荐的 GGUF 嵌入模型

| 模型 | 维度 | 大小 (Q4) | 用途 |
|-----|--------|---------|------|
| `nomic-ai/nomic-embed-text-v1.5-GGUF` | 768 | ~80MB | 通用 |
| `CompendiumLabs/bge-large-en-v1.5-gguf` | 1024 | ~300MB | 高质量英文 |
| `CompendiumLabs/bge-m3-gguf` | 1024 | ~600MB | 多语言 |

## 故障排除

1. **未找到 `llama_cpp`**：使用 `pip install llama-cpp-python` 安装
2. **模型类型错误**：使用专用嵌入模型，而非生成模型
3. **内存不足**：使用更低的量化或更小的嵌入模型
4. **嵌入速度慢**：使用 `n_gpu_layers: -1` 启用 GPU 卸载
5. **全零嵌入**：确保模型支持 embedding 模式（使用专用嵌入 GGUF）
