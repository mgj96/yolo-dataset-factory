"""데이터셋 저장·경로 유틸. YOLO 형식(images/ + labels/) 구조."""
import json
import logging
import uuid
from pathlib import Path
from typing import Any, Optional

import yaml

from config import DATASET_ROOT

# YOLO 레이블 한 줄: (class_index, x_center, y_center, width, height) 정규화 0~1
YoloBox = tuple[int, float, float, float, float]

logger = logging.getLogger(__name__)


def get_dataset_images_dir(dataset_id: str) -> Path:
    """데이터셋의 images 디렉터리 경로를 반환. 없으면 생성."""
    path = DATASET_ROOT / _sanitize_dataset_id(dataset_id) / "images"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_dataset_labels_dir(dataset_id: str) -> Path:
    """데이터셋의 labels 디렉터리 경로를 반환. 없으면 생성."""
    path = DATASET_ROOT / _sanitize_dataset_id(dataset_id) / "labels"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _sanitize_dataset_id(dataset_id: str) -> str:
    """dataset_id에서 경로로 사용 불가 문자 제거."""
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in dataset_id)
    return safe or "default"


def create_session_id() -> str:
    """업로드 진입 시 사용할 새 세션 ID 생성. 세션은 dataset_id와 동일한 저장 구조를 사용한다."""
    return "session_" + uuid.uuid4().hex[:12]


def list_dataset_ids() -> list[str]:
    """등록된 데이터셋 ID 목록 반환. DATASET_ROOT 직하위 중 images 서브디렉터리가 있는 것만."""
    if not DATASET_ROOT.exists():
        return []
    result = []
    for path in DATASET_ROOT.iterdir():
        if path.is_dir() and (path / "images").is_dir():
            result.append(path.name)
    return sorted(result)


def save_frame_to_dataset(
    image_bytes: bytes,
    dataset_id: str,
    prefix: Optional[str] = None,
    extension: str = ".jpg",
) -> Path:
    """
    이미지 바이트를 데이터셋 images 디렉터리에 저장.
    파일명: {prefix}_{uuid}{extension} 또는 {uuid}{extension}
    """
    images_dir = get_dataset_images_dir(dataset_id)
    name = (prefix or "") + "_" + uuid.uuid4().hex[:12] + extension
    file_path = images_dir / name
    file_path.write_bytes(image_bytes)
    logger.debug("저장 완료: %s", file_path)
    return file_path


def list_saved_images(dataset_id: str) -> list[str]:
    """저장된 이미지 파일명 목록 반환 (images 디렉터리 기준)."""
    images_dir = DATASET_ROOT / _sanitize_dataset_id(dataset_id) / "images"
    if not images_dir.exists():
        return []
    return sorted(p.name for p in images_dir.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png"))


def read_yolo_label(dataset_id: str, image_stem: str) -> str:
    """이미지 stem에 대응하는 레이블 파일 내용 반환. 없으면 빈 문자열."""
    labels_dir = get_dataset_labels_dir(dataset_id)
    path = labels_dir / f"{image_stem}.txt"
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def write_yolo_label_raw(dataset_id: str, image_stem: str, content: str) -> Path:
    """레이블 파일 원문을 그대로 저장 (검수 후 업로드용)."""
    labels_dir = get_dataset_labels_dir(dataset_id)
    path = labels_dir / f"{image_stem}.txt"
    path.write_text(content.strip(), encoding="utf-8")
    logger.debug("레이블 원문 저장: %s", path)
    return path


def write_yolo_label(
    dataset_id: str,
    image_stem: str,
    boxes: list[YoloBox],
) -> Path:
    """
    이미지 stem에 대응하는 YOLO 형식 레이블 파일을 labels/에 저장.
    형식: 한 줄당 'class_index x_center y_center width height' (정규화 0~1).
    객체가 없으면 빈 파일을 쓴다.
    """
    labels_dir = get_dataset_labels_dir(dataset_id)
    path = labels_dir / f"{image_stem}.txt"
    lines = [
        f"{cls_idx} {x_c:.6g} {y_c:.6g} {w:.6g} {h:.6g}"
        for cls_idx, x_c, y_c, w, h in boxes
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    logger.debug("레이블 저장: %s (%d boxes)", path, len(boxes))
    return path


def _label_meta_path(dataset_id: str, image_stem: str) -> Path:
    """레이블 메타데이터 JSON 파일 경로 (labels/{stem}.json)."""
    return get_dataset_labels_dir(dataset_id) / f"{image_stem}.json"


def read_label_meta(dataset_id: str, image_stem: str) -> Optional[dict[str, Any]]:
    """
    이미지 stem에 대응하는 레이블 메타데이터(검수 상태·confidence 등) 반환.
    없으면 None.
    """
    path = _label_meta_path(dataset_id, image_stem)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("메타데이터 읽기 실패 %s: %s", path, e)
        return None


def write_label_meta(dataset_id: str, image_stem: str, meta: dict[str, Any]) -> Path:
    """
    레이블 메타데이터를 labels/{stem}.json 에 저장.
    meta: { "image": str, "status": "auto_labeled"|"reviewed"|"manual_labeled", "reviewer"?: str, "objects": [...] }
    """
    path = _label_meta_path(dataset_id, image_stem)
    path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.debug("메타데이터 저장: %s", path)
    return path


def get_dataset_root(dataset_id: str) -> Path:
    """데이터셋 루트 디렉터리 경로 반환 (data.yaml 등 배치용)."""
    return DATASET_ROOT / _sanitize_dataset_id(dataset_id)


def read_data_yaml_class_names(dataset_id: str) -> list[str]:
    """data.yaml 의 names 를 인덱스 순서대로 클래스명 리스트 반환. 없으면 []."""
    root = get_dataset_root(dataset_id)
    path = root / "data.yaml"
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    names = data.get("names") or {}
    if isinstance(names, dict):
        return [names.get(i, str(i)) for i in sorted(names.keys(), key=lambda x: int(x) if str(x).isdigit() else x)]
    return list(names) if isinstance(names, list) else []


def write_data_yaml(
    dataset_id: str,
    class_names: list[str],
    train_path: str = "images",
    val_path: Optional[str] = None,
) -> Path:
    """
    Ultralytics dataset.yaml 구조로 data.yaml 생성.
    path: 데이터셋 루트(절대 경로), train/val: path 기준 상대 경로, names: 0부터 클래스명.
    """
    root = get_dataset_root(dataset_id)
    root.mkdir(parents=True, exist_ok=True)
    val = val_path if val_path is not None else train_path
    data = {
        "path": str(root.resolve()),
        "train": train_path,
        "val": val,
        "names": {i: name for i, name in enumerate(class_names)},
    }
    path = root / "data.yaml"
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    logger.info("data.yaml 생성: %s (classes=%d)", path, len(class_names))
    return path
