# RAG 助理代理示例

此示例演示了一个使用检索增强生成（RAG）的自主代理，通过在 ChromaDB 向量存储中搜索和添加知识来回答问题。

## 概述

代理通过 ReAct 循环运行：

1. **接收问题**：用户提供问题
2. **搜索知识**：代理在向量存储中搜索相关信息
3. **添加知识**：代理还可以向存储中添加新知识
4. **回答**：检索到相关上下文后，生成有依据的答案

### 可用工具

| 工具 | 描述 |
|------|------|
| `search_knowledge` | 在知识库中搜索相关文档 |
| `add_knowledge` | 向知识库添加新知识 |

## 准备工作

### 前置条件

- 已安装 model-compose 并在您的 PATH 中可用
- OpenAI API 密钥
- ChromaDB（作为依赖自动安装）

### 环境配置

1. 导航到此示例目录：
   ```bash
   cd examples/agents/rag-assistant
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
     -d '{"question": "你知道关于 model-compose 的什么信息？"}'
   ```

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 输入您的问题并点击"运行工作流"按钮

   **使用 CLI：**
   ```bash
   model-compose run --input '{"question": "你知道关于 model-compose 的什么信息？"}'
   ```

## 组件详情

### OpenAI GPT-4o 组件 (gpt-4o)
- **类型**：HTTP 客户端组件
- **用途**：用于代理推理（chat 动作）和文本嵌入（embedding 动作）的 LLM
- **API**：OpenAI Chat Completions + Embeddings API

### 向量存储组件 (vector-store)
- **类型**：Vector store 组件
- **用途**：存储和搜索知识嵌入
- **驱动**：ChromaDB
- **集合**：`knowledge`

### RAG 助理代理组件 (rag-assistant)
- **类型**：Agent 组件
- **用途**：搜索和管理知识的自主 RAG 代理
- **最大迭代次数**：5

## 工作流详情

### 工具：search_knowledge

**描述**：在知识库中搜索相关信息。

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `query` | string | 是 | - | 用于查找相关知识的搜索查询 |

### 工具：add_knowledge

**描述**：向知识库添加新知识。

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `text` | string | 是 | - | 要添加到知识库的文本内容 |
| `source` | string | 否 | `user-input` | 知识的来源或出处 |

## 自定义

- 将 `text-embedding-3-small` 替换为其他嵌入模型
- 将 ChromaDB 切换为 Milvus 或其他向量存储驱动
- 调整 `max_iteration_count` 以控制检索深度
- 添加更多工具（例如网络搜索）将 RAG 与实时数据结合
