"""자동 레이블링 프로바이더. YOLOWorld 등으로 사전 레이블 생성 후 검수용."""
from labeling.yoloworld_labeler import run_yoloworld_labeling

__all__ = ["run_yoloworld_labeling"]
