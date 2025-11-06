# 3. CLI 使用

本章介绍 model-compose CLI 命令的使用方法。

---

## 3.1 安装

### 使用 pip 安装

```bash
# 从 PyPI 安装(推荐)
pip install model-compose

# 从源代码安装
git clone https://github.com/your-repo/model-compose.git
cd model-compose
pip install -e .

# 安装开发依赖
pip install -e .[dev]
```

### 验证安装

```bash
model-compose --version
```

---

## 3.2 基本命令

### 3.2.1 `up` - 启动控制器

启动 model-compose 控制器并运行工作流。

```bash
# 基本用法(前台运行)
model-compose up

# 后台运行
model-compose up -d

# 指定配置文件
model-compose up -f custom-compose.yml

# 多个配置文件
model-compose up -f base.yml -f override.yml
```

**选项:**
- `-d, --detach`: 后台模式运行
- `-f, --file FILE`: 指定配置文件(默认: `model-compose.yml`)
- `--env-file FILE`: 指定环境变量文件(默认: `.env`)
- `-e, --env KEY=VALUE`: 设置环境变量
- `--verbose`: 详细日志输出

**示例:**

```bash
# 使用环境文件
model-compose up --env-file .env.production

# 设置特定环境变量
model-compose up -e OPENAI_API_KEY=sk-proj-... -e LOG_LEVEL=debug

# 详细模式
model-compose up --verbose
```

### 3.2.2 `down` - 停止控制器

停止正在运行的控制器。

```bash
# 停止控制器
model-compose down

# 指定配置文件
model-compose down -f custom-compose.yml
```

**工作原理:**
1. 创建 `.stop` 文件
2. 控制器检测该文件(每秒轮询一次)
3. 优雅关闭服务
4. 清理资源

### 3.2.3 `run` - 执行单个工作流

运行特定工作流一次(不启动控制器)。

```bash
# 基本用法
model-compose run workflow-id --input '{"key": "value"}'

# 从文件读取输入
model-compose run workflow-id --input @input.json

# 指定配置文件
model-compose run workflow-id -f model-compose.yml --input '{"text": "Hello"}'
```

**选项:**
- `--input JSON`: 工作流输入(JSON 字符串或 `@filename`)
- `-f, --file FILE`: 指定配置文件
- `--env-file FILE`: 指定环境变量文件
- `-e, --env KEY=VALUE`: 设置环境变量

**示例:**

```bash
# 简单文本输入
model-compose run chatbot --input '{"prompt": "Hello, world!"}'

# 从文件读取复杂输入
cat > input.json <<EOF
{
  "prompt": "Explain quantum computing",
  "temperature": 0.7,
  "max_tokens": 500
}
EOF
model-compose run chatbot --input @input.json

# 使用环境变量
model-compose run chatbot \
  -e OPENAI_API_KEY=sk-proj-... \
  --input '{"prompt": "Hello"}'
```

---

## 3.3 配置文件管理

### 3.3.1 默认配置文件

model-compose 按以下顺序查找配置文件:
1. 命令行指定的文件(`-f` 选项)
2. 当前目录中的 `model-compose.yml`
3. 当前目录中的 `model-compose.yaml`

### 3.3.2 合并多个配置文件

```bash
# 基础配置 + 环境特定覆盖
model-compose up -f base.yml -f production.yml
```

**base.yml:**
```yaml
controller:
  type: http-server
  port: 8080

components:
  - id: my-model
    type: model
    model: gpt2
```

**production.yml:**
```yaml
controller:
  runtime: docker  # 覆盖运行时

components:
  - id: my-model
    device: cuda    # 覆盖设备
```

### 3.3.3 配置文件验证

验证配置文件语法:

```bash
# 使用 Python YAML 解析器
python -c "import yaml; yaml.safe_load(open('model-compose.yml'))"

# 或使用 yq(如果已安装)
yq eval model-compose.yml
```

---

## 3.4 环境变量管理

### 3.4.1 `.env` 文件

创建 `.env` 文件存储敏感信息:

```bash
# .env
OPENAI_API_KEY=sk-proj-...
ANTHROPIC_API_KEY=sk-ant-...
MODEL_CACHE_DIR=/path/to/models
LOG_LEVEL=info
```

**重要:** 将 `.env` 添加到 `.gitignore`:

```bash
echo ".env" >> .gitignore
```

### 3.4.2 环境变量优先级

环境变量按以下顺序应用（从高到低）：

1. **命令行 `-e` 选项** - 最高优先级
2. **当前 shell 环境变量** - 中等优先级
3. **`--env-file` 文件**（后面的文件覆盖前面的）- 最低优先级

