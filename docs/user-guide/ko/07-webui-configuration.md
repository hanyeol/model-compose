# 7장: Web UI 구성

이 장에서는 model-compose의 Web UI를 구성하는 방법을 다룹니다. Gradio 드라이버와 정적 파일 드라이버를 사용하여 워크플로우를 테스트하고 실행할 수 있는 웹 인터페이스를 설정하는 방법을 학습합니다.

---

## 7.1 Web UI 개요

model-compose는 워크플로우를 테스트하고 실행할 수 있는 웹 인터페이스를 선택적으로 제공합니다. Web UI는 컨트롤러 타입(`http-server` 또는 `mcp-server`)에 관계없이 동일하게 동작하며, 설정된 컨트롤러에 맞춰 자동으로 워크플로우를 실행합니다.

### 컨트롤러만 실행

Web UI 없이 컨트롤러만 실행하는 경우입니다. API 엔드포인트만 필요한 프로덕션 환경에 적합합니다.

```yaml
controller:
  type: http-server
  port: 8080
  base_path: /api
  # webui 설정 없음
```

이 경우 워크플로우는 HTTP API(`/api/workflows/runs`)를 통해서만 실행할 수 있습니다.

### 컨트롤러 + Web UI 실행

Web UI를 함께 실행하여 브라우저에서 워크플로우를 테스트하고 실행할 수 있습니다.

```yaml
controller:
  type: http-server
  port: 8080       # 컨트롤러 API 포트
  base_path: /api
  webui:
    driver: gradio # 또는 static
    port: 8081     # Web UI 포트 (컨트롤러와 달라야 함)
```

> **중요**: Web UI는 항상 컨트롤러와 다른 포트에서 실행되어야 합니다.

이 설정을 사용하면 컨트롤러 API는 `http://localhost:8080/api`에서, Web UI는 `http://localhost:8081`에서 실행됩니다. Web UI는 내부적으로 컨트롤러 API를 호출하여 워크플로우를 실행합니다.

---

## 7.2 Gradio 드라이버

Gradio는 워크플로우 스키마를 기반으로 자동 생성되는 대화형 웹 UI입니다.

### 설정

```yaml
controller:
  type: http-server
  port: 8080
  base_path: /api
  webui:
    driver: gradio  # 기본값 (생략 가능)
    host: 127.0.0.1 # 기본값
    port: 8081      # 기본값
```

설정 옵션:
- `driver`: 웹 UI 드라이버 (기본값: `gradio`)
- `host`: 웹 UI 서버가 바인딩할 호스트 주소 (기본값: `127.0.0.1`)
- `port`: 웹 UI 서버 포트 (기본값: `8081`, 컨트롤러 포트와 달라야 함)

### UI 자동 생성

Gradio는 워크플로우의 `input`과 `output` 정의를 기반으로 UI를 자동 생성합니다:

**입력 컴포넌트 매핑**:
- `string`: 텍스트 입력 (Textbox)
- `text`: 다중 라인 텍스트 입력 (Textbox, 5-15줄)
- `integer`: 정수 입력 (Textbox)
- `number`: 숫자 입력 (Number)
- `boolean`: 체크박스 (Checkbox)
- `list`: 쉼표 구분 리스트 (Textbox)
- `image`: 이미지 업로드 (Image)
- `audio`: 오디오 업로드 (Audio)
- `video`: 비디오 업로드 (Video)
- `file`: 파일 업로드 (File)
- `select`: 드롭다운 (Dropdown)

**출력 컴포넌트 매핑**:
- `string`, `text`: 텍스트 표시 (Textbox, 읽기 전용)
- `markdown`: 마크다운 렌더링 (Markdown)
- `json`, `objects`: JSON 뷰어 (JSON)
- `image`: 이미지 표시 (Image)
- `audio`: 오디오 플레이어 (Audio)
- `video`: 비디오 플레이어 (Video)

### 스트리밍 출력 지원

워크플로우에서 출력을 `as text;sse-text` 또는 `as json;sse-json`로 지정하면 실시간 스트리밍으로 표시됩니다.

```yaml
workflow:
  title: Summarize Text
  input: ${input}
  output: ${output as text;sse-text}  # 스트리밍 출력

component:
  type: model
  task: text-generation
  model: facebook/bart-large-cnn
  text: ${input.text}
  streaming: true  # 컴포넌트에서 스트리밍 활성화
```

- **텍스트 스트리밍** (`sse-text`): 청크가 도착할 때마다 누적하여 표시 (예: AI 텍스트 생성)
- **JSON 스트리밍** (`sse-json`): 각 청크를 리스트에 추가하여 표시 (예: 여러 결과 순차 생성)

