"""
YOLO 데이터셋 팩토리 FastAPI 앱.
입력: 이미지 업로드, 동영상 업로드(프레임 추출), WebRTC 캡처 프레임.
출력: YOLO 형식(images/ + labels/ + data.yaml) 데이터셋.
"""
import logging

from pathlib import Path
from typing import Optional

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import FileResponse

import config
from dataset_io import (
    create_session_id,
    get_dataset_images_dir,
    get_dataset_root,
    list_dataset_ids,
    list_saved_images,
    read_data_yaml_class_names,
    read_label_meta,
    read_yolo_label,
    save_frame_to_dataset,
    write_data_yaml,
    write_label_meta,
    write_yolo_label,
    write_yolo_label_raw,
)
from labeling.yoloworld_labeler import run_yoloworld_labeling

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app_router = APIRouter(prefix="/api", tags=["dataset"])


# ---------- 데이터셋 목록 ----------


class DatasetsResponse(BaseModel):
    """등록된 데이터셋 ID 목록."""
    dataset_ids: list[str]


@app_router.get(
    "/datasets",
    response_model=DatasetsResponse,
)
async def list_datasets() -> DatasetsResponse:
    """등록된 데이터셋 ID 목록 조회 (images 디렉터리가 존재하는 것만)."""
    return DatasetsResponse(dataset_ids=list_dataset_ids())


# ---------- 공통 이미지 수집 진입점 ----------


class FrameSaveResult(BaseModel):
    """프레임 저장 결과 한 건."""
    filename: str
    path: str


class FramesResponse(BaseModel):
    """프레임 업로드 응답."""
    dataset_id: str
    saved: list[FrameSaveResult]


@app_router.post(
    "/dataset/frames",
    response_model=FramesResponse,
    responses={413: {"description": "파일 크기 초과"}, 400: {"description": "잘못된 요청"}},
)
async def upload_frames(
    files: list[UploadFile] = File(..., description="이미지 파일 목록"),
    dataset_id: Optional[str] = Form(None, description="데이터셋/세션 ID. 비우거나 생략 시 새 세션 생성"),
    session: Optional[bool] = Form(None, description="true면 새 세션 생성 후 업로드"),
) -> FramesResponse:
    """
    이미지(프레임)를 데이터셋 또는 세션에 추가.
    dataset_id 없음 또는 session=true 이면 새 세션 ID를 생성해 해당 세션에 저장한다.
    """
    if not files:
        raise HTTPException(status_code=400, detail="files 비어 있음")
    target_id = dataset_id if (dataset_id and dataset_id.strip()) and not session else create_session_id()
    saved: list[FrameSaveResult] = []
    for f in files:
        content_type = f.content_type or ""
        if not content_type.startswith("image/"):
            raise HTTPException(
                status_code=400,
                detail=f"이미지가 아님: {f.filename} (content-type: {content_type})",
            )
        data = await f.read()
        if len(data) > config.MAX_IMAGE_SIZE_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"파일 크기 초과: {f.filename} (최대 {config.MAX_IMAGE_SIZE_BYTES} bytes)",
            )
        ext = ".jpg"
        if "png" in content_type:
            ext = ".png"
        path = save_frame_to_dataset(data, target_id, extension=ext)
        saved.append(FrameSaveResult(filename=path.name, path=str(path)))
    return FramesResponse(dataset_id=target_id, saved=saved)


class ImageItem(BaseModel):
    """이미지 파일 한 건."""
    filename: str


class DatasetImagesResponse(BaseModel):
    """데이터셋 내 이미지 목록 응답."""
    dataset_id: str
    images: list[ImageItem]


@app_router.get(
    "/dataset/{dataset_id}/images",
    response_model=DatasetImagesResponse,
)
async def list_dataset_images(dataset_id: str) -> DatasetImagesResponse:
    """
    데이터셋에 업로드된 이미지 목록 조회.
    이미지가 없으면 빈 배열 반환.
    """
    names = list_saved_images(dataset_id)
    return DatasetImagesResponse(
        dataset_id=dataset_id,
        images=[ImageItem(filename=n) for n in names],
    )


