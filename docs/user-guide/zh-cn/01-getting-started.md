# 第一章：入门指南

## 1.1 简介和概述

**model-compose** 是一个声明式 AI 工作流编排工具，让您可以使用简单的 YAML 配置文件定义和运行 AI 模型流水线。受 `docker-compose` 启发，它将声明式配置的理念带入了 AI 模型编排领域。

### 什么是 model-compose？

model-compose 让您可以：

- **声明式地组合 AI 工作流**：在 YAML 中定义完整的多步骤 AI 流水线——无需自定义代码
- **连接任何服务**：无缝集成外部 AI 服务（OpenAI、Anthropic 等）或运行本地 AI 模型
- **构建复杂流水线**：将多个模型和 API 链接在一起，步骤之间数据流清晰
- **灵活执行**：从 CLI 运行工作流，作为 HTTP API 暴露，或使用模型上下文协议（MCP）
- **轻松部署**：使用最小配置在本地运行或通过 Docker 部署

### 关键用例

- **API 编排**：链接多个 AI 服务调用（例如，文本生成 → 翻译 → 语音合成）
- **本地模型推理**：运行 HuggingFace 模型进行聊天补全、图像分析或嵌入等任务
- **RAG 系统**：使用向量存储构建检索增强生成流水线
- **多模态工作流**：在单个流水线中结合文本、图像和音频处理
- **自动化工作流**：在不编写自定义集成代码的情况下脚本化和自动化 AI 任务

### 工作原理

model-compose 由三个核心元素组成：

1. **YAML 配置文件**（`model-compose.yml`）：声明式定义组件、工作流和执行环境。
2. **组件系统**：提供可重用的工作单元，如 API 调用、本地模型执行和数据处理。
3. **执行环境**：通过 CLI 命令或通过 HTTP/MCP 服务器运行工作流。

例如，一个调用 OpenAI API 的简单工作流可以定义为：

```yaml
components:
  - id: chatgpt
    type: http-client
    base_url: https://api.openai.com/v1
    action:
      path: /chat/completions

workflows:
  - id: generate-text
    jobs:
      - component: chatgpt
```

仅使用此配置，您就可以从 CLI 运行它，作为 HTTP API 暴露，或部署为 Docker 容器。

---

## 1.2 安装

### 要求

- **Python 3.9 或更高版本**
- pip 包管理器

### 通过 pip 安装

安装 model-compose 最简单的方法是通过 pip：

```bash
pip install model-compose
```

### 从源码安装

对于最新的开发版本或为项目贡献：

```bash
git clone https://github.com/hanyeol/model-compose.git
cd model-compose
pip install -e .
```

使用额外依赖进行开发：

```bash
pip install -e .[dev]
```

### 验证安装

检查 model-compose 是否正确安装：

```bash
model-compose --version
```

您应该看到打印的版本号。

### 使用虚拟环境（推荐）

建议使用虚拟环境以避免依赖冲突：

```bash
# 创建虚拟环境
python -m venv venv

# 激活它
# 在 macOS/Linux 上：
source venv/bin/activate
# 在 Windows 上：
venv\Scripts\activate

# 安装 model-compose
pip install model-compose
```

---

## 1.3 运行您的第一个工作流

让我们逐步创建并运行您的第一个 model-compose 工作流。我们将构建一个调用 OpenAI API 生成文本的简单工作流。

### 1.3.1 简单示例（OpenAI API 调用）

#### 步骤 1：创建项目目录

```bash
mkdir my-first-workflow
cd my-first-workflow
```

#### 步骤 2：设置您的 API 密钥

创建一个 `.env` 文件来安全存储您的 OpenAI API 密钥：

```bash
# .env
OPENAI_API_KEY=your-api-key
```

> **注意**：永远不要将 `.env` 文件提交到版本控制。将 `.env` 添加到您的 `.gitignore`。

#### 步骤 3：创建您的工作流配置

创建一个 `model-compose.yml` 文件：

