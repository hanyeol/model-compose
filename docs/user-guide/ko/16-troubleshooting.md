# 16. 문제 해결

이 장에서는 model-compose 사용 중 자주 발생하는 문제와 해결 방법을 다룹니다.

---

## 16.1 자주 묻는 질문 (FAQ)

### 16.1.1 설치 및 환경 설정

**Q: Python 버전 요구사항은 무엇인가요?**

A: model-compose는 Python 3.9 이상이 필요합니다. Python 3.11 이상을 권장합니다.

```bash
python --version  # Python 3.9+ 확인
```

**Q: 설치 후 `model-compose` 명령어를 찾을 수 없습니다.**

A: PATH 환경 변수를 확인하세요:

```bash
# pip로 설치한 경우
pip show model-compose

# 개발 모드로 설치
pip install -e .
```

**Q: Docker 런타임 사용 시 GPU를 인식하지 못합니다.**

A: NVIDIA Container Toolkit이 설치되어 있는지 확인하세요:

```bash
# Docker에서 GPU 사용 가능 여부 확인
docker run --rm --gpus all nvidia/cuda:11.8.0-base-ubuntu22.04 nvidia-smi
```

### 16.1.2 컴포넌트 설정

**Q: 모델 컴포넌트 로딩 시 메모리 부족 오류가 발생합니다.**

A: 다음 방법들을 시도해보세요:

1. **양자화 사용**:
```yaml
component:
  type: model
  model: meta-llama/Llama-2-7b-hf
  quantization: int8  # 또는 int4, nf4
```

2. **배치 크기 줄이기**:
```yaml
component:
  batch_size: 1
```

3. **CPU 사용**:
```yaml
component:
  device: cpu
```

**Q: HTTP 클라이언트에서 타임아웃 오류가 발생합니다.**

A: 타임아웃 시간을 늘리거나 재시도 설정을 추가하세요:

```yaml
component:
  type: http-client
  timeout: 120  # 초 단위
  max_retries: 5
  retry_delay: 2
```

**Q: 벡터 스토어 연결이 실패합니다.**

A: 호스트와 포트 설정을 확인하세요:

```yaml
component:
  type: vector-store
  driver: milvus
  host: localhost
  port: 19530
```

서버가 실행 중인지 확인:
```bash
# Milvus
docker ps | grep milvus

# ChromaDB (독립 실행형)
docker ps | grep chroma
```

### 16.1.3 워크플로우 실행

**Q: 워크플로우 실행 시 변수를 찾을 수 없다는 오류가 발생합니다.**

A: 변수 바인딩 구문이 올바른지 확인하세요:

```yaml
# 잘못된 예
output: ${result}  # result가 정의되지 않음

# 올바른 예
output: ${output}
output: ${jobs.job-id.output}
output: ${input.field}
```

**Q: 작업 의존성이 제대로 작동하지 않습니다.**

A: `depends_on` 필드에 올바른 작업 ID를 지정했는지 확인하세요:

```yaml
jobs:
  - id: job1
    component: comp1

  - id: job2
    component: comp2
    depends_on: [ job1 ]  # job1 완료 후 실행
```

**Q: 스트리밍 응답이 출력되지 않습니다.**

A: 다음을 확인하세요:

1. 컴포넌트에서 스트리밍 활성화:
```yaml
component:
  type: http-client
  stream_format: json
```

2. 워크플로우 출력에 스트리밍 참조 사용:
```yaml
workflow:
  output: ${result[]}  # 청크별 출력
```

3. 컨트롤러에서 응답 형식 지정:
```yaml
workflow:
  output: ${output as text;sse-text}
```

### 16.1.4 Web UI

**Q: Gradio Web UI가 시작되지 않습니다.**

A: Gradio가 설치되어 있는지 확인하세요:

```bash
pip show gradio
```

포트 충돌 확인:
```bash
lsof -i :8081  # 기본 Web UI 포트
```

**Q: Web UI에서 파일 업로드가 작동하지 않습니다.**

A: 입력 타입이 올바르게 지정되었는지 확인하세요:

```yaml
workflow:
  input:
    image: ${input.image as image}
    document: ${input.doc as file}
```

### 16.1.5 리스너와 게이트웨이

**Q: 리스너가 외부에서 접근되지 않습니다.**

A: 게이트웨이를 설정하세요:

```yaml
gateway:
  type: ngrok
  port: 8080
  authtoken: ${env.NGROK_AUTHTOKEN}
```

**Q: ngrok 게이트웨이 연결이 실패합니다.**

A: 인증 토큰이 설정되어 있는지 확인하세요:

```bash
echo $NGROK_AUTHTOKEN
```

ngrok이 설치되어 있는지 확인:
```bash
ngrok version
```

---

## 16.2 일반적인 오류 및 해결책

### 16.2.1 모델 로딩 오류

**오류**: `RuntimeError: CUDA out of memory`

**원인**: GPU 메모리 부족

**해결책**:
1. 더 작은 모델 사용
2. 양자화 적용 (`quantization: int8` 또는 `int4`, `nf4`)
3. 배치 크기 줄이기
4. CPU 사용 (`device: cpu`)

```yaml
component:
  type: model
  model: smaller-model
  device: cuda
  quantization: int8
  batch_size: 1
```

---

**오류**: `OSError: Can't load tokenizer for 'model-name'`

**원인**: 모델 또는 토크나이저 다운로드 실패

**해결책**:
1. 인터넷 연결 확인
2. HuggingFace 토큰 설정 (비공개 모델):
```bash
export HF_TOKEN=your_token_here
```
3. 캐시 디렉토리 확인:
```bash
ls ~/.cache/huggingface/hub/
```

---