@app_router.get(
    "/dataset/{dataset_id}/images/{filename}",
    responses={404: {"description": "이미지 없음"}},
)
async def serve_dataset_image(dataset_id: str, filename: str):
    """데이터셋 이미지 파일 스트리밍 (라벨링 UI 등에서 표시용)."""
    safe_name = Path(filename).name
    if not safe_name or safe_name != filename:
        raise HTTPException(status_code=400, detail="invalid filename")
    images_dir = get_dataset_images_dir(dataset_id)
    path = images_dir / safe_name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="image not found")
    suffix = path.suffix.lower()
    media_type = {"": None, ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}.get(suffix, None)
    return FileResponse(str(path), media_type=media_type)

@app_router.get(
    "/dataset/{dataset_id}/info",
    responses={200: {"description": "data.yaml 기반 클래스명 등"}},
)
async def get_dataset_info(
    dataset_id: str,
    refined_only: bool = Query(False, description="true면 정제된(reviewed/manual_labeled) 이미지 수·stem 목록 포함"),
):
    """데이터셋 정보 (클래스명, data.yaml 경로, 학습 CLI 예시). refined_only 시 정제된 데이터 요약 추가."""
    class_names = read_data_yaml_class_names(dataset_id)
    root = get_dataset_root(dataset_id)
    yaml_path = root / "data.yaml"
    data_yaml_path: Optional[str] = str(yaml_path.resolve()) if yaml_path.exists() else None
    train_command_example: Optional[str] = None
    if data_yaml_path:
        train_command_example = f"yolo train data={data_yaml_path} model=yolov8n.pt epochs=100"
    out = {
        "dataset_id": dataset_id,
        "class_names": class_names,
        "data_yaml_path": data_yaml_path,
        "train_command_example": train_command_example,
    }
    if not class_names:
        out["default_class_names"] = config.ANALYZE_CANDIDATE_CLASSES
    if refined_only:
        names = list_saved_images(dataset_id)
        refined_stems: list[str] = []
        for n in names:
            stem = Path(n).stem
            meta = read_label_meta(dataset_id, stem)
            status = meta.get("status") if meta else None
            if status in ("reviewed", "manual_labeled"):
                refined_stems.append(stem)
        out["refined_count"] = len(refined_stems)
        out["refined_stems"] = refined_stems
    return out


class SetClassesRequest(BaseModel):
    """수동 라벨링용 클래스명 설정. data.yaml만 생성하며 추론은 하지 않음."""
    class_names: list[str]


@app_router.put(
    "/dataset/{dataset_id}/classes",
    responses={400: {"description": "class_names 비어 있음"}},
)
async def set_dataset_classes(dataset_id: str, body: SetClassesRequest) -> dict:
    """데이터셋 클래스명만 설정. 자동 라벨 없이 수동 라벨링을 할 때 사용."""
    if not body.class_names:
        raise HTTPException(status_code=400, detail="class_names 비어 있음")
    yaml_path = write_data_yaml(dataset_id, body.class_names)
    train_command_example = f"yolo train data={yaml_path.resolve()} model=yolov8n.pt epochs=100"
    return {
        "dataset_id": dataset_id,
        "class_names": body.class_names,
        "data_yaml_path": str(yaml_path),
        "train_command_example": train_command_example,
    }


# ---------- 반자동 레이블링 ----------


class AutoLabelRequest(BaseModel):
    """자동 레이블 요청 body."""
    class_names: list[str]
    provider: str = "yoloworld"
    conf_threshold: float = 0.25


class AutoLabelResponse(BaseModel):
    """자동 레이블 응답."""
    dataset_id: str
    labeled_count: int
    class_names: list[str]
    data_yaml_path: str
    total_boxes: int = 0
    images_with_boxes: int = 0
    train_command_example: Optional[str] = None


class AnalyzeRequest(BaseModel):
    """분석(업로드 후 1회 추론) 요청. 후보 클래스로 추론 후 검출된 클래스만 제안."""
    candidate_class_names: Optional[list[str]] = None  # None이면 config.ANALYZE_CANDIDATE_CLASSES 사용
    conf_threshold: float = 0.25


class AnalyzeResponse(BaseModel):
    """분석 응답. 제안 클래스·설정과 함께 라벨·메타가 저장됨."""
    dataset_id: str
    suggested_class_names: list[str]
    suggested_conf_threshold: float
    labeled_count: int
    total_boxes: int
    images_with_boxes: int
    data_yaml_path: str
    train_command_example: Optional[str] = None


