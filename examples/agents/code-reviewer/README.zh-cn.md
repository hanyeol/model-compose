# 代码审查代理示例

此示例演示了一个自主代理，它可以读取文件、列出目录和搜索代码来执行代码审查并提供改进建议。

## 概述

代理通过 ReAct 循环运行：

1. **接收请求**：用户提供代码审查请求和目标路径
2. **探索**：代理列出目录并读取相关文件
3. **搜索**：代理在代码库中搜索特定模式
4. **审查**：理解代码后，生成详细的审查结果

### 可用工具

| 工具 | 描述 |
|------|------|
| `read_file` | 读取文件内容 |
| `list_directory` | 列出文件和目录的详细信息 |
| `search_code` | 使用 grep 在文件中搜索模式 |

## 准备工作

### 前置条件

- 已安装 model-compose 并在您的 PATH 中可用
- OpenAI API 密钥

### 环境配置

1. 导航到此示例目录：
   ```bash
   cd examples/agents/code-reviewer
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
     -d '{"request": "审查这段代码中的潜在错误并提出改进建议", "target_path": "/path/to/project/src"}'
   ```

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 输入审查请求和目标路径，然后点击"运行工作流"按钮

   **使用 CLI：**
   ```bash
   model-compose run --input '{"request": "查找安全漏洞", "target_path": "./src"}'
   ```

## 组件详情

### OpenAI GPT-4o 组件 (gpt-4o)
- **类型**：HTTP 客户端组件
- **用途**：用于代理推理和代码分析的 LLM
- **API**：OpenAI GPT-4o Chat Completions（function calling）

### Shell 组件 (file-reader, dir-lister, code-searcher)
- **类型**：Shell 组件
- **用途**：用于代码探索的文件系统操作
- **命令**：`cat`、`ls -la`、`grep -rn`

### 代码审查代理组件 (code-reviewer)
- **类型**：Agent 组件
- **用途**：探索和审查代码的自主代理
- **最大迭代次数**：15

## 工作流详情

### 工具：read_file

**描述**：读取并返回文件的内容。

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `path` | string | 是 | - | 要读取的文件路径 |

### 工具：list_directory

**描述**：列出给定路径下所有文件和目录的详细信息。

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `path` | string | 是 | - | 要列出的目录路径 |

### 工具：search_code

**描述**：使用 grep 在文件中递归搜索模式。

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `pattern` | string | 是 | - | 要搜索的模式或正则表达式 |
| `path` | string | 否 | `.` | 要搜索的目录路径 |

## 自定义

- 将 `gpt-4o` 替换为其他支持 function calling 的模型
- 添加更多工具（例如 `wc` 统计行数、`diff` 比较文件）
- 调整 `max_iteration_count` 以允许更深入的代码探索
- 根据需要修改 shell 命令（例如使用 `rg` 代替 `grep`）