### 16.2.2 네트워크 오류

**오류**: `ConnectionError: Failed to connect to API`

**원인**: API 엔드포인트 연결 실패

**해결책**:
1. 엔드포인트 URL 확인
2. API 키 확인
3. 네트워크 연결 확인
4. 타임아웃 시간 증가

```yaml
component:
  type: http-client
  endpoint: https://api.openai.com/v1/chat/completions
  headers:
    Authorization: Bearer ${env.OPENAI_API_KEY}
  timeout: 60
```

---

**오류**: `SSLError: certificate verify failed`

**원인**: SSL 인증서 검증 실패

**해결책**:
1. 인증서 업데이트:
```bash
pip install --upgrade certifi
```
2. 또는 검증 비활성화 (권장하지 않음):
```yaml
component:
  type: http-client
  verify_ssl: false
```

---

### 16.2.3 설정 파일 오류

**오류**: `ValidationError: Invalid configuration`

**원인**: YAML 문법 오류 또는 필수 필드 누락

**해결책**:
1. YAML 문법 검사:
```bash
python -c "import yaml; yaml.safe_load(open('model-compose.yml'))"
```
2. 스키마 참조하여 필수 필드 확인 (17장 참조)
3. 들여쓰기 확인 (공백 2칸 사용)

---

**오류**: `KeyError: 'component-id'`

**원인**: 존재하지 않는 컴포넌트 ID 참조

**해결책**:
컴포넌트 ID가 정의되어 있는지 확인:

```yaml
components:
  - id: my-component  # 이 ID 사용
    type: model

workflow:
  component: my-component  # 동일한 ID 참조
```

---

### 16.2.4 변수 바인딩 오류

**오류**: `ValueError: Cannot resolve variable '${input.field}'`

**원인**: 변수 경로가 잘못되었거나 데이터가 없음

**해결책**:
1. 변수 경로 확인
2. 기본값 추가:
```yaml
output: ${input.field | "default-value"}
```
3. 디버깅을 위해 전체 객체 출력:
```yaml
output: ${input}  # 전체 입력 확인
```

---

**오류**: `TypeError: Object of type 'bytes' is not JSON serializable`

**원인**: 바이너리 데이터를 JSON으로 직렬화 시도

**해결책**:
Base64 인코딩 사용:
```yaml
output: ${binary_data as base64}
```

---

### 16.2.5 Docker 런타임 오류

**오류**: `docker.errors.ImageNotFound`

**원인**: Docker 이미지를 찾을 수 없음

**해결책**:
1. 이미지 풀:
```bash
docker pull python:3.11
```
2. 또는 커스텀 빌드:
```yaml
controller:
  runtime:
    type: docker
    build:
      context: .
      dockerfile: Dockerfile
```

---

**오류**: `PermissionError: [Errno 13] Permission denied`

**원인**: Docker 소켓 권한 부족

**해결책**:
```bash
# 현재 사용자를 docker 그룹에 추가
sudo usermod -aG docker $USER
newgrp docker
```

---

## 16.3 디버깅 팁

### 16.3.1 로깅 활성화

상세한 로그를 보려면 로거 레벨을 DEBUG로 설정하세요:

```yaml
logger:
  type: console
  level: DEBUG
  format: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
```

또는 환경 변수 사용:
```bash
export LOG_LEVEL=DEBUG
model-compose up
```

### 16.3.2 변수 값 확인

워크플로우 중간에 변수 값을 확인하려면 임시 출력을 추가하세요:

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

### 16.3.3 단계별 실행

복잡한 워크플로우는 단계별로 나누어 테스트하세요:

```yaml
# 1단계: 첫 번째 작업만 테스트
workflow:
  jobs:
    - id: step1
      component: comp1

# 2단계: 두 번째 작업 추가
workflow:
  jobs:
    - id: step1
      component: comp1
    - id: step2
      component: comp2
      depends_on: [step1]
```

### 16.3.4 API 응답 확인

HTTP 클라이언트 응답을 확인하려면:

```yaml
component:
  type: http-client
  endpoint: https://api.example.com/v1/resource
  output: ${response}  # 전체 응답 출력
```

### 16.3.5 Docker 컨테이너 로그

Docker 런타임 사용 시 컨테이너 로그 확인:

```bash
# 실행 중인 컨테이너 확인
docker ps

# 로그 보기
docker logs <container-id>

# 실시간 로그
docker logs -f <container-id>
```

### 16.3.6 환경 변수 확인

환경 변수가 제대로 설정되었는지 확인:

```bash
# .env 파일 사용
cat .env

# 환경 변수 출력
env | grep OPENAI
```

워크플로우에서 환경 변수 테스트:

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

### 16.3.7 포트 충돌 확인

포트가 이미 사용 중인지 확인:

```bash
# Linux/Mac
lsof -i :8080

# Windows
netstat -ano | findstr :8080
```

다른 포트 사용:
```yaml
controller:
  port: 8081  # 다른 포트로 변경
```

### 16.3.8 의존성 확인

필요한 Python 패키지가 설치되어 있는지 확인:

```bash
pip list | grep transformers
pip list | grep torch
pip list | grep gradio
```

누락된 패키지 설치:
```bash
pip install transformers torch gradio
```

---

## 다음 단계

문제가 해결되지 않으면:
- [GitHub Issues](https://github.com/your-repo/model-compose/issues)에서 유사한 문제 검색
- 새로운 이슈 생성 시 다음 정보 포함:
  - model-compose 버전
  - Python 버전
  - 운영 체제
  - 오류 메시지 전체
  - 재현 가능한 최소 설정 파일
- 커뮤니티 포럼에서 도움 요청

---

**다음 장**: [17. 부록](./17-appendix.md)
