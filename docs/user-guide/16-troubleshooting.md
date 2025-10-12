# 16. Troubleshooting

This chapter covers common issues and solutions when using model-compose.

---

## 16.1 Frequently Asked Questions (FAQ)

### 16.1.1 Installation and Environment Setup

**Q: What are the Python version requirements?**

A: model-compose requires Python 3.9 or higher. Python 3.11 or higher is recommended.

```bash
python --version  # Check for Python 3.9+
```

**Q: I can't find the `model-compose` command after installation.**

A: Check your PATH environment variable:

```bash
# If installed with pip
pip show model-compose

# Install in development mode
pip install -e .
```

**Q: GPU is not recognized when using Docker runtime.**

A: Verify that NVIDIA Container Toolkit is installed:

```bash
# Check GPU availability in Docker
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
```

### 16.1.2 Component Configuration

**Q: I get out-of-memory errors when loading model components.**

A: Try these approaches:

1. **Use quantization**:
```yaml
component:
  type: model
  model: meta-llama/Llama-2-7b-hf
  quantization: int8  # or int4, nf4
```

2. **Reduce batch size**:
```yaml
component:
  batch_size: 1
```

3. **Use CPU**:
```yaml
component:
  device: cpu
```

**Q: I'm getting timeout errors with HTTP client.**

A: Increase timeout or add retry settings:

```yaml
component:
  type: http-client
  timeout: 120  # seconds
  max_retries: 5
  retry_delay: 2
```

**Q: Vector store connection fails.**

A: Verify host and port settings:

```yaml
component:
  type: vector-store
  driver: milvus
  host: localhost
  port: 19530
```

Check if the server is running:
```bash
# Milvus
docker ps | grep milvus

# ChromaDB (standalone)
docker ps | grep chroma
```

### 16.1.3 Workflow Execution

**Q: I get "variable not found" errors when executing workflows.**

A: Verify your variable binding syntax is correct:

```yaml
# Incorrect
output: ${result}  # result is not defined

# Correct
output: ${output}
output: ${jobs.job-id.output}
output: ${input.field}
```

**Q: Job dependencies don't work properly.**

A: Ensure you specify the correct job ID in `depends_on`:

```yaml
jobs:
  - id: job1
    component: comp1

  - id: job2
    component: comp2
    depends_on: [job1]  # Executes after job1 completes
```

**Q: Streaming responses are not outputting.**

A: Check the following:

1. Enable streaming in component:
```yaml
component:
  type: http-client
  stream_format: json
```

2. Use streaming reference in workflow output:
```yaml
workflow:
  output: ${result[]}  # Per-chunk output
```

3. Specify response format in controller:
```yaml
workflow:
  output: ${output as text;sse-text}
```

### 16.1.4 Web UI

**Q: Gradio Web UI doesn't start.**

A: Verify Gradio is installed:

```bash
pip install gradio
```

Check for port conflicts:
```bash
lsof -i :8081  # Default Web UI port
```

**Q: File uploads don't work in Web UI.**

A: Ensure input types are correctly specified:

```yaml
workflow:
  input:
    image: ${input.image as image}
    document: ${input.doc as file}
```

### 16.1.5 Listeners and Gateways

**Q: Listener is not accessible from external sources.**

A: Configure a gateway:

```yaml
gateway:
  type: ngrok
  port: 8080
  authtoken: ${env.NGROK_AUTHTOKEN}
```

**Q: ngrok gateway connection fails.**

A: Verify auth token is configured:

```bash
echo $NGROK_AUTHTOKEN
```

Check if ngrok is installed:
```bash
ngrok version
```

---

## 16.2 Common Errors and Solutions

### 16.2.1 Model Loading Errors

**Error**: `RuntimeError: CUDA out of memory`

**Cause**: Insufficient GPU memory

**Solution**:
1. Use a smaller model
2. Apply quantization (`quantization: int8` or `int4`, `nf4`)
3. Reduce batch size
4. Use CPU (`device: cpu`)

```yaml
component:
  type: model
  model: smaller-model
  device: cuda
  quantization: int8
  batch_size: 1
```

---

**Error**: `OSError: Can't load tokenizer for 'model-name'`

**Cause**: Model or tokenizer download failed

**Solution**:
1. Check internet connection
2. Set HuggingFace token (for private models):
```bash
export HF_TOKEN=your_token_here
```
3. Check cache directory:
```bash
ls ~/.cache/huggingface/hub/
```

---

### 16.2.2 Network Errors

**Error**: `ConnectionError: Failed to connect to API`

**Cause**: Failed to connect to API endpoint

