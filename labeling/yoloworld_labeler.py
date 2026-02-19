"""
YOLOWorld 기반 자동 레이블링.
클래스명 리스트 + 이미지 경로 → 정규화된 YOLO 형식 bbox 반환.
"""
import logging
import os
import ssl
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import config
from dataset_io import YoloBox

logger = logging.getLogger(__name__)


def _install_socks_proxy_if_set() -> None:
    """HTTPS_PROXY/ALL_PROXY가 socks5h:// 이면 urllib이 SSH 터널 등 SOCKS로 나가도록 설정. SSL 검증 유지."""
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("ALL_PROXY") or ""
    proxy = proxy.strip()
    if not proxy.lower().startswith("socks5"):
        return
    try:
        from urllib.request import build_opener, install_opener

        import socks

        try:
            from sockshandler import SocksiPyHandler
        except ImportError:
            from socks.sockshandler import SocksiPyHandler

        parsed = urlparse(proxy)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or 1080
        opener = build_opener(SocksiPyHandler(socks.SOCKS5, host, port))
        install_opener(opener)
        logger.info("다운로드 프록시 적용: socks5://%s:%s (SSL 검증 유지)", host, port)
    except Exception as e:
        logger.warning("SOCKS 프록시 설정 실패(%s), 기본 연결 사용: %s", proxy, e)


def _predict_and_boxes(
    model: Any,
    image_path: Path,
    conf_threshold: float = 0.25,
) -> list[YoloBox]:
    """단일 이미지 추론 후 정규화된 (class_index, x_c, y_c, w, h) 리스트 반환."""
    results = model.predict(str(image_path), conf=conf_threshold, verbose=False)
    if not results:
        return []
    r = results[0]
    if r.boxes is None or len(r.boxes) == 0:
        return []
    # xywhn: (N, 4) normalized; cls: (N,) class index
    xywhn = r.boxes.xywhn
    cls_ids = r.boxes.cls
    if xywhn is None:
        return []
    try:
        import torch
        if isinstance(xywhn, torch.Tensor):
            xywhn = xywhn.cpu().numpy()
        if isinstance(cls_ids, torch.Tensor):
            cls_ids = cls_ids.cpu().numpy()
    except Exception:
        pass
    boxes: list[YoloBox] = []
    for i in range(len(xywhn)):
        x_c, y_c, w, h = float(xywhn[i, 0]), float(xywhn[i, 1]), float(xywhn[i, 2]), float(xywhn[i, 3])
        c = int(cls_ids[i]) if cls_ids is not None else 0
        # 클램프 0~1
        x_c = max(0.0, min(1.0, x_c))
        y_c = max(0.0, min(1.0, y_c))
        w = max(0.0, min(1.0, w))
        h = max(0.0, min(1.0, h))
        boxes.append((c, x_c, y_c, w, h))
    return boxes


def run_yoloworld_labeling(
    image_paths: list[Path],
    class_names: list[str],
    model_name: str = "yolov8s-worldv2.pt",
    conf_threshold: float = 0.25,
) -> dict[str, list[YoloBox]]:
    """
    이미지 경로 목록에 대해 YOLOWorld 추론 후 stem -> YoloBox 리스트 반환.
    class_names 순서가 클래스 인덱스 0, 1, ... 과 대응한다.
    """
    # SSH 터널 등 SOCKS 프록시가 있으면 먼저 적용 (SSL 검증 유지, 0/1 전환 불필요)
    _install_socks_proxy_if_set()
    if not config.SSL_VERIFY_FOR_DOWNLOADS:
        # SOCKS 미사용 시에만: 자체서명/프록시 환경에서 SSL 검증 생략 (YOLO_DATASET_FACTORY_SSL_VERIFY=0)
        ssl._create_default_https_context = ssl._create_unverified_context

    from ultralytics import YOLO

    if not class_names:
        return {p.stem: [] for p in image_paths}

    model = YOLO(model_name)
    model.set_classes(class_names)

    out: dict[str, list[YoloBox]] = {}
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
