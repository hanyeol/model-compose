# In-Memory Key-Value Store 示例

本示例演示如何在工作流中使用 model-compose 和内存 key-value 存储来存储、检索和管理数据。

## 概述

此工作流提供基本的 key-value 存储操作：

1. **Set**：使用可选的 TTL（生存时间）存储值
2. **Get**：通过键检索存储的值
3. **Delete**：从存储中删除键
4. **Exists**：检查键是否存在

内存驱动将所有条目保存在控制器进程内。数据**不会持久化** —— 控制器停止时所有数据都会丢失。因此它非常适合本地开发、测试、缓存短期数据，或不希望依赖外部服务的示例。

## 准备工作

### 先决条件

- model-compose 已安装并在 PATH 中可用

无需外部服务或额外依赖。

### 环境配置

导航到此示例目录：
```bash
cd examples/integrations/key-value-store/memory
```

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

### In-Memory Key-Value Store 组件 (kv)
- **类型**：Key-value store 组件
- **用途**：存储和检索键值对
- **驱动**：Memory（进程内）
- **功能**：
  - 基本 CRUD 操作（get、set、delete、exists）
  - 支持 TTL 自动过期
  - 支持任何可 JSON 序列化的值
  - 无外部依赖

> **注意**：数据仅在控制器进程存活期间存在。重启 `model-compose` 将清除所有条目。

## 工作流详情

### "Set Value" 工作流

**描述**：使用可选的 TTL 在内存中存储键值对。

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

**描述**：通过键从内存检索值。

#### 输入参数

| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| `key` | string | 是 | - | 要检索的键 |

#### 输出格式

| 字段 | 类型 | 描述 |
|------|------|------|
| `value` | any \| null | 存储的值。如果键不存在则为 null |

### "Delete Value" 工作流

**描述**：从内存删除键。

#### 输入参数

| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| `key` | string | 是 | - | 要删除的键 |

#### 输出格式

| 字段 | 类型 | 描述 |
|------|------|------|
| `count` | integer | 删除的键数（0 或 1） |

### "Check Exists" 工作流

**描述**：检查内存中键是否存在。

#### 输入参数

| 参数 | 类型 | 必填 | 默认值 | 描述 |
|------|------|------|--------|------|
| `key` | string | 是 | - | 要检查的键 |

#### 输出格式

| 字段 | 类型 | 描述 |
|------|------|------|
| `exists` | boolean | 键是否存在 |

## 自定义

### 切换驱动

内存驱动除声明外无需其他配置：

```yaml
components:
  - id: kv
    type: key-value-store
    driver: memory
```

如果需要在重启后保留数据，可切换到 `sqlite` 或 `redis` 驱动 —— 动作定义和工作流输入保持不变。请参考 `examples/integrations/key-value-store/` 下的相邻示例。

### 值类型

组件接受任何可 JSON 序列化的值：字符串、数字、布尔值、对象和数组。返回时保持存储时的形状。
