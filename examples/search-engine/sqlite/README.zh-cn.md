# SQLite Search Engine 示例

本示例演示如何在工作流中使用 model-compose 和 SQLite FTS5 全文搜索引擎来索引、检索和管理文档。

## 概述

此工作流提供基于 SQLite FTS5 的全文搜索操作：

1. **Index**：将文档插入搜索索引
2. **Search**：对已索引的文档执行 BM25 排序的关键字搜索
3. **Delete**：通过 id 从索引中删除文档

## 准备工作

### 先决条件

- model-compose 已安装并在 PATH 中可用
- Python 3.11+（官方构建中内置的 `sqlite3` 模块默认启用 FTS5）

### 环境配置

1. 导航到此示例目录：
   ```bash
   cd examples/search-engine/sqlite
   ```

2. 不需要外部服务。索引以单个 SQLite 数据库文件 `./data/search.db` 的形式存储，在首次执行 `index` 操作时自动创建。

## 运行方法

1. **启动服务：**
   ```bash
   model-compose up
   ```

2. **运行工作流：**

   **索引文档：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow_id": "index-documents", "input": {"documents": [
       {"document_id": "1", "title": "Python tutorial", "content": "Learn Python basics"},
       {"document_id": "2", "title": "JavaScript guide", "content": "Modern JavaScript features"},
       {"document_id": "3", "title": "Rust handbook", "content": "Systems programming in Rust"}
     ]}}'
   ```

   **搜索文档：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow_id": "search-documents", "input": {"query": "Python", "limit": 5}}'
   ```

   **删除文档：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow_id": "delete-documents", "input": {"document_ids": ["1", "3"]}}'
   ```

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 选择所需的工作流（index、search、delete）
   - 输入参数
   - 点击 "Run Workflow" 按钮

   **使用 CLI：**
   ```bash
   # 索引文档
   model-compose run index-documents --input '{"documents": [
     {"document_id": "1", "title": "Python tutorial", "content": "Learn Python basics"},
     {"document_id": "2", "title": "JavaScript guide", "content": "Modern JavaScript features"}
   ]}'

   # 使用字段过滤进行搜索
   model-compose run search-documents --input '{"query": "Modern", "search_fields": ["content"], "limit": 5}'

   # 删除文档
   model-compose run delete-documents --input '{"document_ids": ["1"]}'
   ```

## 组件详情

### SQLite Search Engine 组件（search）
- **类型**：Search-engine 组件
- **目的**：对用户提供的文档进行全文关键字搜索
- **驱动**：SQLite FTS5
- **特性**：
  - 零依赖（使用 Python 内置 `sqlite3` 的 FTS5）
  - 内置 BM25 排序
  - 单个数据库文件中容纳多个索引
  - 声明 `id` 字段时支持 upsert 语义
  - 数据库不存在时 `search` / `delete` 抛出明确的 `FileNotFoundError`（不会静默生成空文件）

## 工作流详情

### "Index Documents" 工作流

**描述**：将一批文档插入 FTS5 索引。首次运行时自动创建数据库文件和索引。

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|-----|------|------|--------|------|
| `documents` | object 数组 | 是 | - | 要索引的文档列表。每个对象的键必须与已声明的字段名匹配 |

#### 输出格式

| 字段 | 类型 | 描述 |
|-----|------|------|
| `indexed` | integer | 本次调用插入的文档数 |
| `total` | integer | 索引中当前的文档总数 |

### "Search Documents" 工作流

**描述**：对索引执行 BM25 排序的关键字搜索。

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|-----|------|------|--------|------|
| `query` | string | 是 | - | FTS5 查询表达式 |
| `search_fields` | string 数组 | 否 | null | 限定匹配的字段。省略时在所有 text 字段中搜索 |
| `limit` | integer | 否 | 10 | 返回的最大命中数 |

#### 输出格式

| 字段 | 类型 | 描述 |
|-----|------|------|
| `hits` | object 数组 | 匹配的文档（按 `score` 降序排列） |
| `count` | integer | 返回的命中数 |

每个命中包含已索引的字段值以及一个 `score` 字段（值越高相关性越强）。

### "Delete Documents" 工作流

**描述**：通过 id 字段值从索引中删除文档。

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|-----|------|------|--------|------|
| `document_ids` | string 数组 | 是 | - | 要删除的文档的 `id` 类型字段值列表 |

#### 输出格式

| 字段 | 类型 | 描述 |
|-----|------|------|
| `deleted` | integer | 已删除的文档数 |

## 自定义

### 存储位置

```yaml
components:
  - id: search
    type: search-engine
    driver: sqlite
    storage_dir: /var/lib/myapp/search
    database: knowledge.db
```

完整数据库路径为 `${storage_dir}/${database}`。多个索引以独立的 FTS5 虚拟表形式共存于同一个文件中。

### 字段类型

| 类型 | 行为 |
|------|------|
| `text` | 经分词后可通过全文 MATCH 搜索 |
| `id` | 用于 upsert 和 delete 的唯一标识符 |
| `keyword` | 标签型值（在 FTS5 中以 text 形式存储） |

```yaml
fields:
  - name: document_id
    type: id
  - name: title
    type: text
  - name: tags
    type: keyword
```

### 单个组件中的多索引

通过为每个操作指定不同的 `index` 参数，单个组件可以提供多个索引。它们共享数据库文件，但分别存储于独立的 FTS5 虚拟表中：

```yaml
actions:
  - id: index-articles
    method: index
    index: articles
    fields:
      - { name: document_id, type: id }
      - { name: body, type: text }
    documents: ${input.documents}

  - id: index-comments
    method: index
    index: comments
    fields:
      - { name: document_id, type: id }
      - { name: body, type: text }
    documents: ${input.documents}
```
