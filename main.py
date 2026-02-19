"""
YOLO 데이터셋 팩토리 FastAPI 앱.
입력: 이미지 업로드, 동영상 업로드(프레임 추출), WebRTC 캡처 프레임.
출력: YOLO 형식(images/ + labels/ + data.yaml) 데이터셋.
"""
import logging

from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.responses import FileResponse

import config
from dataset_io import (
    get_dataset_images_dir,
    get_dataset_root,
    list_dataset_ids,
    list_saved_images,
    read_data_yaml_class_names,
    read_yolo_label,
    save_frame_to_dataset,
    write_data_yaml,
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
    dataset_id: str = Form("default", description="데이터셋 ID (동일한 수집 세션에서 동일 값 사용 권장)"),
) -> FramesResponse:
    """
    이미지(프레임)를 데이터셋에 추가.
    동영상에서 추출한 프레임 또는 WebRTC 브라우저 캡처 이미지를 전송할 때 사용.
    """
    if not files:
        raise HTTPException(status_code=400, detail="files 비어 있음")
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
        path = save_frame_to_dataset(data, dataset_id, extension=ext)
        saved.append(FrameSaveResult(filename=path.name, path=str(path)))
    return FramesResponse(dataset_id=dataset_id, saved=saved)


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
    return FileResponse(str(path), media_type=None)

@app_router.get(
    "/dataset/{dataset_id}/info",
    responses={200: {"description": "data.yaml 기반 클래스명 등"}},
)
async def get_dataset_info(dataset_id: str):
    """데이터셋 정보 (클래스명 등). data.yaml 이 없으면 class_names 는 []."""
    class_names = read_data_yaml_class_names(dataset_id)
    return {"dataset_id": dataset_id, "class_names": class_names}


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

    image_paths = [images_dir / n for n in names]
    stem_to_boxes = run_yoloworld_labeling(
        image_paths,
        body.class_names,
        conf_threshold=body.conf_threshold,
    )

    for stem, boxes in stem_to_boxes.items():
        write_yolo_label(dataset_id, stem, boxes)

    yaml_path = write_data_yaml(dataset_id, body.class_names)

    return AutoLabelResponse(
        dataset_id=dataset_id,
        labeled_count=len(stem_to_boxes),
        class_names=body.class_names,
        data_yaml_path=str(yaml_path),
    )


# ---------- 검수 워크플로: 레이블 조회·편집 ----------


class LabelStemItem(BaseModel):
    """레이블 파일 한 건 (stem만, 이미지와 1:1)."""
    stem: str


@app_router.get(
    "/dataset/{dataset_id}/labels",
    response_model=list[LabelStemItem],
    responses={404: {"description": "데이터셋 없음"}},
)
async def list_labels(dataset_id: str) -> list[LabelStemItem]:
    """데이터셋 내 레이블 파일 stem 목록 (images 기준, .txt 존재 여부 무관)."""
    names = list_saved_images(dataset_id)
    if not names:
        raise HTTPException(status_code=404, detail=f"데이터셋에 이미지 없음: {dataset_id}")
    stems = [Path(n).stem for n in names]
    return [LabelStemItem(stem=s) for s in stems]


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


# ---------- 앱 마운트 ----------

# 프론트엔드 빌드 산출물 (frontend/dist). 없으면 / 에서 JSON 안내만 반환
FRONTEND_DIST = Path(__file__).resolve().parent / "frontend" / "dist"
FRONTEND_INDEX = FRONTEND_DIST / "index.html"

app = FastAPI(
    title="YOLO Dataset Factory",
    description="영상/이미지 수집 → YOLO 형식 데이터셋 생성",
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