@app_router.post(
    "/dataset/{dataset_id}/analyze",
    response_model=AnalyzeResponse,
    responses={404: {"description": "데이터셋 또는 이미지 없음"}, 400: {"description": "잘못된 요청"}},
)
async def analyze_dataset(
    dataset_id: str,
    body: AnalyzeRequest,
) -> AnalyzeResponse:
    """
    업로드된 이미지에 대해 1회 추론 후 검출된 클래스만 제안하고, 초기 라벨·메타를 저장.
    candidate_class_names 가 비어 있으면 config.ANALYZE_CANDIDATE_CLASSES 를 사용한다.
    """
    class_names = body.candidate_class_names or config.ANALYZE_CANDIDATE_CLASSES
    if not class_names:
        raise HTTPException(status_code=400, detail="후보 클래스가 비어 있음 (candidate_class_names 또는 ANALYZE_CANDIDATE_CLASSES)")

    images_dir = get_dataset_images_dir(dataset_id)
    names = list_saved_images(dataset_id)
    if not names:
        raise HTTPException(
            status_code=404,
            detail=f"데이터셋에 이미지가 없음: {dataset_id}",
        )

    try:
        image_paths = [images_dir / n for n in names]
        stem_to_boxes = run_yoloworld_labeling(
            image_paths,
            class_names,
            conf_threshold=body.conf_threshold,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"분석 실행 실패: {e!s}")

    detected_class_indices: set[int] = set()
    total_boxes = 0
    for boxes in stem_to_boxes.values():
        total_boxes += len(boxes)
        for b in boxes:
            detected_class_indices.add(int(b[0]))
    suggested_class_names = [class_names[i] for i in sorted(detected_class_indices) if 0 <= i < len(class_names)]
    if not suggested_class_names:
        suggested_class_names = class_names[:1]

    for stem, boxes in stem_to_boxes.items():
        write_yolo_label(
            dataset_id, stem, [(b[0], b[1], b[2], b[3], b[4]) for b in boxes]
        )
        image_filename = next((n for n in names if Path(n).stem == stem), f"{stem}.jpg")
        write_label_meta(
            dataset_id,
            stem,
            {
                "image": image_filename,
                "status": "auto_labeled",
                "objects": [
                    {
                        "class_id": b[0],
                        "bbox": [b[1], b[2], b[3], b[4]],
                        "confidence": b[5],
                        "source": "yoloworld",
                    }
                    for b in boxes
                ],
            },
        )

    yaml_path = write_data_yaml(dataset_id, suggested_class_names)
    images_with_boxes = sum(1 for boxes in stem_to_boxes.values() if len(boxes) > 0)
    train_command_example = f"yolo train data={yaml_path.resolve()} model=yolov8n.pt epochs=100"

    return AnalyzeResponse(
        dataset_id=dataset_id,
        suggested_class_names=suggested_class_names,
        suggested_conf_threshold=body.conf_threshold,
        labeled_count=len(stem_to_boxes),
        total_boxes=total_boxes,
        images_with_boxes=images_with_boxes,
        data_yaml_path=str(yaml_path),
        train_command_example=train_command_example,
    )


@app_router.post(
    "/dataset/{dataset_id}/auto-label",
    response_model=AutoLabelResponse,
    responses={404: {"description": "데이터셋 또는 이미지 없음"}, 400: {"description": "잘못된 요청"}},
)
async def auto_label_dataset(
    dataset_id: str,
    body: AutoLabelRequest,
) -> AutoLabelResponse:
    """
    데이터셋 이미지에 대해 자동 레이블 생성 후 labels/*.txt 및 data.yaml 저장.
    반자동 워크플로: 생성된 레이블은 검수·수정 후 사용 권장.
    """
    if not body.class_names:
        raise HTTPException(status_code=400, detail="class_names 비어 있음")
    if body.provider != "yoloworld":
        raise HTTPException(
            status_code=400,
            detail=f"지원하지 않는 provider: {body.provider}. 현재 지원: yoloworld",
        )

    images_dir = get_dataset_images_dir(dataset_id)
    names = list_saved_images(dataset_id)
    if not names:
        raise HTTPException(
            status_code=404,
            detail=f"데이터셋에 이미지가 없음: {dataset_id}",
        )

    try:
        image_paths = [images_dir / n for n in names]
        stem_to_boxes = run_yoloworld_labeling(
            image_paths,
            body.class_names,
            conf_threshold=body.conf_threshold,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"자동 라벨 실행 실패: {e!s}")

    total_boxes = 0
    for stem, boxes in stem_to_boxes.items():
        # YOLO .txt (5열만)
        write_yolo_label(
            dataset_id, stem, [(b[0], b[1], b[2], b[3], b[4]) for b in boxes]
        )
        total_boxes += len(boxes)
        # 메타데이터 (검수 상태·confidence·source)
        image_filename = next((n for n in names if Path(n).stem == stem), f"{stem}.jpg")
        write_label_meta(
            dataset_id,
            stem,
            {
                "image": image_filename,
                "status": "auto_labeled",
                "objects": [
                    {
                        "class_id": b[0],
                        "bbox": [b[1], b[2], b[3], b[4]],
                        "confidence": b[5],
                        "source": "yoloworld",
                    }
                    for b in boxes
                ],
            },
        )

    yaml_path = write_data_yaml(dataset_id, body.class_names)
    images_with_boxes = sum(1 for boxes in stem_to_boxes.values() if len(boxes) > 0)
    train_command_example = f"yolo train data={yaml_path.resolve()} model=yolov8n.pt epochs=100"

    return AutoLabelResponse(
        dataset_id=dataset_id,
        labeled_count=len(stem_to_boxes),
        class_names=body.class_names,
        data_yaml_path=str(yaml_path),
        total_boxes=total_boxes,
        images_with_boxes=images_with_boxes,
        train_command_example=train_command_example,
    )


