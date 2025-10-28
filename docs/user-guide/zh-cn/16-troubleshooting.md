# 16. 故障排除

本章涵盖使用 model-compose 时的常见问题和解决方案。

---

## 16.1 常见问题解答（FAQ）

### 16.1.1 安装和环境设置

**问：Python 版本要求是什么？**

答：model-compose 需要 Python 3.9 或更高版本。建议使用 Python 3.11 或更高版本。

```bash
python --version  # 检查 Python 3.9+
```

**问：安装后找不到 `model-compose` 命令。**

答：检查您的 PATH 环境变量：

```bash
# 如果使用 pip 安装
pip show model-compose

# 以开发模式安装
pip install -e .
```

**问：使用 Docker 运行时无法识别 GPU。**

答：验证是否已安装 NVIDIA Container Toolkit：

```bash
# 检查 Docker 中的 GPU 可用性
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
```

### 16.1.2 组件配置

**问：加载模型组件时出现内存不足错误。**

答：尝试以下方法：

1. **使用量化**：
```yaml
component:
  type: model
  model: meta-llama/Llama-2-7b-hf
  quantization: int8  # 或 int4, nf4
```

2. **减少批次大小**：
```yaml
component:
  batch_size: 1
```

3. **使用 CPU**：
```yaml
component:
  device: cpu
```

**问：HTTP 客户端出现超时错误。**

答：增加超时时间或添加重试设置：

```yaml
component:
  type: http-client
  timeout: 120  # 秒
  max_retries: 5
  retry_delay: 2
```

**问：向量存储连接失败。**

答：验证主机和端口设置：

```yaml
component:
  type: vector-store
  driver: milvus
  host: localhost
  port: 19530
```

检查服务器是否正在运行：
```bash
# Milvus
docker ps | grep milvus

# ChromaDB（独立）
docker ps | grep chroma
```

### 16.1.3 工作流执行

**问：执行工作流时出现"找不到变量"错误。**

答：验证变量绑定语法是否正确：

```yaml
# 错误
output: ${result}  # result 未定义

# 正确
output: ${output}
output: ${jobs.job-id.output}
output: ${input.field}
```

**问：作业依赖关系无法正常工作。**

答：确保在 `depends_on` 中指定了正确的作业 ID：

```yaml
jobs:
  - id: job1
    component: comp1

  - id: job2
    component: comp2
    depends_on: [job1]  # 在 job1 完成后执行
```

**问：流式响应没有输出。**

答：检查以下内容：

1. 在组件中启用流式传输：
```yaml
component:
  type: http-client
  stream_format: json
```

2. 在工作流输出中使用流式引用：
```yaml
workflow:
  output: ${result[]}  # 按块输出
```

3. 在控制器中指定响应格式：
```yaml
workflow:
  output: ${output as text;sse-text}
```

### 16.1.4 Web UI

**问：Gradio Web UI 无法启动。**

答：验证是否已安装 Gradio：

```bash
pip install gradio
```

检查端口冲突：
```bash
lsof -i :8081  # 默认 Web UI 端口
```

**问：Web UI 中的文件上传功能无法使用。**

答：确保正确指定了输入类型：

```yaml
workflow:
  input:
    image: ${input.image as image}
    document: ${input.doc as file}
```

### 16.1.5 监听器和网关

**问：监听器无法从外部访问。**

答：配置网关：

```yaml
gateway:
  type: ngrok
  port: 8080
  authtoken: ${env.NGROK_AUTHTOKEN}
```

**问：ngrok 网关连接失败。**

答：验证是否已配置认证令牌：

```bash
echo $NGROK_AUTHTOKEN
```

检查是否已安装 ngrok：
```bash
ngrok version
```

---

## 16.2 常见错误和解决方案

### 16.2.1 模型加载错误

**错误**：`RuntimeError: CUDA out of memory`

**原因**：GPU 内存不足

**解决方案**：
1. 使用较小的模型
2. 应用量化（`quantization: int8` 或 `int4`、`nf4`）
3. 减少批次大小
4. 使用 CPU（`device: cpu`）

```yaml
component:
  type: model
  model: smaller-model
  device: cuda
  quantization: int8
  batch_size: 1
```

---

**错误**：`OSError: Can't load tokenizer for 'model-name'`

**原因**：模型或分词器下载失败

**解决方案**：
1. 检查互联网连接
2. 设置 HuggingFace 令牌（对于私有模型）：
```bash
export HF_TOKEN=your_token_here
```
3. 检查缓存目录：
```bash
ls ~/.cache/huggingface/hub/
```

---

### 16.2.2 网络错误

**错误**：`ConnectionError: Failed to connect to API`

**原因**：无法连接到 API 端点

**解决方案**：
1. 验证端点 URL
2. 检查 API 密钥
3. 验证网络连接
4. 增加超时时间

```yaml
component:
  type: http-client
  endpoint: https://api.openai.com/v1/chat/completions
  headers:
    Authorization: Bearer ${env.OPENAI_API_KEY}
  timeout: 60
```

