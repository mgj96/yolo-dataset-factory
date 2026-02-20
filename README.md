# YOLO Dataset Factory

이미지 수집부터 AI 기반 자동 라벨링·검수까지 한 흐름으로 다루어, **YOLO 학습용 데이터셋을 빠르게 만들고 관리**하는 솔루션입니다.

## 개요

- **해결하는 일**: YOLO 학습용 데이터셋 구성에 필요한 수집·라벨링·포맷 변환을 하나의 파이프라인으로 제공합니다.
- **입력**: 이미지 업로드, 동영상(프레임 추출), WebRTC 캡처.
- **출력**: YOLO 표준 형식(`images/` + `labels/` + `data.yaml`), 학습 파이프라인에 바로 사용 가능.
- **범위**: Object Detection 중심, 필요 시 Segmentation 등 확장 검토.

## 주요 기능

| 영역 | 내용 |
|------|------|
| **데이터셋 관리** | 데이터셋 목록, 이미지 목록·조회, data.yaml 기반 클래스/정보 |
| **수집** | 이미지/프레임 업로드 API (`/api/dataset/frames`) |
| **AI 자동 라벨링** | YOLO-World 기반 반자동 라벨 생성 (`/api/dataset/{id}/auto-label`), 검수·수정 후 사용 권장 |
| **검수·편집** | 레이블 목록/내용 조회, 레이블 본문 수정(PUT) |
| **서빙** | FastAPI + Vue 프론트엔드, `/docs` Swagger, `/health` 헬스체크 |

## AI 오케스트레이션

AI를 어떻게 붙였는지, 왜 그렇게 설계했는지가 드러나도록 방식과 의도·판단을 정리했습니다.

| 방식 | 내용 | 의도·판단 |
|------|------|-----------|
| **모델 로드** | 요청 시점에 YOLO-World 로드, `set_classes(class_names)` 로 사용자 클래스 매핑. 동일 요청 내 이미지마다 모델 재사용. | 요청 단위 로드로 메모리 사용을 요청 범위로 제한; 상시 대기 시 메모리 상주 부담을 피함. |
| **추론 흐름** | 이미지 경로 리스트를 순차 순회, `model.predict()` → `xywhn`/`cls` 추출 → 정규화 bbox로 변환 후 YOLO .txt 형식으로 저장. | 구현 단순성·디버깅 용이; 대량 처리 시 배치/비동기 확장 여지는 문서 또는 주석으로 명시 가능. |
| **파이프라인 위치** | API `POST /api/dataset/{id}/auto-label` → `run_yoloworld_labeling()` → `write_yolo_label` / `write_data_yaml`. | “수집 완료 → AI 라벨 생성 → 저장” 단계를 API 한 번 호출로 묶어 워크플로를 단순화. |
| **환경·네트워크** | 선택적 SSL 검증 완화. | 자체서명/프록시 환경에서 모델 다운로드가 되도록 설정 가능. |
| **견고성·품질** | 이미지 단위 try/except, 실패 시 해당 이미지만 빈 라벨·나머지 계속. `conf_threshold`는 API 파라미터로 노출. | 부분 실패 시에도 데이터셋 전체 생산성을 유지; 검출 품질은 사용자가 임계값으로 조절. |

**요약**: 요청 단위 모델 로드 → 클래스 설정 → 이미지별 동기 추론 → YOLO .txt·data.yaml 저장. 수집·라벨·저장을 하나의 오케스트레이션으로 구성했습니다.

## 기술 스택

- **백엔드**: Python 3.x, FastAPI, Uvicorn — API 우선 설계, 비동기·문서화 활용.
- **AI·비전**: Ultralytics, YOLO-World(zero-shot 클래스 지정), OpenCV — 학습 파이프라인과 동일 생태계.
- **프론트**: Vue, 빌드 산출물을 FastAPI에서 서빙 — 단일 배포 단위로 운영 가능.

의존성은 [requirements.txt](requirements.txt) 기준입니다.

## 빠른 시작

- **설치**: `pip install -r requirements.txt`, 프론트는 `cd frontend && npm install`
- **실행**: **`./run.sh`** 권장. API(8081)와 Vue dev(8100)를 한 번에 가동하며, cwd를 프로젝트 루트로 맞춤.
- **접속**: `http://localhost:8100` (UI), `http://localhost:8081/docs` (API 문서)
- **수동 실행**: 프로젝트 루트에서 `uvicorn main:app --host 0.0.0.0 --port 8081`. 포트·CORS는 [docs/API_AND_DEV_COMPATIBILITY.md](docs/API_AND_DEV_COMPATIBILITY.md) 참고.
- **프론트 빌드**: `frontend/`에서 `npm run build` 시 루트 `/` 에서 Vue 앱 서빙 가능.

## API·문서

- API: `/docs`, `/redoc` (실행 중인 API 포트 기준)
- 설계·스타일: [docs/DESIGN.md](docs/DESIGN.md), [docs/STYLE.md](docs/STYLE.md)
- **데이터셋 워크플로**(업로드 → 분석 → 라벨링·검수 → 학습): [docs/DATASET_WORKFLOW.md](docs/DATASET_WORKFLOW.md)
- **API·개발 환경 호환**(CORS, 데이터셋 경로, 이미지 응답, SSL 등 재발 방지): [docs/API_AND_DEV_COMPATIBILITY.md](docs/API_AND_DEV_COMPATIBILITY.md)
- **라벨 편집 화면 주의사항**: [docs/LABEL_EDIT_NOTES.md](docs/LABEL_EDIT_NOTES.md)

## 프로젝트 방향

“수집 → AI 라벨링 → 검수 → YOLO 데이터셋” 워크플로를 한 곳에서 관리하는 솔루션으로 확장·개선 중입니다.
