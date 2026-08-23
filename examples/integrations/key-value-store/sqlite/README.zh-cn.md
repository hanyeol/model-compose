# SQLite Key-Value Store 示例

本示例演示如何在工作流中使用 model-compose 和 SQLite key-value 存储来存储、检索和管理数据。

## 概述

此工作流提供基本的 key-value 存储操作：

1. **Set**：使用可选的 TTL（生存时间）存储值
2. **Get**：通过键检索存储的值
3. **Delete**：从存储中删除键
4. **Exists**：检查键是否存在

SQLite 驱动将条目持久化到本地数据库文件，因此数据在控制器重启后依然存在。它无需外部服务器，适合作为 Redis 的轻量替代方案 —— 在需要持久化但不需要完整网络访问存储的场景下使用。

## 准备工作

### 先决条件

- model-compose 已安装并在 PATH 中可用

无需外部服务。SQLite 为嵌入式，数据库文件在首次使用时自动创建。

### 环境配置

导航到此示例目录：
```bash
cd examples/integrations/key-value-store/sqlite
```

本示例默认写入 `storage/kv-store.sqlite` 文件（相对于此目录）。控制器启动时会自动创建 `storage/` 目录和数据库文件。

## 运行方法

1. **启动服务：**
   ```bash
   model-compose up
   ```

2. **运行工作流：**

   **存储值：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow_id": "set-value", "input": {"key": "greeting", "value": "Hello, World!", "ttl": 3600}}'
   ```

   **检索值：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow_id": "get-value", "input": {"key": "greeting"}}'
   ```

   **检查键是否存在：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow_id": "check-value", "input": {"key": "greeting"}}'
   ```

   **删除键：**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{"workflow_id": "delete-value", "input": {"key": "greeting"}}'
   ```

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 选择所需的工作流（set、get、delete、exists）
   - 输入参数
   - 点击 "Run Workflow" 按钮

   **使用 CLI：**
   ```bash
   # 使用 TTL 存储值
   model-compose run set-value --input '{"key": "user:1", "value": {"name": "Alice", "role": "admin"}, "ttl": 86400}'

   # 检索值
   model-compose run get-value --input '{"key": "user:1"}'

   # 检查是否存在
   model-compose run check-value --input '{"key": "user:1"}'

   # 删除键
   model-compose run delete-value --input '{"key": "user:1"}'
   ```

## 组件详情

### SQLite Key-Value Store 组件 (kv)
- **类型**：Key-value store 组件
- **用途**：存储和检索键值对
- **驱动**：SQLite（嵌入式）
- **功能**：
  - 基本 CRUD 操作（get、set、delete、exists）
  - 支持 TTL 自动过期
  - 复杂值的 JSON 序列化/反序列化
  - 持久化存储在单个数据库文件中
  - 无需外部服务器

## 工作流详情

### "Set Value" 工作流

**描述**：使用可选的 TTL 在 SQLite 中存储键值对。

#### 输入参数

| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| `key` | string | 是 | - | 要存储的键 |
| `value` | any | 是 | - | 要存储的值（字符串、数字、对象、数组） |
| `ttl` | integer | 否 | null | 生存时间（秒）。null = 不过期 |

#### 输出格式

| 字段 | 类型 | 描述 |
|------|------|------|
| `success` | boolean | 操作是否成功 |

### "Get Value" 工作流

**描述**：通过键从 SQLite 检索值。

#### 输入参数

| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| `key` | string | 是 | - | 要检索的键 |

#### 输出格式

| 字段 | 类型 | 描述 |
|------|------|------|
| `value` | any \| null | 存储的值。如果键不存在则为 null |

### "Delete Value" 工作流

**描述**：从 SQLite 删除键。

#### 输入参数

| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| `key` | string | 是 | - | 要删除的键 |

#### 输出格式

| 字段 | 类型 | 描述 |
|------|------|------|
| `count` | integer | 删除的键数（0 或 1） |

### "Check Exists" 工作流

**描述**：检查 SQLite 中键是否存在。

#### 输入参数

| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| `key` | string | 是 | - | 要检查的键 |

#### 输出格式

| 字段 | 类型 | 描述 |
|------|------|------|
| `exists` | boolean | 键是否存在 |

## 自定义

### 数据库位置

通过设置 `path` 控制 SQLite 文件的位置。相对路径以示例目录为基准解析。使用绝对路径可将数据库放在其他位置，使用 `:memory:` 则创建非持久化的内存数据库。

```yaml
components:
  - id: kv
    type: key-value-store
    driver: sqlite
    path: /var/lib/model-compose/kv-store.sqlite
```

```yaml
components:
  - id: kv
    type: key-value-store
    driver: sqlite
    path: ":memory:"
```

### 表名

默认情况下条目存储在名为 `kv_store` 的表中。如果希望在同一数据库文件中共存多个存储，可通过 `table` 覆盖：

```yaml
components:
  - id: sessions
    type: key-value-store
    driver: sqlite
    path: app.sqlite
    table: sessions

  - id: cache
    type: key-value-store
    driver: sqlite
    path: app.sqlite
    table: cache
```

### 值类型

组件自动处理序列化：
- **字符串**：直接存储
- **对象/数组**：序列化为 JSON，检索时自动反序列化
- **数字/布尔值**：存储时转换为字符串