这意味着：
- Shell 环境变量会覆盖 `.env` 文件中的值
- 命令行 `-e` 参数会覆盖所有其他值
- 这允许在不同部署场景中进行灵活配置

```bash
# 示例:命令行覆盖 .env
model-compose up -e LOG_LEVEL=debug  # 覆盖 .env 中的 LOG_LEVEL
```

### 3.4.3 在配置中使用环境变量

```yaml
components:
  - id: openai-client
    type: http-client
    base_url: https://api.openai.com/v1
    headers:
      Authorization: Bearer ${env.OPENAI_API_KEY}

  - id: local-model
    type: model
    model: ${env.MODEL_NAME | "gpt2"}  # 带默认值
    cache_dir: ${env.MODEL_CACHE_DIR}
```

---

## 3.5 常见工作流

### 3.5.1 本地开发

```bash
# 1. 创建配置文件
cat > model-compose.yml <<EOF
controller:
  type: http-server
  port: 8080
  webui:
    driver: gradio
    port: 8081

workflow:
  title: My Chatbot
  component: openai-chat
  input: \${input}
  output: \${output}

component:
  id: openai-chat
  type: http-client
  endpoint: https://api.openai.com/v1/chat/completions
  headers:
    Authorization: Bearer \${env.OPENAI_API_KEY}
  body:
    model: gpt-4o
    messages:
      - role: user
        content: \${input.prompt}
  output: \${response.choices[0].message.content}
EOF

# 2. 创建 .env 文件
cat > .env <<EOF
OPENAI_API_KEY=sk-proj-...
EOF

# 3. 启动服务
model-compose up

# 4. 访问 Web UI
# 打开 http://localhost:8081
```

### 3.5.2 测试工作流

```bash
# 快速测试不启动服务器
model-compose run default --input '{"prompt": "Hello"}'

# 测试不同输入
model-compose run default --input '{"prompt": "Explain AI"}'
model-compose run default --input '{"prompt": "Write a poem"}'
```

### 3.5.3 生产部署

```bash
# 1. 创建生产配置
cat > production.yml <<EOF
controller:
  type: http-server
  port: 8080
  runtime:
    type: docker
    mem_limit: 4g
    cpus: "2.0"
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8080/health"]
      interval: 30s
EOF

# 2. 使用生产配置启动
model-compose up -f model-compose.yml -f production.yml -d

# 3. 检查状态
docker ps

# 4. 查看日志
docker logs <container-id>

# 5. 停止
model-compose down -f model-compose.yml -f production.yml
```

---

## 3.6 调试技巧

### 3.6.1 启用详细日志

```bash
# 方法 1: 命令行选项
model-compose up --verbose

# 方法 2: 环境变量
LOG_LEVEL=DEBUG model-compose up

# 方法 3: 配置文件
```

**在配置中:**
```yaml
logger:
  type: console
  level: DEBUG
```

### 3.6.2 检查配置加载

```bash
# 打印加载的配置(仅加载,不运行)
model-compose up --dry-run  # (如果实现)

# 或使用 Python
python -c "
import yaml
config = yaml.safe_load(open('model-compose.yml'))
print(yaml.dump(config, default_flow_style=False))
"
```

### 3.6.3 测试组件

创建最小测试配置:

```yaml
# test-component.yml
controller:
  type: http-server
  port: 8080

workflow:
  component: test-comp
  input: ${input}
  output: ${output}

component:
  id: test-comp
  type: shell
  actions:
    - id: default
      command:
        - echo
        - ${input.message}
      output: ${stdout}
```

```bash
# 测试
model-compose run default -f test-component.yml \
  --input '{"message": "Testing..."}'
```

---

## 3.7 故障排除

### 3.7.1 常见错误

**错误: `command not found: model-compose`**

解决方案:
```bash
# 检查安装
pip show model-compose

# 检查 PATH
echo $PATH

# 重新安装
pip install --force-reinstall model-compose
```

**错误: `FileNotFoundError: model-compose.yml`**

解决方案:
```bash
# 检查当前目录
ls -la

# 指定配置文件
model-compose up -f /path/to/model-compose.yml
```

**错误: `Port 8080 already in use`**

解决方案:
```bash
# 查找占用端口的进程
lsof -i :8080

# 或修改端口
model-compose up -e PORT=8081
```

### 3.7.2 获取帮助

```bash
# 显示帮助
model-compose --help

# 命令特定帮助
model-compose up --help
model-compose run --help
model-compose down --help
```

---

## 下一步

现在您已经了解了 CLI 基础知识,让我们深入了解组件配置。

---

**下一章**: [4. 组件配置](./04-component-configuration.md)
