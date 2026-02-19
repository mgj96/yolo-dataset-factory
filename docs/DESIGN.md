# yolo-dataset-factory 메인 디자인

## 1. 개요

- **목적**: YOLO 학습용 **데이터셋 자동 생성** 도구. 이미지 수집·라벨링·포맷 변환을 지원하여 YOLO 학습용 데이터셋을 구성.
- **범위**: Detection용 데이터셋 중심. 필요 시 Segmentation 등 확장 검토.

## 2. 아키텍처

- **레이어**: 단일 FastAPI 앱 + 전처리·라벨/포맷 변환 레이어. 클라이언트 → FastAPI → 이미지/메타 처리 → YOLO 형식 데이터셋 출력.
- **주요 모듈**: 설계 시 `main.py`(라우트), `utils.py`(전처리·포맷), 데이터셋 디렉터리 구조·YAML 정의.
- **데이터셋 생성·이미지 수집**: 모두 API로 수행. 이미지 업로드(`POST /api/dataset/frames`) → 이미지 목록 조회(`GET /api/dataset/{id}/images`) → 자동 라벨(`POST /api/dataset/{id}/auto-label`) 순으로 사용.
- **실행**: 기본 포트 **8081** (다른 메인 모듈과 충돌 방지). `./run.sh` 또는 `uvicorn main:app --port 8081`. `SERVER_PORT` 환경 변수로 변경 가능.
- **자동 라벨 다운로드 (회사 프록시 등)**  
  - **권장**: SSH 터널로 우회해 SSL 검증 유지. `ssh -D 1080 user@점프서버` 후 `HTTPS_PROXY=socks5h://127.0.0.1:1080 ./run.sh` 로 실행. 0/1 전환 없이 한 번만 설정하면 됨.  
  - **대안**: SSH 불가 시 `YOLO_DATASET_FACTORY_SSL_VERIFY=0` 으로 검증 생략 (보안상 비권장).

## 3. 패턴

- **API 레이어**: 엔드포인트는 프로젝트 요구에 따라 정의. 응답은 JSON 일관 권장.
- **데이터셋**: YOLO 형식(images/ + labels/ + data.yaml). 전처리·어노테이션 변환 시 프로젝트 규칙(STYLE.md, rules) 준수.
- **문서**: 분석·설계 문서는 개요 → 상세 → 요약, 용어 통일(예: 엔드포인트, 추론, 전처리).

## 4. 의사결정

- 데이터셋 형식: YOLO 표준 구조·포맷 우선.
- 단일 앱 구조 유지: 마이크로서비스 분리는 요구·운영 정책에 따라 검토.
- 기존 PythonProject 룰·docs 기반으로 스타일·패턴 유지.

## 5. Cursor 사용: Rules / Skills / Subagents

- **Rules** (`.cursor/rules/*.mdc`): 프로젝트 전역·파일별 코딩·스타일 규칙. style.mdc, python-api.mdc 등. STYLE.md 참조.
- **Skills**: 공통 워크플로·패턴. 필요 시 .cursor/skills 에 추가.
- **Subagents** (`.cursor/agents/*.md`): 역할별 에이전트. docs/prompts 참조.
