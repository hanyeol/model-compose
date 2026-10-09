# Instagram 다운로더 (인증 세션 기반)

로컬에서 실행 중인 Chrome 브라우저의 세션 쿠키를 사용해 Instagram
게시물, 릴스, IGTV 클립(또는 오디오 트랙)을 다운로드합니다.
Instagram은 거의 모든 요청에 로그인 세션을 요구합니다 — 스토리,
릴스, 피드 영상, 비공개 계정 게시물 모두 쿠키가 없으면 "로그인하여
계속" 응답으로 떨어집니다.

## 개요

두 컴포넌트가 함께 동작합니다:

1. **`browser` (`web-browser` / `chrome`)** — 사용자가
   `--remote-debugging-port=9222`로 실행한 Chrome에 attach합니다.
   그 창에서 Instagram에 한 번 로그인해두면, 워크플로우가 세션
   쿠키를 읽어옵니다.
2. **`downloader` (`media-downloader` / `ytdlp`)** — 그 쿠키 리스트를
   그대로 받아 yt-dlp에 전달하고, 인증된 세션으로 미디어를 다운로드
   합니다.

`web-browser`의 `get-cookies`가 반환하는 쿠키 형식은
`media-downloader`가 기대하는 형식과 동일하므로, 변환 없이 그대로
연결할 수 있습니다.

## 준비

### 사전 요건

- model-compose가 설치되어 PATH에 등록되어 있어야 함
- Google Chrome (또는 Chromium)이 설치되어 있어야 함
- `yt-dlp` — 드라이버의 setup requirement로 첫 실행 시 자동 설치됨
- `ffmpeg`이 PATH에 있어야 함 (오디오 추출과 영상/오디오 스트림 병합에
  필요)

### 원격 디버깅 모드로 Chrome 실행

일상 브라우저 세션과 겹치지 않도록 별도 프로필로 실행하세요:

**macOS**
```bash
/Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9222 \
  --user-data-dir=/tmp/chrome-instagram-profile
```

**Linux**
```bash
google-chrome \
  --remote-debugging-port=9222 \
  --user-data-dir=/tmp/chrome-instagram-profile
```

**Windows (PowerShell)**
```powershell
& "C:\Program Files\Google\Chrome\Application\chrome.exe" `
  --remote-debugging-port=9222 `
  --user-data-dir=$env:TEMP\chrome-instagram-profile
```

이 창은 계속 열어두세요. 이 창에서 Instagram에 한 번 로그인하면,
이후 워크플로우 실행마다 세션이 유지됩니다 (프로필을 지우거나
Instagram이 쿠키를 만료시키기 전까지 — 일반적으로 수 주간 비활성
상태가 지속되면 만료됩니다).

## 실행 방법

1. **컨트롤러 시작:**
   ```bash
   model-compose up
   ```

2. **워크플로우 실행:**

   **API 사용:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -H "Content-Type: application/json" \
     -d '{
       "workflow_id": "download-instagram-media",
       "input": {
         "url": "https://www.instagram.com/reel/C5XxYyZzZz0/"
       }
     }'
   ```

   **Web UI 사용:**
   - http://localhost:8081 열기
   - 게시물/릴스/IGTV URL 입력 (선택: `format`)
   - Run 클릭

   **CLI 사용:**
   ```bash
   model-compose run download-instagram-media \
     --input '{"url": "https://www.instagram.com/reel/C5XxYyZzZz0/"}'
   ```

3. **워크플로우가 일시 정지되면:**
   - `check-signin` 작업이 페이지에서 로그인된 네비게이션 바를
     찾습니다. 없으면(로그인된 세션 아님) `wait-for-signin` 작업이
     실행 전에 인터럽트를 겁니다.
   - localhost:9222에 attach된 Chrome 창으로 이동해 Instagram에
     로그인한 뒤, Web UI에서 Resume을 클릭하거나 API로 resume 요청을
     보내세요.
   - 그러면 워크플로우가 로그인된 네비게이션이 렌더링될 때까지
     기다린 후 쿠키를 수집하고 yt-dlp로 넘깁니다.
   - 이미 Chrome에 유효한 Instagram 세션이 있으면 (첫 실행 이후 대개
     그렇습니다) `check-signin`이 true를 반환해 인터럽트를 완전히
     건너뜁니다.

4. **컨트롤러 종료:**
   ```bash
   model-compose down
   ```

## 워크플로우 세부

### "Download Instagram media" 워크플로우

**설명**: 필요할 때만 attached Chrome으로 Instagram에 로그인시키고,
결과 세션 쿠키를 yt-dlp에 넘겨 요청받은 게시물, 릴스, IGTV 클립을
다운로드합니다.

#### 작업 흐름

```mermaid
graph TD
    J1((open-instagram))
    J2((check-signin))
    J3((wait-for-signin))
    J4((collect-cookies))
    J5((download))
    B[browser<br/>component]
    D[downloader<br/>component]

    Input((Input)) --> J1
    J1 -.-> B
    B -.-> J1
    J1 --> J2
    J2 -.-> B
    B -.-> J2
    J2 --> J3
    J3 -. "check-signin == false → interrupt" .-> Human((Human))
    Human -.-> J3
    J3 -.-> B
    B -.-> J3
    J3 --> J4
    J4 -.-> B
    B -.-> J4
    J4 --> J5
    J5 -.-> D
    D -.-> J5
    J5 --> Output((Output))