---

**错误**：`SSLError: certificate verify failed`

**原因**：SSL 证书验证失败

**解决方案**：
1. 更新证书：
```bash
pip install --upgrade certifi
```
2. 或禁用验证（不推荐）：
```yaml
component:
  type: http-client
  verify_ssl: false
```

---

### 16.2.3 配置文件错误

**错误**：`ValidationError: Invalid configuration`

**原因**：YAML 语法错误或缺少必填字段

**解决方案**：
1. 检查 YAML 语法：
```bash
python -c "import yaml; yaml.safe_load(open('model-compose.yml'))"
```
2. 使用架构参考验证必填字段（第 17 章）
3. 检查缩进（使用 2 个空格）

---

**错误**：`KeyError: 'component-id'`

**原因**：引用的组件 ID 不存在

**解决方案**：
验证组件 ID 已定义：

```yaml
components:
  - id: my-component  # 使用此 ID
    type: model

workflow:
  component: my-component  # 引用相同的 ID
```

---

### 16.2.4 变量绑定错误

**错误**：`ValueError: Cannot resolve variable '${input.field}'`

**原因**：变量路径不正确或数据缺失

**解决方案**：
1. 检查变量路径
2. 添加默认值：
```yaml
output: ${input.field | "default-value"}
```
3. 输出整个对象进行调试：
```yaml
output: ${input}  # 检查整个输入
```

---

**错误**：`TypeError: Object of type 'bytes' is not JSON serializable`

**原因**：尝试将二进制数据序列化为 JSON

**解决方案**：
使用 Base64 编码：
```yaml
output: ${binary_data as base64}
```

---

### 16.2.5 Docker 运行时错误

**错误**：`docker.errors.ImageNotFound`

**原因**：找不到 Docker 镜像

**解决方案**：
1. 拉取镜像：
```bash
docker pull python:3.11
```
2. 或使用自定义构建：
```yaml
controller:
  runtime:
    type: docker
    build:
      context: .
      dockerfile: Dockerfile
```

---

**错误**：`PermissionError: [Errno 13] Permission denied`

**原因**：Docker 套接字权限不足

**解决方案**：
```bash
# 将当前用户添加到 docker 组
sudo usermod -aG docker $USER
newgrp docker
```

---

## 16.3 调试技巧

### 16.3.1 启用日志记录

将日志记录器级别设置为 DEBUG 以获取详细日志：

```yaml
logger:
  type: console
  level: DEBUG
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

或使用环境变量：
```bash
export LOG_LEVEL=DEBUG
model-compose up
```

### 16.3.2 检查变量值

在工作流期间添加临时输出以检查变量值：

```yaml
jobs:
  - id: debug-job
    component: shell-component

components:
  - id: shell-component
    type: shell
    actions:
      - id: default
        command:
          - echo
          - "Input: ${input}"
```

### 16.3.3 逐步执行

通过将复杂工作流分解为步骤来测试：

```yaml
# 步骤 1：仅测试第一个作业
workflow:
  jobs:
    - id: step1
      component: comp1

# 步骤 2：添加第二个作业
workflow:
  jobs:
    - id: step1
      component: comp1
    - id: step2
      component: comp2
      depends_on: [step1]
```

### 16.3.4 检查 API 响应

验证 HTTP 客户端响应：

```yaml
component:
  type: http-client
  endpoint: https://api.example.com/v1/resource
  output: ${response}  # 输出整个响应
```

### 16.3.5 Docker 容器日志

使用 Docker 运行时时检查容器日志：

```bash
# 检查正在运行的容器
docker ps

# 查看日志
docker logs <container-id>

# 实时跟踪日志
docker logs -f <container-id>
```

### 16.3.6 验证环境变量

检查环境变量是否正确设置：

```bash
# 使用 .env 文件
cat .env

# 打印环境变量
env | grep OPENAI
```

在工作流中测试环境变量：

```yaml
workflow:
  component: shell-env-test

component:
  id: shell-env-test
  type: shell
  actions:
    - id: default
      command:
        - echo
        - ${env.OPENAI_API_KEY}
```

### 16.3.7 检查端口冲突

检查端口是否已被使用：

```bash
# Linux/Mac
lsof -i :8080

# Windows
netstat -ano | findstr :8080
```

使用不同的端口：
```yaml
controller:
  port: 8081  # 更改为不同的端口
```

### 16.3.8 验证依赖项

检查是否已安装所需的 Python 包：

```bash
pip list | grep transformers
pip list | grep torch
pip list | grep gradio
```

安装缺少的包：
```bash
pip install transformers torch gradio
```

---

## 下一步

如果问题仍然存在：
- 在 [GitHub Issues](https://github.com/your-repo/model-compose/issues) 中搜索类似问题
- 创建新问题时，请包含：
  - model-compose 版本
  - Python 版本
  - 操作系统
  - 完整的错误消息
  - 最小可重现的配置文件
- 在社区论坛寻求帮助

---

**下一章**：[17. 附录](./17-appendix.md)
