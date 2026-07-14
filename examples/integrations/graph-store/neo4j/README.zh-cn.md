# Neo4j Graph Store 示例

本示例演示如何使用 model-compose 和 Neo4j 图存储来构建和查询知识图谱。

## 概述

此工作流提供基于 Neo4j 的图数据库操作：

1. **Add Person**：向知识图谱插入人物节点
2. **Add Friendship**：在两个人之间创建 KNOWS 关系
3. **Find Person**：使用 Cypher 按姓名查询人物
4. **Find Connections**：遍历图谱发现连接的人物

## 准备工作

### 先决条件

- model-compose 已安装并在 PATH 中可用
- Neo4j 服务器正在运行（本地或远程）

### Neo4j 安装

**使用 Docker：**
```bash
docker run -d --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j
```

**使用 Homebrew（macOS）：**
```bash
brew install neo4j
neo4j start
```

### 环境配置

1. 导航到此示例目录：
   ```bash
   cd examples/graph-store/neo4j
   ```

2. 确保 Neo4j 在 `localhost:7687` 上运行（默认 Bolt 端口）。

3. 访问 http://localhost:7474 的 Neo4j Browser 验证连接。

## 运行方法

1. **启动服务：**
   ```bash
   model-compose up
   ```

2. **运行工作流：**

   **添加人物：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow_id": "add-person", "input": {"name": "Alice", "age": 30}}'
   ```

   **添加友谊关系：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow_id": "add-friendship", "input": {"from_id": "<node_id_1>", "to_id": "<node_id_2>", "since": "2024-01-01"}}'
   ```

   **查找人物：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow_id": "find-person", "input": {"name": "Alice"}}'
   ```

   **查找连接：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow_id": "find-connections", "input": {"node_id": "<node_id>"}}'
   ```

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 选择所需的工作流
   - 输入参数
   - 点击 "Run Workflow" 按钮

   **使用 CLI：**
   ```bash
   # 添加人物
   model-compose run add-person --input '{"name": "Alice", "age": 30}'

   # 查找人物
   model-compose run find-person --input '{"name": "Alice"}'

   # 查找连接（遍历）
   model-compose run find-connections --input '{"node_id": "<node_id>"}'
   ```

## 组件详情

### Neo4j Graph Store 组件 (knowledge-graph)
- **类型**：Graph store 组件
- **用途**：存储和查询图结构数据
- **驱动**：Neo4j
- **功能**：
  - 节点和关系 CRUD 操作
  - Cypher 查询执行
  - 可配置深度和方向的图遍历
  - 通过 URL 或 host/port 连接

## 工作流详情

### "Add Person" 工作流

**描述**：向知识图谱插入人物节点。

#### 输入参数

| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| `name` | string | 是 | - | 人物姓名 |
| `age` | integer | 是 | - | 人物年龄 |

#### 输出格式

| 字段 | 类型 | 描述 |
|------|------|------|
| `ids` | array | 创建的节点元素 ID 列表 |
| `created_nodes` | integer | 创建的节点数 |
| `created_relationships` | integer | 创建的关系数 |

### "Add Friendship" 工作流

**描述**：在两个人之间创建 KNOWS 关系。

#### 输入参数

| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| `from_id` | string | 是 | - | 源节点元素 ID |
| `to_id` | string | 是 | - | 目标节点元素 ID |
| `since` | string | 是 | - | 友谊开始日期 |

#### 输出格式

| 字段 | 类型 | 描述 |
|------|------|------|
| `ids` | array | 创建的关系元素 ID 列表 |
| `created_nodes` | integer | 创建的节点数 |
| `created_relationships` | integer | 创建的关系数 |

### "Find Person" 工作流

**描述**：使用 Cypher 查询按姓名查找人物。

#### 输入参数

| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| `name` | string | 是 | - | 要搜索的人物姓名 |

#### 输出格式

返回包含节点属性的匹配记录列表。

### "Find Connections" 工作流

**描述**：遍历图谱查找 2 跳以内的连接人物。

#### 输入参数

| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| `node_id` | string | 是 | - | 起始节点元素 ID |

#### 输出格式

返回包含深度和关系类型信息的连接节点列表。

## 自定义

### Neo4j 连接

#### 使用 URL
```yaml
components:
  - id: knowledge-graph
    type: graph-store
    driver: neo4j
    url: bolt://localhost:7687
```

#### 使用 Host/Port
```yaml
components:
  - id: knowledge-graph
    type: graph-store
    driver: neo4j
    host: neo4j.example.com
    port: 7687
    protocol: neo4j+s
    username: neo4j
    password: ${env.NEO4J_PASSWORD}
```

### 支持的协议

| 协议 | 描述 |
|------|------|
| `bolt` | 未加密 Bolt 连接 |
| `bolt+s` | TLS Bolt 连接（验证证书） |
| `bolt+ssc` | TLS Bolt 连接（自签名证书） |
| `neo4j` | Neo4j 协议（支持路由） |
| `neo4j+s` | TLS Neo4j 协议（验证证书） |
| `neo4j+ssc` | TLS Neo4j 协议（自签名证书） |
