# 磁盘分析代理示例

此示例演示了一个使用 shell 命令作为工具来分析系统磁盘使用情况并提供详细建议的自主代理。它是 `analyze-disk-usage` 示例的代理版本。

## 概述

代理通过 ReAct 循环运行：

1. **接收问题**：用户提供磁盘分析问题（或使用默认值）
2. **调查**：代理自主运行 shell 命令来检查磁盘使用情况、目录大小和文件列表
3. **分析**：收集足够的信息后，生成详细的分析和建议

### 可用工具

| 工具 | 描述 |
|------|------|
| `get_disk_usage` | 获取所有挂载文件系统的磁盘使用情况 (`df -h`) |
| `get_directory_sizes` | 获取特定目录的总大小 (`du -sh`) |
| `list_files` | 列出文件和目录的详细信息 (`ls -la`) |

## 准备工作

### 前置条件

- 已安装 model-compose 并在您的 PATH 中可用
- OpenAI API 密钥

### 环境配置

1. 导航到此示例目录：
   ```bash
   cd examples/agents/disk-analyzer
   ```

2. 复制示例环境文件：
   ```bash
   cp .env.sample .env
   ```

3. 编辑 `.env` 并添加您的 OpenAI API 密钥：
   ```env
   OPENAI_API_KEY=your-openai-api-key
   ```

## 运行方式

1. **启动服务：**
   ```bash
   model-compose up
   ```

2. **运行工作流：**

   **使用 API：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"question": "/home 下哪些目录占用了最多的磁盘空间？"}'
   ```

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 输入您的问题并点击"运行工作流"按钮

   **使用 CLI：**
   ```bash
   model-compose run --input '{"question": "分析磁盘使用情况并找出大文件"}'
   ```

## 组件详情

### OpenAI GPT-4o 组件 (gpt-4o)
- **类型**：HTTP 客户端组件
- **用途**：用于代理推理和工具使用的 LLM
- **API**：OpenAI GPT-4o Chat Completions（function calling）

### Shell 组件 (disk-usage, directory-sizes, file-lister)
- **类型**：Shell 组件
- **用途**：执行磁盘分析系统命令
- **命令**：`df -h`、`du -sh`、`ls -la`

### 磁盘分析代理组件 (disk-analyzer)
- **类型**：Agent 组件
- **用途**：调查磁盘使用情况的自主代理
- **最大迭代次数**：10

## 工作流详情

### 工具：get_disk_usage

**描述**：获取所有挂载文件系统的磁盘使用信息。

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| - | - | - | - | 此工具不需要输入参数 |

### 工具：get_directory_sizes

**描述**：获取特定目录的总大小。

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `path` | string | 是 | - | 要测量的目录的绝对路径 |

### 工具：list_files

**描述**：列出给定路径中文件和目录的详细信息。

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `path` | string | 是 | - | 要列出的目录的绝对路径 |

## 自定义

- 将 `gpt-4o` 替换为其他支持 function calling 的模型
- 添加更多 shell 工具（例如 `find` 搜索文件、`top` 获取进程信息）
- 调整 `max_iteration_count` 以允许更深入的调查
- 根据您的操作系统修改 shell 命令