# ---------- 검수 워크플로: 레이블 조회·편집 ----------


class LabelStemItem(BaseModel):
    """레이블 파일 한 건 (stem, 검수 상태, bbox 개수·적합성 요약)."""
    stem: str
    status: Optional[str] = None  # "auto_labeled" | "reviewed" | "manual_labeled"
    bbox_count: int = 0
    confidence_avg: Optional[float] = None


def _bbox_count_from_label_content(content: str) -> int:
    """YOLO 레이블 원문에서 유효한 줄 수(bbox 개수) 반환."""
    return sum(1 for line in (content or "").strip().splitlines() if line.strip())


def _confidence_avg_from_meta(meta: Optional[dict]) -> Optional[float]:
    """메타 objects에서 confidence 평균 반환. 없으면 None."""
    if not meta:
        return None
    objects = meta.get("objects") or []
    confs = [o.get("confidence") for o in objects if isinstance(o.get("confidence"), (int, float))]
    if not confs:
        return None
    return sum(confs) / len(confs)


@app_router.get(
    "/dataset/{dataset_id}/labels",
    response_model=list[LabelStemItem],
    responses={404: {"description": "데이터셋 없음"}},
)
async def list_labels(
    dataset_id: str,
    refined_only: bool = Query(False, description="true면 검수 완료(reviewed/manual_labeled) stem만 반환"),
) -> list[LabelStemItem]:
    """데이터셋 내 레이블 stem 목록 및 검수 상태·bbox 개수·적합성 요약 (images 기준). refined_only 시 정제된 데이터만."""
    names = list_saved_images(dataset_id)
    if not names:
        raise HTTPException(status_code=404, detail=f"데이터셋에 이미지 없음: {dataset_id}")
    result: list[LabelStemItem] = []
    for n in names:
        stem = Path(n).stem
        meta = read_label_meta(dataset_id, stem)
        status = meta.get("status") if meta else None
        if refined_only and status not in ("reviewed", "manual_labeled"):
            continue
        content = read_yolo_label(dataset_id, stem)
        bbox_count = _bbox_count_from_label_content(content)
        confidence_avg = _confidence_avg_from_meta(meta)
        result.append(
            LabelStemItem(stem=stem, status=status, bbox_count=bbox_count, confidence_avg=confidence_avg)
        )
    return result


@app_router.get(
    "/dataset/{dataset_id}/labels/{stem}",
    responses={404: {"description": "레이블 없음"}},
)
async def get_label_content(dataset_id: str, stem: str) -> str:
    """단일 레이블 파일 내용 반환 (검수·다운로드용). 없으면 빈 문자열."""
    content = read_yolo_label(dataset_id, stem)
    return content


class LabelContentUpdate(BaseModel):
    """검수 후 레이블 본문 업로드."""
    content: str = ""


