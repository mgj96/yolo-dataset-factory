# yolo-dataset-factory 메인 디자인

## 1. 개요

- **목적**: YOLO 학습용 **데이터셋 자동 생성** 도구. 이미지 수집·라벨링·포맷 변환을 지원하여 YOLO 학습용 데이터셋을 구성.
- **범위**: Detection용 데이터셋 중심. 필요 시 Segmentation 등 확장 검토.

## 2. 아키텍처

- **레이어**: 단일 FastAPI 앱 + 전처리·라벨/포맷 변환 레이어. 클라이언트 → FastAPI → 이미지/메타 처리 → YOLO 형식 데이터셋 출력.
- **주요 모듈**: 설계 시 `main.py`(라우트), `dataset_io.py`(저장·경로), `labeling/yoloworld_labeler.py`(추론), 데이터셋 디렉터리 구조·YAML 정의.
- **워크플로**: 업로드 진입 → 세션 생성(또는 기존 데이터셋) → 분석(설정 자동 채움) → 라벨링·검수 → 검수 완료 시 정제된 데이터로 판별 → 학습용 사용. 자세한 단계는 [DATASET_WORKFLOW.md](DATASET_WORKFLOW.md) 참고.

## 3. 패턴

- **API 레이어**: 엔드포인트는 프로젝트 요구에 따라 정의. 응답은 JSON 일관 권장.
- **데이터셋·세션**: YOLO 형식(images/ + labels/ + data.yaml). 세션은 업로드 시 `dataset_id` 없이 생성되며, 동일 디렉터리 구조를 사용(세션 ID = dataset_id 형태). `POST /api/dataset/frames` 에서 dataset_id 생략 또는 session=true 시 세션 ID 자동 생성.
- **분석 API**: `POST /api/dataset/{id}/analyze` — 후보 클래스로 1회 추론 후 검출된 클래스 제안·초기 라벨 저장. 후보 클래스는 요청 body 또는 config.ANALYZE_CANDIDATE_CLASSES.
- **정제된 데이터**: 메타 status가 `reviewed` 또는 `manual_labeled` 인 항목만 정제된 것으로 간주. `GET /api/dataset/{id}/labels?refined_only=true`, `GET /api/dataset/{id}/info?refined_only=true` 로 필터링·요약 가능.
- **문서**: 분석·설계 문서는 개요 → 상세 → 요약, 용어 통일(예: 엔드포인트, 추론, 전처리).

## 4. 의사결정

- 데이터셋 형식: YOLO 표준 구조·포맷 우선.
- 단일 앱 구조 유지: 마이크로서비스 분리는 요구·운영 정책에 따라 검토.
- 기존 PythonProject 룰·docs 기반으로 스타일·패턴 유지.

## 5. API·개발 환경 호환

- 프론트(8100) ↔ API(8081) 크로스 오리진, 데이터셋 경로(cwd), 이미지 응답 Content-Type 등으로 인한 호환 이슈 재발 방지를 위해 [API_AND_DEV_COMPATIBILITY.md](API_AND_DEV_COMPATIBILITY.md)를 두었음. 새 엔드포인트·실행 방식 변경 시 해당 문서의 체크리스트를 참고.

## 6. Cursor 사용: Rules / Skills / Subagents

- **Rules** (`.cursor/rules/*.mdc`): 프로젝트 전역·파일별 코딩·스타일 규칙. style.mdc, python-api.mdc 등. STYLE.md 참조.
- **Skills**: 공통 워크플로·패턴. 필요 시 .cursor/skills 에 추가.
- **Subagents** (`.cursor/agents/*.md`): 역할별 에이전트. docs/prompts 참조.
