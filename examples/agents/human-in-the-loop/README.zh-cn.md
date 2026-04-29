# Human-in-the-Loop 代理示例

本示例展示了一个文件管理代理，它在执行危险操作（写入、删除）前需要人工审批，同时允许安全操作（读取、列表）无中断运行。

## 概述

代理通过带有中断机制的 ReAct 循环运行：

1. **接收请求**：用户要求代理执行文件操作
2. **选择工具**：代理决定使用哪些工具
3. **安全操作**：读取和列表操作立即执行，无需中断
4. **危险操作**：写入和删除操作暂停，等待人工审批后再执行
5. **返回结果**：完成操作后生成结果摘要

### 可用工具

| 工具 | 描述 | 需要审批 |
|------|------|:--------:|
| `read_file` | 读取文件内容 | 否 |
| `list_directory` | 列出文件和目录 | 否 |
| `write_file` | 将内容写入文件 | 是 |
| `delete_file` | 删除文件 | 是 |

## 准备工作

### 前置条件

- 已安装 model-compose 并可在 PATH 中使用
- OpenAI API 密钥

### 环境配置

1. 进入本示例目录：
   ```bash
   cd examples/agents/human-in-the-loop
   ```

2. 复制示例环境文件：
   ```bash
   cp .env.sample .env
   ```

3. 编辑 `.env` 文件并添加您的 API 密钥：
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
     -d '{"request": "List the files in the current directory."}'
   ```

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 输入您的请求并点击 "Run Workflow"
   - 当触发危险操作时，会弹出确认对话框

   **使用 CLI：**
   ```bash
   model-compose run --input '{"request": "Create a file called hello.txt with the content Hello World"}'
   ```

## 组件详情

### OpenAI GPT-4o 组件 (gpt-4o)
- **类型**：HTTP 客户端组件
- **用途**：用于代理推理和工具选择的 LLM
- **API**：支持函数调用的 OpenAI GPT-4o Chat Completions

### 文件读取组件 (file-reader)
- **类型**：Shell 组件
- **用途**：使用 `cat` 读取文件内容

### 目录列表组件 (directory-lister)
- **类型**：Shell 组件
- **用途**：使用 `ls -la` 列出目录内容

### 文件写入组件 (file-writer)
- **类型**：Shell 组件
- **用途**：使用 Shell 重定向将内容写入文件

### 文件删除组件 (file-deleter)
- **类型**：Shell 组件
- **用途**：使用 `rm` 删除文件

### 文件管理代理组件 (file-manager)
- **类型**：代理组件
- **用途**：协调文件操作，对危险操作进行人工审批
- **最大迭代次数**：15

## 中断工作原理

`interrupt` 功能在危险作业运行前暂停工作流执行：

```yaml
interrupt:
  before:
    message: "The agent wants to write to a file. Please review and approve."
    metadata:
      path: ${job.input.path}
      content: ${job.input.content}
```

- **`before`**：作业在执行前暂停，并向用户显示消息
- **`metadata`**：在审批对话框中显示的附加上下文（如文件路径、内容）
- 用户可以选择**批准**继续执行，或**拒绝**取消操作

此模式确保代理在没有人工明确同意的情况下无法执行破坏性操作。

## 自定义

- 将 `gpt-4o` 替换为其他支持函数调用的模型
- 添加更多工具（如重命名、移动、复制），可选择是否添加中断保护
- 调整 `max_iteration_count` 以控制代理可执行的工具调用次数
- 修改 `system_prompt` 以更改代理行为或限制允许的路径
