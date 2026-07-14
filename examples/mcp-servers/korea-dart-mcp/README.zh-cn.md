# Korea DART MCP 服务器示例

此示例演示了如何创建一个 MCP 服务器，用于查询由韩国金融监督院运营的 [DART（Data Analysis, Retrieval and Transfer System，电子公示系统）](https://opendart.fss.or.kr) 中的韩国财务公示数据。

灵感来自 [dart-mcp](https://github.com/2geonhyup/dart-mcp)。

## 概述

此 MCP 服务器为韩国上市公司（KOSPI/KOSDAQ）提供财务数据工作流：

1. **公示搜索**：搜索近期定期公示并提取关键财务指标
2. **财务报表**：获取结构化财务数据（资产负债表、损益表、现金流量表）
3. **公司概况**：获取基本公司信息（股票代码、CEO、行业等）
4. **公司代码查询**：通过公司名称查询 DART 公司代码 (corp_code)
5. **股息信息**：获取每股股息、股息收益率和派息率
6. **主要股东**：获取主要股东及持股信息

## 准备工作

### 前置条件

- 已安装 model-compose 并在您的 PATH 中可用
- DART Open API 密钥

### 获取 DART API 密钥

1. 访问 [DART Open API](https://opendart.fss.or.kr)
2. 注册账户
3. 申请 API 认证密钥
4. 密钥将被签发（免费）

### 环境配置

1. 导航到此示例目录：
   ```bash
   cd examples/mcp-servers/korea-dart-mcp
   ```

2. 复制示例环境文件：
   ```bash
   cp .env.sample .env
   ```

3. 编辑 `.env` 并添加您的 DART API 密钥：
   ```env
   DART_API_KEY=your-actual-dart-api-key
   ```

## 运行方式

1. **启动服务：**
   ```bash
   model-compose up
   ```

2. **运行工作流：**

   **使用 MCP 客户端：**
   - 连接到 MCP 服务器：http://localhost:8080/mcp
   - 可用工作流：search-disclosure、get-financial-statements、get-company-overview、get-company-code、get-dividend-info、get-major-shareholders
   - 使用兼容 MCP 的客户端执行工作流

   **使用 Web UI：**
   - 打开 Web UI：http://localhost:8081
   - 选择所需的工作流
   - 输入必需参数
   - 点击"运行"按钮

   **使用 CLI：**
   ```bash
   # 通过公司名称查询 corp_code
   model-compose run get-company-code --input '{"corp_name": "삼성전자"}'

   # 搜索某公司的公示
   model-compose run search-disclosure --input '{
     "corp_code": "00126380",
     "bgn_de": "20240101",
     "end_de": "20241231"
   }'

   # 获取年度财务报表（合并）
   model-compose run get-financial-statements --input '{
     "corp_code": "00126380",
     "bsns_year": "2024",
     "reprt_code": "11011",
     "fs_div": "CFS"
   }'

   # 获取公司概况
   model-compose run get-company-overview --input '{"corp_code": "00126380"}'

   # 获取股息信息
   model-compose run get-dividend-info --input '{
     "corp_code": "00126380",
     "bsns_year": "2024"
   }'

   # 获取主要股东
   model-compose run get-major-shareholders --input '{
     "corp_code": "00126380",
     "bsns_year": "2024"
   }'
   ```

## 组件详情

### 公司代码查询 (Shell 组件)
- **ID**：`corp-code-lookup`
- **类型**：Shell 组件（Python 脚本）
- **用途**：下载 DART 公司代码 ZIP/XML 文件，解析并按公司名称搜索
- **认证**：使用 `DART_API_KEY` 环境变量

### DART Open API HTTP 客户端组件
- **ID**：`dart-api`
- **类型**：具有多个 action 的 HTTP 客户端组件
- **用途**：DART Open API 集成
- **Base URL**：`https://opendart.fss.or.kr/api`
- **认证**：API 密钥通过查询参数传递
- **Actions**：
  - **search-disclosure**：搜索定期公示文件
  - **get-financial-statements**：获取完整财务报表数据
  - **get-company-overview**：获取公司基本信息
  - **get-dividend-info**：获取股息数据
  - **get-major-shareholders**：获取主要股东信息

## 工作流详情

### "Search DART Disclosure" 工作流

**描述**：搜索某韩国上市公司的近期定期公示

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `corp_code` | text | 是 | - | DART 公司代码（8 位数字） |
| `bgn_de` | text | 是 | - | 搜索开始日期（YYYYMMDD） |
| `end_de` | text | 是 | - | 搜索结束日期（YYYYMMDD） |
| `last_reprt_at` | text | 否 | `Y` | 仅返回最新报告（Y/N） |
| `pblntf_ty` | text | 否 | `A` | 公示类型（A=年度、B=半年、C=季度） |

### "Get Financial Statements" 工作流

**描述**：按年度和报告类型获取结构化财务数据

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `corp_code` | text | 是 | - | DART 公司代码（8 位数字） |
| `bsns_year` | text | 是 | - | 会计年度（YYYY） |
| `reprt_code` | text | 否 | `11011` | 报告代码（11011=年报、11012=半年报、11013=Q1、11014=Q3） |
| `fs_div` | text | 否 | `CFS` | 财务报表类型（CFS=合并、OFS=单独） |

### "Get Company Overview" 工作流

**描述**：获取公司基本信息

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `corp_code` | text | 是 | - | DART 公司代码（8 位数字） |

### "Get Company Code" 工作流

**描述**：通过公司名称搜索 DART 公司代码（下载并解析完整的 DART 公司代码 ZIP/XML）

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `corp_name` | text | 是 | - | 要搜索的公司名称（韩文或英文） |

### "Get Dividend Information" 工作流

**描述**：获取某上市公司的股息数据

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `corp_code` | text | 是 | - | DART 公司代码（8 位数字） |
| `bsns_year` | text | 是 | - | 会计年度（YYYY） |
| `reprt_code` | text | 否 | `11011` | 报告代码 |

### "Get Major Shareholders" 工作流

**描述**：获取主要股东信息

#### 输入参数

| 参数 | 类型 | 必需 | 默认值 | 描述 |
|------|------|------|--------|------|
| `corp_code` | text | 是 | - | DART 公司代码（8 位数字） |
| `bsns_year` | text | 是 | - | 会计年度（YYYY） |
| `reprt_code` | text | 否 | `11011` | 报告代码 |

## MCP 服务器集成

### 连接详情
- **传输方式**：HTTP
- **端点**：`http://localhost:8080/mcp`
- **协议**：Model Context Protocol v1.0

### 可用工具
AI 代理可以将这些工作流作为工具调用：
- `search-disclosure`：搜索公示文件
- `get-financial-statements`：获取财务报表
- `get-company-overview`：获取公司信息
- `get-company-code`：通过公司名称查找公司代码
- `get-dividend-info`：获取股息数据
- `get-major-shareholders`：获取股东信息

## DART Open API 参考

### 使用的端点

1. **list.json** - 搜索公示文件
   - 文档：https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019001

2. **fnlttSinglAcntAll.json** - 完整财务报表（单一账户）
   - 文档：https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS003&apiId=2019020

3. **company.json** - 公司概况
   - 文档：https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019002

4. **corpCode.xml** - 公司代码查询
   - 文档：https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS001&apiId=2019018

5. **alotMatter.json** - 股息信息
   - 文档：https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS004&apiId=2019006

6. **hyslrSttus.json** - 主要股东持股
   - 文档：https://opendart.fss.or.kr/guide/detail.do?apiGrpCd=DS004&apiId=2019004

## 错误处理

### 常见 API 错误

| 状态 | 消息 | 解决方法 |
|------|------|----------|
| `010` | 未注册的 API 密钥 | 检查您的 `DART_API_KEY` |
| `011` | 超出使用限制 | 等待后重试（每日限额） |
| `012` | 未找到数据 | 验证 corp_code 和日期范围 |
| `013` | 未公示的数据 | 该期间的数据尚未公开 |
| `020` | 无效参数 | 检查参数格式和值 |
| `100` | 字段限制超出 | 缩小请求范围 |
| `800` | IP 不被允许 | 在 DART 设置中注册您的 IP |
| `900` | 未指定的错误 | 联系 DART 支持 |

## 故障排查

### 常见问题

1. **未返回任何结果**：验证 `corp_code` 是否正确（先使用 `get-company-code`）
2. **认证错误**：确保 `.env` 中的 `DART_API_KEY` 设置正确
3. **财务数据为空**：该公司可能未在请求的期间提交报告
4. **get-company-code 速度慢**：公司代码 API 每次调用都会下载约 3MB 的 ZIP 文件，这是预期行为