@app_router.put(
    "/dataset/{dataset_id}/labels/{stem}",
    responses={400: {"description": "잘못된 요청"}},
)
async def update_label_content(
    dataset_id: str,
    stem: str,
    body: LabelContentUpdate,
) -> dict:
    """검수 후 레이블 내용으로 덮어쓰기. content는 YOLO .txt 원문(한 줄당 class_index x_center y_center width height)."""
    path = write_yolo_label_raw(dataset_id, stem, body.content)
    return {"dataset_id": dataset_id, "stem": stem, "path": str(path)}


class LabelMetaUpdate(BaseModel):
    """레이블 메타데이터 업데이트 (검수 완료 등)."""
    status: Optional[str] = None  # "reviewed" | "manual_labeled"
    reviewer: Optional[str] = None
    objects: Optional[list[dict]] = None  # [{ class_id, bbox, confidence?, source? }]


@app_router.get(
    "/dataset/{dataset_id}/labels/{stem}/meta",
    responses={404: {"description": "메타데이터 없음"}},
)
async def get_label_meta(dataset_id: str, stem: str) -> dict:
    """단일 이미지 stem에 대한 레이블 메타데이터 (검수 상태·confidence 등). 없으면 404."""
    meta = read_label_meta(dataset_id, stem)
    if meta is None:
        raise HTTPException(status_code=404, detail="메타데이터 없음")
    return meta


@app_router.put(
    "/dataset/{dataset_id}/labels/{stem}/meta",
    responses={400: {"description": "잘못된 요청"}},
)
async def update_label_meta(
    dataset_id: str,
    stem: str,
    body: LabelMetaUpdate,
) -> dict:
    """레이블 메타데이터 갱신 (검수 완료 시 status=reviewed 등)."""
    names = list_saved_images(dataset_id)
    image_filename = next((n for n in names if Path(n).stem == stem), f"{stem}.jpg")
    existing = read_label_meta(dataset_id, stem) or {
        "image": image_filename,
        "status": "auto_labeled",
        "objects": [],
    }
    if body.status is not None:
        existing["status"] = body.status
    if body.reviewer is not None:
        existing["reviewer"] = body.reviewer
    if body.objects is not None:
        existing["objects"] = body.objects
    path = write_label_meta(dataset_id, stem, existing)
    return {"dataset_id": dataset_id, "stem": stem, "path": str(path)}


# ---------- 앱 마운트 ----------

# 프론트엔드 빌드 산출물 (frontend/dist). 없으면 / 에서 JSON 안내만 반환
FRONTEND_DIST = Path(__file__).resolve().parent / "frontend" / "dist"
FRONTEND_INDEX = FRONTEND_DIST / "index.html"

app = FastAPI(
    title="YOLO Dataset Factory",
    description="영상/이미지 수집 → YOLO 형식 데이터셋 생성",
)

# CORS: Vue dev(8100) 등에서 API(8081) 호출 시 브라우저 차단 방지
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8100", "http://localhost:8081", "http://localhost:5173", "http://127.0.0.1:8100", "http://127.0.0.1:8081", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(app_router)

# 정적 파일: 기존 static/, 프론트엔드 assets/
app.mount("/static", StaticFiles(directory="static"), name="static")
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")


@app.get("/")
async def root():
    """루트: frontend/dist 가 있으면 Vue 프론트엔드(index.html) 서빙, 없으면 JSON 안내."""
    if FRONTEND_INDEX.exists():
        return FileResponse(str(FRONTEND_INDEX), media_type="text/html")
    return {
        "message": "YOLO Dataset Factory",
        "docs": "/docs",
        "static": "/static/index.html",
        "ui_note": "프론트엔드: frontend/ 에서 npm run build 후 재시작하면 / 에서 제공됩니다.",
    }


@app.get("/health")
async def health():
    """헬스체크."""
    return {"status": "ok"}


# SPA 폴백: /api, /docs, /assets 등이 아닌 경로는 index.html (Vue Router용). /health 등은 위에서 처리.
RESERVED_PREFIXES = ("api", "docs", "openapi.json", "redoc", "health", "static", "assets")


@app.get("/{path:path}")
async def serve_spa(path: str):
    """API·문서가 아닌 경로는 Vue SPA index.html 로 서빙."""
    if path.split("/")[0] in RESERVED_PREFIXES or path.startswith("api/"):
        raise HTTPException(status_code=404, detail="Not Found")
    if FRONTEND_INDEX.exists():
        return FileResponse(str(FRONTEND_INDEX), media_type="text/html")
    raise HTTPException(status_code=404, detail="Not Found")
