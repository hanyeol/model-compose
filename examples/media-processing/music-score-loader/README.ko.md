# 음악 악보 로더 예제

이 예제는 model-compose의 `music-score-loader` 컴포넌트를 사용하여 심볼릭 음악 파일 — MIDI (`.mid`/`.midi`) 및 MusicXML (`.xml`/`.musicxml`/`.mxl`) — 을 MusicXML `<score-partwise>`를 본뜬 `MusicScore` 형태로 파싱하는 방법을 보여줍니다. 결과물에는 파트별 노트/가사/음자리표와 악보 수준의 템포, 박자/조표, 화성이 모두 포함됩니다.

레퍼런스 멜로디나 리드 시트를 파일 형태로 가지고 있고, 다운스트림 컴포넌트(피치 보정, 신디사이즈, 정렬 등)가 이를 불투명한 바이너리가 아닌 구조화된 데이터로 소비하도록 하고 싶을 때 사용합니다.

## 개요

이 예제는 4개의 워크플로우를 제공합니다:

1. **악보 파일 로드** (기본) — 헤더 또는 확장자로 포맷 자동 감지, 악보의 모든 파트를 반환
2. **특정 파트 로드** — 명시적 `part` 인덱스를 지정. MIDI는 `(track, channel)` 조합마다 별도 파트로 분리되고, 다중 파트 MusicXML 악보에서 한 성부만 뽑고 싶을 때 사용
3. **MIDI 포맷 강제** — 자동 감지를 건너뛰고 입력을 MIDI로 파싱. 헤더가 제거되었거나 비표준 확장자를 가진 파일에 유용
4. **MusicXML 포맷 강제** — 같은 방식으로 MusicXML로 파싱. 압축되지 않은 XML 형식과 압축된 `.mxl` ZIP 컨테이너 모두 지원

## 준비사항

### 필수 요구사항

- model-compose가 설치되어 PATH에서 사용 가능
- Python 의존성은 첫 실행 시 자동 설치:
  - `mido` (`local` 드라이버의 MIDI 파싱에 사용). MusicXML 파싱은 Python 표준 라이브러리를 사용하므로 추가 설치가 필요 없습니다.

### 설정

이 예제 디렉토리로 이동:
```bash
cd examples/media-processing/music-score-loader
```

## 실행 방법

1. **서비스 시작:**
   ```bash
   model-compose up
   ```

   서비스가 시작되면:
   - API 엔드포인트: http://localhost:8080/api
   - 웹 UI: http://localhost:8081

2. **워크플로우 실행:**

   **웹 UI 사용:**
   - 웹 UI 열기: http://localhost:8081
   - 드롭다운에서 워크플로우 선택
   - MIDI 또는 MusicXML 파일 업로드
   - "Run Workflow" 클릭

   **CLI 사용:**
   ```bash
   # 포맷과 트랙 자동 감지 (기본)
   model-compose run load-score --input '{"score": "/path/to/melody.mid"}'

   # 특정 파트 선택 — 파일에 여러 파트가 있고 하나만 뽑고 싶을 때 유용
   model-compose run load-score-track --input '{
     "score": "/path/to/melody.mid",
     "part": 1
   }'

   # 알 수 없는 확장자의 파일을 MIDI로 취급
   model-compose run load-score-as-midi --input '{"score": "/path/to/melody.bin"}'

   # 압축된 .mxl 아카이브를 명시적으로 MusicXML로 취급
   model-compose run load-score-as-musicxml --input '{"score": "/path/to/melody.mxl"}'
   ```

   **API 사용:**
   ```bash
   curl -X POST http://localhost:8080/api/workflows/runs \
     -F "workflow=load-score" \
     -F "score=@/path/to/melody.mid"
   ```

## 컴포넌트 상세

### Music Score Loader 컴포넌트

- **타입**: `music-score-loader`
- **용도**: MIDI/MusicXML 파일을 `MusicScore` (파트별 노트/가사/음자리표 + 악보 수준 템포, 박자/조표, 화성)로 파싱하여 다운스트림 컴포넌트가 포맷별 로직 없이 사용할 수 있도록 함
- **드라이버**:
  - `local` — 표준 라이브러리 + `mido` 기반 파싱 (기본)

*오디오*로부터 피치를 추정하려면(심볼릭 악보가 아닌) [`pitch-estimator`](../../model-tasks/pitch-estimation/)를 대신 사용하세요. 이 로더의 출력을 피치 보정 중 레퍼런스 멜로디로 사용하는 방법은 [`music-pitch-corrector`](../music-pitch-corrector/)를 참조하세요.

## 워크플로우 상세