```yaml
# model-compose.yml
controller:
  type: http-server
  port: 8080
  base_path: /api
  webui:
    port: 8081

components:
  - id: chatgpt
    type: http-client
    base_url: https://api.openai.com/v1
    action:
      path: /chat/completions
      method: POST
      headers:
        Authorization: Bearer ${env.OPENAI_API_KEY}
        Content-Type: application/json
      body:
        model: gpt-4o
        messages:
          - role: user
            content: ${input.prompt}
      output:
        response: ${response.choices[0].message.content}

workflows:
  - id: generate-text
    default: true
    jobs:
      - id: call-gpt
        component: chatgpt
```

#### 理解配置

让我们分解每个部分的作用：

**控制器**
```yaml
controller:
  type: http-server
  port: 8080
  base_path: /api
  webui:
    port: 8081
```
- 定义工作流如何暴露（作为 HTTP 服务器）
- 设置 API 端口（8080）和 Web UI 端口（8081）
- API 端点的基础路径（`/api`）

**组件**
```yaml
components:
  - id: chatgpt
    type: http-client
    base_url: https://api.openai.com/v1
    action:
      path: /chat/completions
      method: POST
      headers:
        Authorization: Bearer ${env.OPENAI_API_KEY}
      body:
        model: gpt-4o
        messages:
          - role: user
            content: ${input.prompt}
      output:
        response: ${response.choices[0].message.content}
```
- 定义一个名为 `chatgpt` 的可重用组件
- 配置 HTTP 客户端来调用 OpenAI 的 API
- 使用 `${env.OPENAI_API_KEY}` 从环境变量注入 API 密钥
- 将 `${input.prompt}` 传递给请求体
- 将响应提取到 `output.response` 变量中

**工作流**
```yaml
workflows:
  - id: generate-text
    default: true
    jobs:
      - id: call-gpt
        component: chatgpt
```
- 定义一个名为 `generate-text` 的工作流
- 标记为 `default`（未指定工作流名称时运行）
- 包含执行 `chatgpt` 组件的单个作业

---

### 1.3.2 运行工作流（run 命令）

`run` 命令直接从 CLI 执行一次工作流——非常适合测试和脚本编写。

#### 基本用法

```bash
model-compose run generate-text --input '{"prompt": "写一首关于编程的短诗"}'
```

这将：
1. 加载 `model-compose.yml` 配置
2. 执行 `generate-text` 工作流
3. 将输入传递给工作流
4. 将输出打印到控制台

#### 预期输出

```json
{
  "response": "代码如流水，\n月光下虫现，\n调试到日出。"
}
```

#### 传递不同的输入

您可以传递工作流期望的任何 JSON 输入：

```bash
model-compose run generate-text --input '{"prompt": "用一句话解释量子计算"}'
```

#### 使用环境变量

如果需要覆盖环境变量：

```bash
model-compose run generate-text \
  --input '{"prompt": "你好！"}' \
  --env OPENAI_API_KEY=sk-different-key
```

或使用不同的 env 文件：

```bash
model-compose run generate-text \
  --input '{"prompt": "你好！"}' \
  --env-file .env.production
```

#### 运行非默认工作流

如果您有多个工作流并想运行特定的一个：

```bash
model-compose run my-other-workflow --input '{"key": "value"}'
```

---

### 1.3.3 启动控制器并使用 Web UI

`up` 命令启动一个持久服务器，将您的工作流作为 HTTP 端点托管，并可选择提供 Web UI。

#### 启动控制器

```bash
model-compose up
```

您应该看到类似的输出：

```
启动 model-compose 控制器...
✓ 从 model-compose.yml 加载配置
✓ HTTP 服务器运行在 http://localhost:8080
✓ Web UI 可在 http://localhost:8081 访问
✓ 加载了 1 个工作流：generate-text（默认）
```

控制器现在正在运行并准备接受请求。

#### 使用 Web UI

打开浏览器并导航到：

```
http://localhost:8081
```

Web UI 提供了一个交互式界面，您可以：

- 从下拉菜单中**选择工作流**
- 在表单中**输入输入**
- 通过按钮点击**运行工作流**
- 实时**查看输出**
- **查看执行日志**以进行调试

![Web UI 截图](../images/01-001.png)

