"""
YOLOWorld 기반 자동 레이블링.
클래스명 리스트 + 이미지 경로 → 정규화된 YOLO 형식 bbox 반환.
"""
import logging
import ssl
import urllib.request
from pathlib import Path
from typing import Any

import config
from dataset_io import YoloBox

# (class_index, x_c, y_c, w, h, confidence) — 메타데이터·검수용
YoloBoxWithConf = tuple[int, float, float, float, float, float]

logger = logging.getLogger(__name__)


def _make_ssl_no_verify_context() -> ssl.SSLContext:
    """검증 비활성화 SSL 컨텍스트 (캐시/기본값 의존 없이 직접 생성)."""
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _install_urllib_no_verify_opener() -> None:
    """urllib 전역 opener를 SSL 검증 없이 HTTPS 요청하도록 교체. CLIP 등 urlopen 사용처에 적용."""
    ctx = _make_ssl_no_verify_context()
    urllib.request.install_opener(urllib.request.build_opener(urllib.request.HTTPSHandler(context=ctx)))


def _apply_ssl_no_verify() -> None:
    """자체서명/프록시 환경: SSL 검증 비활성화. 모듈 로드 시 + run_yoloworld_labeling 진입 시 적용."""
    if config.SSL_VERIFY_FOR_DOWNLOADS:
        return
    ssl._create_default_https_context = ssl._create_unverified_context
    _install_urllib_no_verify_opener()


_apply_ssl_no_verify()


def _predict_and_boxes(
    model: Any,
    image_path: Path,
    conf_threshold: float = 0.25,
) -> list[YoloBoxWithConf]:
    """단일 이미지 추론 후 정규화된 (class_index, x_c, y_c, w, h, confidence) 리스트 반환."""
    results = model.predict(str(image_path), conf=conf_threshold, verbose=False)
    if not results:
        return []
    r = results[0]
    if r.boxes is None or len(r.boxes) == 0:
        return []
    xywhn = r.boxes.xywhn
    cls_ids = r.boxes.cls
    confs = getattr(r.boxes, "conf", None)
    if xywhn is None:
        return []
    try:
        import torch
        if isinstance(xywhn, torch.Tensor):
            xywhn = xywhn.cpu().numpy()
        if isinstance(cls_ids, torch.Tensor):
            cls_ids = cls_ids.cpu().numpy()
        if confs is not None and isinstance(confs, torch.Tensor):
            confs = confs.cpu().numpy()
    except Exception:
        pass
    boxes: list[YoloBoxWithConf] = []
    for i in range(len(xywhn)):
        x_c, y_c, w, h = float(xywhn[i, 0]), float(xywhn[i, 1]), float(xywhn[i, 2]), float(xywhn[i, 3])
        c = int(cls_ids[i]) if cls_ids is not None else 0
        conf = float(confs[i]) if confs is not None and i < len(confs) else 0.0
        x_c = max(0.0, min(1.0, x_c))
        y_c = max(0.0, min(1.0, y_c))
        w = max(0.0, min(1.0, w))
        h = max(0.0, min(1.0, h))
        boxes.append((c, x_c, y_c, w, h, conf))
    return boxes


def run_yoloworld_labeling(
    image_paths: list[Path],
    class_names: list[str],
    model_name: str = "yolov8s-worldv2.pt",
    conf_threshold: float = 0.25,
) -> dict[str, list[YoloBoxWithConf]]:
    """
    이미지 경로 목록에 대해 YOLOWorld 추론 후 stem -> (class_index, x_c, y_c, w, h, confidence) 리스트 반환.
    class_names 순서가 클래스 인덱스 0, 1, ... 과 대응한다.
    """
    from ultralytics import YOLO

    if not class_names:
        return {p.stem: [] for p in image_paths}

    model = YOLO(model_name)
    # CLIP _download 내부에서 urllib.request.urlopen 호출. 해당 호출 시에만 no-verify 적용되도록 _download 실행 구간에서 urlopen 일시 교체.
    if not config.SSL_VERIFY_FOR_DOWNLOADS:
        logger.info("SSL 검증 비활성화: clip 다운로드 구간에서 no-verify 적용.")
        _install_urllib_no_verify_opener()
        try:
            import clip.clip as _clip_mod
            _orig_download = _clip_mod._download
            _orig_urlopen = urllib.request.urlopen
            def _patched_download(url, download_root=None):
                def _wrapped_urlopen(req, *a, **kw):
                    _install_urllib_no_verify_opener()
                    return _orig_urlopen(req, *a, **kw)
                urllib.request.urlopen = _wrapped_urlopen
                try:
                    return _orig_download(url, download_root)
                finally:
                    urllib.request.urlopen = _orig_urlopen
            _clip_mod._download = _patched_download
        except Exception as e:
            logger.warning("clip 모듈 패치 스킵: %s", e)
        model.set_classes(class_names)
    else:
        logger.info("SSL 검증 활성화 상태. 자체서명/프록시 오류 시 run.sh에서 export YOLO_DATASET_FACTORY_SSL_VERIFY=0 주석 해제 후 서버 재시작.")
        model.set_classes(class_names)

    out: dict[str, list[YoloBoxWithConf]] = {}
    for path in image_paths:
        if not path.exists():
            logger.warning("이미지 없음: %s", path)
            out[path.stem] = []
            continue
        try:
            boxes = _predict_and_boxes(model, path, conf_threshold=conf_threshold)
            out[path.stem] = boxes
        except Exception as e:
            logger.exception("YOLOWorld 추론 실패 %s: %s", path, e)
            out[path.stem] = []
    return out