Gradio UI에서는 출력이 실시간으로 업데이트되어 생성 과정을 볼 수 있습니다.

### 다중 워크플로우

- 여러 워크플로우가 정의된 경우 탭으로 구분하여 표시됩니다
- 각 탭에는 워크플로우의 `title` 또는 `id`가 표시됩니다

### Gradio UI 접속

```
http://localhost:8081
```

각 워크플로우는 다음 구조로 표시됩니다:
1. 워크플로우 제목과 설명
2. 입력 파라미터 섹션
3. "Run Workflow" 버튼
4. 출력 값 섹션

---

## 7.3 정적 파일 드라이버

커스텀 HTML/CSS/JavaScript 파일을 제공합니다. FastAPI의 `StaticFiles`를 사용하여 정적 파일을 서빙하며, `html=True` 옵션으로 `index.html`을 자동으로 제공합니다.

### 설정

```yaml
controller:
  type: http-server
  port: 8080
  base_path: /api
  webui:
    driver: static     # 필수
    host: 127.0.0.1    # 기본값
    port: 8081         # 기본값
    static_dir: webui  # 기본값
```

설정 옵션:
- `driver`: `static` (필수, gradio가 기본값이므로 반드시 지정 필요)
- `host`: 웹 UI 서버가 바인딩할 호스트 주소 (기본값: `127.0.0.1`)
- `port`: 웹 UI 서버 포트 (기본값: `8081`)
- `static_dir`: 정적 파일이 있는 디렉토리 경로 (기본값: `webui`)

### 동작 방식

- `static_dir` 경로의 모든 파일이 `/` 경로로 마운트됩니다
- `http://localhost:8081/`로 접속하면 `index.html`이 자동으로 제공됩니다
- 모든 정적 파일(CSS, JS, 이미지 등)은 상대 경로로 참조 가능합니다
- 컨트롤러 API는 별도 포트(예: 8080)에서 실행되므로 CORS 설정이 필요할 수 있습니다

### 디렉토리 구조 예시

```
webui/
├── index.html
├── css/
│   └── style.css
├── js/
│   └── app.js
└── assets/
    └── logo.png
```

### 간단한 예시

**index.html**:
```html
<!DOCTYPE html>
<html>
<head>
    <title>AI Workflow UI</title>
    <link rel="stylesheet" href="/css/style.css">
</head>
<body>
    <h1>Workflow Runner</h1>
    <div id="workflow-container">
        <input id="input" type="text" placeholder="Enter input...">
        <button onclick="runWorkflow()">Run</button>
        <pre id="output"></pre>
    </div>
    <script src="/js/app.js"></script>
</body>
</html>
```

**js/app.js**:
```javascript
async function runWorkflow() {
    const input = document.getElementById('input').value;
    const output = document.getElementById('output');

    try {
        const response = await fetch('http://localhost:8080/api/workflows/runs', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                workflow_id: 'my-workflow',
                input: { text: input },
                wait_for_completion: true,
                output_only: true
            })
        });

        const data = await response.json();
        output.textContent = JSON.stringify(data, null, 2);
    } catch (error) {
        output.textContent = `Error: ${error.message}`;
    }
}
```

> **참고**: 정적 파일 드라이버는 단순히 파일을 제공할 뿐이며, 실제 워크플로우 실행은 컨트롤러 API를 통해 JavaScript에서 직접 호출해야 합니다.

---

## 7.4 리버스 프록시를 통한 Web UI 배포

프로덕션 환경에서는 Nginx 같은 리버스 프록시를 통해 컨트롤러 API와 Web UI를 함께 배포할 수 있습니다.

### model-compose 설정

```yaml
controller:
  type: http-server
  host: 127.0.0.1  # 프록시에서만 접근
  port: 8080
  base_path: /api
  webui:
    driver: gradio
    host: 127.0.0.1
    port: 8081
```

### Nginx 설정 예시

```nginx
server {
    listen 80;
    server_name example.com;

    # API 프록시
    location /api/ {
        proxy_pass http://127.0.0.1:8080/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # Web UI 프록시
    location / {
        proxy_pass http://127.0.0.1:8081/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

외부 접속:
- **API**: `http://example.com/api/` → `http://127.0.0.1:8080/api/`
- **Web UI**: `http://example.com/` → `http://127.0.0.1:8081/`

Web UI는 컨트롤러와 같은 도메인에서 서비스되므로 별도의 CORS 설정이 필요하지 않습니다.

---

## 다음 단계

실습해보세요:
- Gradio를 사용하여 자동 생성 UI 테스트
- 정적 파일 드라이버로 커스텀 UI 구축
- 스트리밍 출력으로 실시간 응답 표시

---

**다음 장**: [8. 로컬 AI 모델 사용](./08-local-ai-models.md)