**运行您的工作流：**
1. 在输入字段中输入您的提示（例如，"写一首关于 AI 的短诗"）
2. 点击"运行工作流"
3. 在输出面板中查看生成的响应

#### 使用 HTTP API

您也可以通过 HTTP 以编程方式触发工作流：

```bash
curl -X POST http://localhost:8080/api/workflows/runs \
  -H "Content-Type: application/json" \
  -d '{
    "workflow_id": "generate-text",
    "input": {
      "prompt": "什么是机器学习？"
    },
    "output_only": true
  }'
```

响应：

```json
{
  "response": "机器学习是人工智能的一个子集..."
}
```

#### 在后台模式下运行

要在后台运行控制器：

```bash
model-compose up -d
```

#### 停止控制器

要优雅地关闭控制器：

```bash
model-compose down
```

这将：
- 停止 HTTP 服务器
- 停止 Web UI
- 清理资源
- 如果需要保存状态

---

## 1.4 基础概念

现在您已经运行了第一个工作流，让我们澄清 model-compose 中的关键概念。

### 控制器

**控制器**是托管和执行工作流的运行时环境。它可以在两种模式下运行：

- **HTTP 服务器**：将工作流作为 REST API 端点暴露，可选 Web UI
- **MCP 服务器**：通过模型上下文协议（JSON-RPC）暴露工作流

控制器在 `model-compose.yml` 的 `controller` 部分配置。

### 组件

**组件**是执行特定任务的可重用构建块。将它们视为可以从工作流调用的函数。

常见的组件类型：
- `http-client`：对外部服务进行 HTTP API 调用
- `model`：运行本地 AI 模型（HuggingFace transformers）
- `shell`：执行 shell 命令
- `text-splitter`：将文本拆分为块
- `workflow`：将另一个工作流作为组件调用

每个组件都有：
- 一个 **id**：唯一标识符，用于在工作流中引用它
- 一个 **type**：它是什么类型的组件
- **配置**：该组件类型的特定设置
- **输入/输出映射**：数据如何流入和流出

### 工作流

**工作流**是定义完整 AI 流水线的命名作业序列。工作流可以：

- 按顺序执行多个步骤
- 使用变量绑定在步骤之间传递数据
- 具有多个分支或并行执行（高级）
- 通过 CLI、HTTP API 或 Web UI 触发

关键工作流属性：
- `id`：工作流的唯一名称
- `default`：此工作流是否默认运行（可选）
- `jobs`：要执行的作业列表
- `title` 和 `description`：Web UI 的人类可读元数据

### 作业

**作业**是工作流中的各个步骤。每个作业：

- 引用要执行的组件
- 可以接受来自先前作业的输入
- 可以为后续作业产生输出
- 按顺序执行（默认）

示例：
```yaml
jobs:
  - id: generate-text
    component: chatgpt
    input:
      prompt: ${input.query}

  - id: translate
    component: translator
    input:
      text: ${generate-text.output.response}
```

### 变量绑定

**变量绑定**是使用 `${...}` 语法让数据在工作流中流动的方式。

常见的变量来源：

- `${env.VAR_NAME}`：环境变量
- `${input.field}`：工作流输入
- `${response.field}`：来自当前组件的 HTTP 响应
- `${jobs.job-id.output.field}`：来自特定作业（job-id）的输出

数据流示例：
```yaml
component:
  action:
    body:
      prompt: ${input.user_prompt}  # 来自工作流输入
      api_key: ${env.API_KEY}       # 来自环境
    output:
      result: ${response.data}      # 从 API 响应中提取
```

### 综合起来

以下是所有内容的连接方式：

1. **定义组件** - 可重用的操作（API 调用、模型等）
2. **创建工作流** - 使用这些组件的作业序列
3. **配置控制器** - 如何暴露和运行工作流
4. **运行** - 通过 CLI（`run`）执行或启动服务器（`up`）
5. **数据流** - 通过作业之间的变量绑定

---

## 下一步

试一试：
- 更改 OpenAI 模型（尝试 `gpt-3.5-turbo` 或 `gpt-4`）
- 尝试不同的提示和输入

---

**下一章**：[2. 核心概念](./02-core-concepts.md)