### 1. 악보 파일 로드

**ID**: `load-score`

파일의 매직 바이트로 포맷 자동 감지(`MThd` → MIDI, `<?xml` → MusicXML, `PK` → 압축된 `.mxl`)하고, 헤더가 모호할 때는 확장자로 폴백합니다. 파일의 모든 파트를 반환합니다 — MIDI는 노트가 있는 각 `(track, channel)` 조합이 하나의 파트가 됩니다.

#### 입력 매개변수

| 매개변수 | 타입 | 필수 | 기본값 | 설명 |
|-----------|------|----------|---------|-------------|
| `score` | file | 예 | - | 파싱할 MIDI 또는 MusicXML 파일 |

#### 예시 출력

```json
{
  "format": "midi",
  "duration": 1.5,
  "parts": [
    {
      "id": "T0_C0",
      "part_name": "Melody",
      "part_abbreviation": null,
      "midi_channel": 0,
      "midi_program": null,
      "notes": [
        { "start_time": 0.0, "end_time": 0.5, "pitch": 60, "velocity": 0.787 },
        { "start_time": 1.0, "end_time": 1.5, "pitch": 64, "velocity": 0.630 }
      ],
      "lyrics": [],
      "clefs": []
    }
  ],
  "tempos":          [{ "time": 0.0, "beats_per_minute": 120.0 }],
  "time_signatures": [{ "time": 0.0, "beats": 4, "beat_type": 4 }],
  "key_signatures":  [],
  "harmonies":       []
}
```

- `pitch`는 MIDI 번호(중앙 C = 60).
- `velocity`는 [0, 1]로 정규화. MusicXML은 보편적 다이내믹이 없어 고정된 메조포르테 값으로 폴백.
- `tempos`, `time_signatures`, `key_signatures`는 모든 변화 지점을 순서대로 나열.
- `harmonies`, `clefs`, 가사의 `syllabic`/`number`는 MusicXML 전용. MIDI 로드 시 비어있거나 `null`.

---

### 2. 특정 파트 로드

**ID**: `load-score-track`

파트를 0-기반 인덱스로 정확히 하나 선택합니다. 범위를 벗어난 인덱스는 조용히 폴백하지 않고 에러를 발생시킵니다.

#### 입력 매개변수

| 매개변수 | 타입 | 필수 | 기본값 | 설명 |
|-----------|------|----------|---------|-------------|
| `score` | file | 예 | - | 파싱할 MIDI 또는 MusicXML 파일 |
| `part` | number | 아니오 | `0` | 0-기반 파트 인덱스 |

일반적인 경우:
- **다채널 MIDI**: 노트가 있는 각 `(track, channel)`이 별도의 파트 — 필요한 조합의 인덱스를 지정.
- **MusicXML 리드 시트**: 보통 단일 `<part>`라 `part=0`이 맞음.
- **다중 파트 MusicXML 악보**: 더 높은 인덱스로 추가 성부(예: 베이스, 하모니) 선택.

#### 예시 출력

*악보 파일 로드*와 동일한 형태이며, `parts`가 선택된 인덱스로 좁혀집니다.

---

### 3. MIDI 포맷 강제

**ID**: `load-score-as-midi`

포맷 스니핑을 건너뛰고 입력을 Standard MIDI File로 파싱합니다. 입력 계약을 알고 있을 때는 자동 감지 오류가 조용히 일어나는 것보다 명시적으로 실패하는 쪽이 종종 바람직합니다.

#### 입력 매개변수

| 매개변수 | 타입 | 필수 | 기본값 | 설명 |
|-----------|------|----------|---------|-------------|
| `score` | file | 예 | - | MIDI로 파싱할 파일 |

---

### 4. MusicXML 포맷 강제

**ID**: `load-score-as-musicxml`

포맷 스니핑을 건너뛰고 입력을 MusicXML로 파싱합니다. 압축되지 않은(`.xml`/`.musicxml`) 입력과 압축된(`.mxl` ZIP) 입력을 모두 받습니다. `.mxl`의 경우 로더가 `META-INF/container.xml`의 rootfile 포인터를 읽고, 해당 파일이 없을 때는 첫 번째 non-meta XML 엔트리로 폴백합니다.

#### 입력 매개변수

| 매개변수 | 타입 | 필수 | 기본값 | 설명 |
|-----------|------|----------|---------|-------------|
| `score` | file | 예 | - | MusicXML로 파싱할 파일 |

`score-partwise` 레이아웃만 지원됩니다 — `score-timewise`는 에러로 거부됩니다(실제 사용되는 파일의 5% 미만이 timewise 사용).
