# ArangoDB Graph Store 示例

本示例演示如何使用 model-compose 和 ArangoDB 图存储来构建和查询社交图谱。

## 概述

此工作流提供基于 ArangoDB 的图数据库操作：

1. **Add Person**：向图中插入人物文档
2. **Find Friends**：使用 AQL（ArangoDB 查询语言）查询朋友
3. **Find Connections**：遍历社交图谱发现连接

## 准备工作

### 先决条件

- model-compose 已安装并在 PATH 中可用
- ArangoDB 服务器正在运行（本地或远程）

### ArangoDB 安装

**使用 Docker：**
```bash
docker run -d --name arangodb \
  -p 8529:8529 \
  -e ARANGO_ROOT_PASSWORD=password \
  arangodb
```

**使用 Homebrew（macOS）：**
```bash
brew install arangodb
brew services start arangodb
```

### 环境配置

1. 导航到此示例目录：
   ```bash
   cd examples/graph-store/arangodb
   ```

2. 确保 ArangoDB 在 `localhost:8529` 上运行（默认端口）。

3. 访问 http://localhost:8529 的 ArangoDB Web UI 验证连接。

4. 创建数据库和集合：
   - 创建名为 `social` 的数据库
   - 创建名为 `persons` 的文档集合
   - 创建名为 `friendships` 的边集合
   - 创建名为 `social_graph` 的命名图（边定义：`friendships`，from：`persons`，to：`persons`）

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

   **查找朋友：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow_id": "find-friends", "input": {"name": "Alice"}}'
   ```

   **查找连接：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow_id": "find-connections", "input": {"node_id": "persons/12345"}}'
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

   # 按姓名查找朋友
   model-compose run find-friends --input '{"name": "Alice"}'

   # 查找连接（遍历）
   model-compose run find-connections --input '{"node_id": "persons/12345"}'
   ```

## 组件详情

### ArangoDB Graph Store 组件 (social-graph)
- **类型**：Graph store 组件
- **用途**：存储和查询图结构数据
- **驱动**：ArangoDB
- **功能**：
  - 文档和边 CRUD 操作
  - AQL 查询执行
  - 可配置深度和方向的命名图遍历
  - 通过 URL 或 host/port 连接

## 工作流详情

### "Add Person" 工作流

**描述**：向图中插入人物文档。

#### 输入参数

| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| `name` | string | 是 | - | 人物姓名 |
| `age` | integer | 是 | - | 人物年龄 |

#### 输出格式

| 字段 | 类型 | 描述 |
|------|------|------|
| `ids` | array | 创建的文档 ID 列表 |
| `created_nodes` | integer | 创建的文档数 |
| `created_relationships` | integer | 创建的边数 |

### "Find Friends" 工作流

**描述**：使用 AQL 按姓名查询朋友。

#### 输入参数

| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| `name` | string | 是 | - | 要搜索的人物姓名 |

#### 输出格式

返回包含属性的匹配文档列表。

### "Find Connections" 工作流

**描述**：遍历社交图谱查找 2 跳以内的连接。

#### 输入参数

| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| `node_id` | string | 是 | - | 起始文档 ID（例如 `persons/12345`） |

#### 输出格式

返回包含深度和路径信息的连接文档列表。

## 自定义

### ArangoDB 连接

#### 使用 URL
```yaml
components:
  - id: social-graph
    type: graph-store
    driver: arangodb
    url: http://localhost:8529
    username: root
    password: password
    database: social
```

#### 使用 Host/Port
```yaml
components:
  - id: social-graph
    type: graph-store
    driver: arangodb
    host: arangodb.example.com
    port: 8529
    protocol: https
    username: root
    password: ${env.ARANGO_PASSWORD}
    database: social
```

### ArangoDB 特有功能

- **命名图**：在操作中使用 `graph` 字段利用 ArangoDB 的命名图功能进行遍历
- **集合**：文档操作指定 `collection`，边操作指定 `edge_collection`
- **AQL 查询**：使用带绑定参数的自定义 AQL 查询实现灵活的数据访问
