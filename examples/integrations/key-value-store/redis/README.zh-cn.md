# Redis Key-Value Store 示例

本示例演示如何在工作流中使用 model-compose 和 Redis key-value 存储来存储、检索和管理数据。

## 概述

此工作流提供基本的 key-value 存储操作：

1. **Set**：使用可选的 TTL（生存时间）存储值
2. **Get**：通过键检索存储的值
3. **Delete**：从存储中删除键
4. **Exists**：检查键是否存在

## 准备工作

### 先决条件

- model-compose 已安装并在 PATH 中可用
- Redis 服务器正在运行（本地或远程）

### Redis 安装

**使用 Docker：**
```bash
docker run -d --name redis -p 6379:6379 redis
```

**使用 Homebrew（macOS）：**
```bash
brew install redis
brew services start redis
```

### 环境配置

1. 导航到此示例目录：
   ```bash
   cd examples/key-value-store/redis
   ```

2. 确保 Redis 在 `localhost:6379` 上运行（默认配置）。

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

### Redis Key-Value Store 组件 (kv)
- **类型**：Key-value store 组件
- **用途**：存储和检索键值对
- **驱动**：Redis
- **功能**：
  - 基本 CRUD 操作（get、set、delete、exists）
  - 支持 TTL 自动过期
  - 复杂值的 JSON 序列化/反序列化
  - 通过 host/port 或 URL 连接

## 工作流详情

### "Set Value" 工作流

**描述**：使用可选的 TTL 在 Redis 中存储键值对。

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

**描述**：通过键从 Redis 检索值。

#### 输入参数

| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| `key` | string | 是 | - | 要检索的键 |

#### 输出格式

| 字段 | 类型 | 描述 |
|------|------|------|
| `value` | any \| null | 存储的值。如果键不存在则为 null |

### "Delete Value" 工作流

**描述**：从 Redis 删除键。

#### 输入参数

| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| `key` | string | 是 | - | 要删除的键 |

#### 输出格式

| 字段 | 类型 | 描述 |
|------|------|------|
| `count` | integer | 删除的键数（0 或 1） |

### "Check Exists" 工作流

**描述**：检查 Redis 中键是否存在。

#### 输入参数

| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| `key` | string | 是 | - | 要检查的键 |

#### 输出格式

| 字段 | 类型 | 描述 |
|------|------|------|
| `exists` | boolean | 键是否存在 |

## 自定义

### Redis 连接

#### 使用 URL
```yaml
components:
  - id: kv
    type: key-value-store
    driver: redis
    url: redis://localhost:6379/0
```

#### 需要认证的远程 Redis
```yaml
components:
  - id: kv
    type: key-value-store
    driver: redis
    host: redis.example.com
    port: 6379
    password: ${env.REDIS_PASSWORD}
    database: 1
    secure: true
```

### 值类型

组件自动处理序列化：
- **字符串**：直接存储
- **对象/数组**：序列化为 JSON，检索时自动反序列化
- **数字/布尔值**：存储时转换为字符串
