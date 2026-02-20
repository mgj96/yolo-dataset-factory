# API·개발 환경 호환 가이드

기존 API와 프론트엔드가 계속 호환되도록, **발생했던 이슈 원인**과 **재발 방지 체크리스트**를 정리합니다.

---

## 1. 왜 호환이 깨졌는지 (원인 정리)

| 현상 | 원인 | 해결 요약 |
|------|------|-----------|
| **Failed to fetch** | Vue(8100) → API(8081) 크로스 오리진 요청에 백엔드가 CORS 헤더를 보내지 않음. 브라우저가 응답을 차단. | FastAPI에 `CORSMiddleware` 추가, 개발용 origin(8100/8081, localhost·127.0.0.1) 허용. |
| **데이터셋 목록이 비어 보임** | `DATASET_ROOT`를 `./datasets`로 두고 `resolve()`만 사용. 서버를 **다른 cwd**에서 실행하면 `./datasets`가 프로젝트 루트가 아닌 곳을 가리킴. | `config.py`에서 기본값을 **config 파일 기준 프로젝트 루트**의 `datasets`로 고정 (`Path(__file__).resolve().parent / "datasets"`). |
| **이미지(썸네일)가 안 보임** | `FileResponse(path, media_type=None)`. Content-Type 미설정 시 브라우저가 이미지를 이미지로 인식하지 못해 렌더 실패. | 이미지 응답 시 확장자별 `media_type` 지정 (`.png` → `image/png`, `.jpg`/`.jpeg` → `image/jpeg`). |
| **자동 라벨 실행 시 SSL 오류** | YOLO-World의 CLIP 다운로드가 `urllib.request.urlopen` 사용. 자체서명/프록시 인증서 환경에서 `CERTIFICATE_VERIFY_FAILED` 발생. | **기본값: SSL 비검증(0)**. `config.SSL_VERIFY_FOR_DOWNLOADS` 기본 0, `run.sh`에서도 `YOLO_DATASET_FACTORY_SSL_VERIFY=0` 적용. CLIP `_download` 호출 구간에서 urlopen을 no-verify opener로 일시 교체 (`yoloworld_labeler.py`). 검증 필요 시 `YOLO_DATASET_FACTORY_SSL_VERIFY=1` 로 실행. |

공통점: **실행 환경(origin, cwd, 응답 헤더)**에 대한 가정이 문서/코드에 없어, 환경이 조금만 달라져도 기존 API·UI와 호환이 깨짐.

---

## 2. 개발 환경의 전제 (반드시 유지할 것)

- **실행**: API·Vue는 `./run.sh`로 띄우는 것을 기본으로 함. `run.sh`는 프로젝트 루트로 `cd` 한 뒤 API(8081)·Vue(8100)를 기동하므로, **cwd = 프로젝트 루트**가 보장됨.
- **포트**: API `8081`, Vue dev `8100`. 프론트엔드는 `location.origin`의 포트를 8081로 바꿔 API_BASE를 만듦 (`api.js`). 포트 변경 시 CORS allow_origins와 프론트의 API_BASE(또는 `VITE_API_BASE`)를 함께 맞출 것.
- **CORS**: API는 **모든 응답**(JSON뿐 아니라 이미지·파일 포함)에 대해 개발용 origin을 허용해야 함. 미들웨어는 앱에 한 번만 추가하고, 새 엔드포인트도 동일 정책을 따르게 함.
- **데이터셋 경로**: `DATASET_ROOT` 기본값은 **실행 cwd가 아닌, config 파일 위치 기준** 프로젝트 루트의 `datasets`. 다른 경로를 쓰려면 `DATASET_ROOT` 환경 변수로만 오버라이드할 것.

---

## 3. 재발 방지 체크리스트

새 엔드포인트·프론트 호출·실행 방식 변경 시 아래를 확인하면 기존 API·UI와의 호환이 유지됩니다.

### 백엔드

| 확인 항목 | 설명 |
|-----------|------|
| **CORS** | 새 라우트만 추가한 경우, 기존 `CORSMiddleware`로 동일 origin 허용 적용되는지 확인. 미들웨어 제거/조건 분기 시 8100→8081 호출 실패하지 않는지 확인. |
| **파일/이미지 응답** | `FileResponse` 사용 시 **확장자별 `media_type`** 지정. (이미지: `image/png`, `image/jpeg` 등). `media_type=None`만 쓰지 않기. |
| **경로·데이터셋** | 파일/디렉터리 경로는 `config.DATASET_ROOT` 또는 `dataset_io` 유틸 사용. `./datasets` 등 cwd 의존 경로 직접 사용 금지. |

### 프론트엔드

| 확인 항목 | 설명 |
|-----------|------|
| **API 호출** | `fetchApi`·`uploadFrames` 등 공용 `api.js` 사용. API_BASE는 `api.js` 기준으로 한 곳에서만 결정. |
| **이미지 URL** | 데이터셋 이미지 표시는 `datasetImagesUrl(datasetId, filename)` 사용. 포트·경로 변경 시 해당 함수와 백엔드 라우트만 맞추면 됨. |

### 실행·배포

| 확인 항목 | 설명 |
|-----------|------|
| **서버 기동** | 가능하면 **항상 `./run.sh`**로 기동. 수동으로 uvicorn만 쓸 경우 **반드시 프로젝트 루트에서** 실행해 `DATASET_ROOT`가 의도한 `datasets/`를 가리키는지 확인. |
| **포트 변경** | 8081/8100을 바꿀 경우: `run.sh`, `config.SERVER_PORT`(또는 env), CORS `allow_origins`, 프론트 `API_BASE`(또는 `VITE_API_BASE`)를 함께 수정. |

---

## 4. 요약

- **CORS**: 개발 시 8100→8081 크로스 오리진이므로, API에서 개발용 origin을 허용해야 "Failed to fetch"가 나지 않음.
- **경로**: 데이터셋 루트는 **cwd에 의존하지 않도록** config/프로젝트 루트 기준으로 고정.
- **이미지 응답**: 파일 스트리밍 시 **Content-Type(media_type)**을 명시해 브라우저가 이미지를 정상 렌더하도록 함.
- **변경 시**: 새 API·실행 방식 추가 시 위 체크리스트로 한 번씩 점검하면 기존 API·UI와의 호환 재발을 줄일 수 있음.

이 문서는 [DESIGN.md](DESIGN.md), [DATASET_WORKFLOW.md](DATASET_WORKFLOW.md)와 함께 참고합니다.