**Solution**:
1. Verify endpoint URL
2. Check API key
3. Verify network connection
4. Increase timeout

```yaml
component:
  type: http-client
  endpoint: https://api.openai.com/v1/chat/completions
  headers:
    Authorization: Bearer ${env.OPENAI_API_KEY}
  timeout: 60
```

---

**Error**: `SSLError: certificate verify failed`

**Cause**: SSL certificate verification failed

**Solution**:
1. Update certificates:
```bash
pip install --upgrade certifi
```
2. Or disable verification (not recommended):
```yaml
component:
  type: http-client
  verify_ssl: false
```

---

### 16.2.3 Configuration File Errors

**Error**: `ValidationError: Invalid configuration`

**Cause**: YAML syntax error or missing required fields

**Solution**:
1. Check YAML syntax:
```bash
python -c "import yaml; yaml.safe_load(open('model-compose.yml'))"
```
2. Verify required fields using schema reference (Chapter 17)
3. Check indentation (use 2 spaces)

---

**Error**: `KeyError: 'component-id'`

**Cause**: Referenced component ID does not exist

**Solution**:
Verify component ID is defined:

```yaml
components:
  - id: my-component  # Use this ID
    type: model

workflow:
  component: my-component  # Reference same ID
```

---

### 16.2.4 Variable Binding Errors

**Error**: `ValueError: Cannot resolve variable '${input.field}'`

**Cause**: Variable path is incorrect or data is missing

**Solution**:
1. Check variable path
2. Add default value:
```yaml
output: ${input.field | "default-value"}
```
3. Output entire object for debugging:
```yaml
output: ${input}  # Check entire input
```

---

**Error**: `TypeError: Object of type 'bytes' is not JSON serializable`

**Cause**: Attempting to serialize binary data as JSON

**Solution**:
Use Base64 encoding:
```yaml
output: ${binary_data as base64}
```

---

### 16.2.5 Docker Runtime Errors

**Error**: `docker.errors.ImageNotFound`

**Cause**: Docker image not found

**Solution**:
1. Pull image:
```bash
docker pull python:3.11
```
2. Or use custom build:
```yaml
controller:
  runtime:
    type: docker
    build:
      context: .
      dockerfile: Dockerfile
```

---

**Error**: `PermissionError: [Errno 13] Permission denied`

**Cause**: Insufficient permissions for Docker socket

**Solution**:
```bash
# Add current user to docker group
sudo usermod -aG docker $USER
newgrp docker
```

---

## 16.3 Debugging Tips

### 16.3.1 Enable Logging

Set logger level to DEBUG for detailed logs:

```yaml
logger:
  type: console
  level: DEBUG
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

Or use environment variable:
```bash
export LOG_LEVEL=DEBUG
model-compose up
```

### 16.3.2 Check Variable Values

Add temporary output to check variable values during workflow:

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

### 16.3.3 Step-by-Step Execution

Test complex workflows by breaking them into steps:

```yaml
# Step 1: Test first job only
workflow:
  jobs:
    - id: step1
      component: comp1

# Step 2: Add second job
workflow:
  jobs:
    - id: step1
      component: comp1
    - id: step2
      component: comp2
      depends_on: [step1]
```

### 16.3.4 Check API Responses

To verify HTTP client responses:

```yaml
component:
  type: http-client
  endpoint: https://api.example.com/v1/resource
  output: ${response}  # Output entire response
```

### 16.3.5 Docker Container Logs

Check container logs when using Docker runtime:

```bash
# Check running containers
docker ps

# View logs
docker logs <container-id>

# Follow logs in real-time
docker logs -f <container-id>
```

### 16.3.6 Verify Environment Variables

Check if environment variables are properly set:

```bash
# Use .env file
cat .env

# Print environment variables
env | grep OPENAI
```

Test environment variables in workflow:

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

### 16.3.7 Check Port Conflicts

Check if port is already in use:

```bash
# Linux/Mac
lsof -i :8080

# Windows
netstat -ano | findstr :8080
```

Use a different port:
```yaml
controller:
  port: 8081  # Change to different port
```

### 16.3.8 Verify Dependencies

Check if required Python packages are installed:

```bash
pip list | grep transformers
pip list | grep torch
pip list | grep gradio
```

Install missing packages:
```bash
pip install transformers torch gradio
```

---

## Next Steps

If issues persist:
- Search for similar issues in [GitHub Issues](https://github.com/your-repo/model-compose/issues)
- When creating a new issue, include:
  - model-compose version
  - Python version
  - Operating system
  - Complete error message
  - Minimal reproducible configuration file
- Ask for help in community forums

---

**Next Chapter**: [17. Appendix](./17-appendix.md)