```

#### 입력 파라미터

| 파라미터 | 타입 | 필수 | 기본값 | 설명 |
|-----------|------|----------|---------|-------------|
| `url` | string | 예 | — | Instagram 게시물, 릴스, 또는 IGTV URL |
| `format` | string \| object | 아니오 | `mp4` | media-downloader의 `format`: preset(`mp4`, `webm`, `mkv`, `mp3`, ...), raw yt-dlp 표현식, 또는 구조화된 spec. |

#### 출력 형식

| 필드 | 타입 | 설명 |
|-------|------|-------------|
| `video` | video stream | 다운로드된 미디어 파일, 스트리밍으로 반환 |

Web UI는 인라인 플레이어로 재생하며, HTTP API는 적절한
content type과 함께 스트림을 반환합니다. 단일 이미지 게시물의 경우
extractor가 이미지 파일을 다운로드로 반환합니다.

## 컴포넌트 세부

### `browser` — web-browser (Chrome via CDP)

`localhost:9222`의 Chrome DevTools Protocol로 attach합니다. model-compose가
직접 브라우저를 띄우지 않습니다 — 사용자가 브라우저 프로세스를
소유하므로 로그인, 2FA, "의심스러운 로그인" 이메일 확인, CAPTCHA를
직접 처리할 수 있습니다.

액션:

| 액션 | 메서드 | 설명 |
|--------|--------|-------------|
| `navigate` | `navigate` | URL을 열고 DOM 파싱이 끝날 때까지 대기 |
| `check-signin` | `evaluate` | 페이지를 최대 5초 폴링하여 로그인된 네비게이션 바가 있으면 `true` 반환 |
| `wait-for-nav` | `wait-for` | Instagram의 로그인된 네비게이션이 표시될 때까지 대기 (최대 5분) |
| `get-instagram-cookies` | `get-cookies` | `instagram.com` 스코프의 쿠키 반환 |

### `downloader` — media-downloader (yt-dlp)

브라우저에서 받은 쿠키로 yt-dlp를 실행합니다. yt-dlp가 그 쿠키를
임시 Netscape 쿠키 파일로 기록하며, 각 쿠키의 domain, path, secure,
expiry를 그대로 보존해 브라우저와 동일하게 `instagram.com` 인증 요청이
성공하도록 합니다.

## 쿠키에 관한 참고

`web-browser`의 `get-cookies`가 반환하는 쿠키 객체 — `name`, `value`,
`domain`, `path`, `secure`, `expires` 등을 포함 — 는 `media-downloader`의
`cookies` 필드에 그대로 넘길 수 있습니다. Chrome DevTools Protocol과
Playwright가 사용하는 형식이 동일하므로, 다른 쿠키 소스(저장된 fixture,
`set-cookies`로 심어둔 값 등)도 같은 방식으로 downloader에 연결할 수
있습니다.

YouTube나 TikTok과 달리 Instagram은 세션 없이 공개 콘텐츠를 안정적으로
제공하지 않습니다. 앞의 네 작업을 지우고 `download`에 빈 `cookies`
필드를 넘기면 대부분의 URL이 "login required" 오류로 실패합니다.

## Rate Limit에 관한 참고

Instagram은 스크래핑 트래픽에 공격적인 rate limit을 걸며, 단일
계정에서 반복 다운로드를 하면 일시적인 action block ("일부 활동이
커뮤니티를 보호하기 위해 제한되었습니다")이 발동할 수 있습니다.
안전하게 사용하려면:

- 요청 간격을 두세요; 수십 개의 URL을 짧은 루프로 일괄 다운로드하지
  마세요.
- 개인 계정 대신 전용 더미 계정을 사용하세요.
- Action block이 발동하면 하루 이틀 정도 계정을 쉬게 둔 뒤 다시
  시도하세요 — 반복 재시도는 block을 연장시킵니다.

## 문제 해결

- **`wait-for-nav` 타임아웃**: attach된 Chrome 창이 실제로 Instagram에
  있지 않거나 로그인되지 않은 상태입니다. 창에서
  https://www.instagram.com/ 으로 이동해 로그인한 뒤 ("로그인 정보
  저장", "알림 켜기" 같은 프롬프트는 모두 닫아서 네비게이션이 완전히
  렌더링되도록) 워크플로우를 다시 실행하세요.
- **CDP 연결 거부**: Chrome이 `--remote-debugging-port=9222`로 실행되지
  않았거나, 다른 프로세스가 그 포트를 점유하고 있습니다.
  `lsof -i :9222`로 확인하세요.
- **`Requested content is not available` / HTTP 404**: 게시물이 삭제
  되었거나, 계정이 비공개로 전환되었고 팔로우되어 있지 않거나, 이미
  만료된 스토리 URL일 수 있습니다. attach된 브라우저에서 해당 URL을
  열어 아직 유효한지 확인하세요.
- **쿠키를 수집했는데도 `login required`**: Instagram이 세션을
  무효화했습니다 (비밀번호 변경, 2FA 재설정, 장기 비활성 이후 흔히
  발생). attach된 브라우저에서 다시 로그인하세요 — 다음 실행이 새
  쿠키를 가져갑니다.
- **"일부 활동이 제한되었습니다" / action block**: Instagram의
  rate limiter가 발동한 상태입니다. 위의 "Rate Limit에 관한 참고"
  항목을 보세요.
- **다운로드 이후 Web UI 플레이어가 오래 걸림**: 원본이 HEVC 또는 VP9
  일 때 Gradio가 브라우저 호환 코덱으로 재인코딩합니다. 대기 시간이
  부담되면 download 액션의 `format`을 구조화된 spec으로 지정해 H.264를
  우선 선택하도록 조정하세요 (예: `{ media: video, container: mp4,
  codec: avc1 }`).
