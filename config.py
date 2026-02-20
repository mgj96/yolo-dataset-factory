"""앱 설정. 데이터셋 루트, 업로드 제한 등."""
import os
from pathlib import Path

# 데이터셋 루트 디렉터리 (YOLO 형식: {root}/{dataset_id}/images/, labels/, data.yaml)
# 기본값은 config.py 기준 프로젝트 루트의 datasets (실행 cwd와 무관)
_PROJECT_ROOT = Path(__file__).resolve().parent
DATASET_ROOT: Path = Path(os.environ.get("DATASET_ROOT", str(_PROJECT_ROOT / "datasets"))).resolve()

# 서버 포트 (다른 메인 모듈과 충돌 방지용 기본 8081)
SERVER_PORT: int = int(os.environ.get("SERVER_PORT", "8081"))

# 이미지 업로드 최대 크기 (바이트). PLAN_VALUES 기준 10MB 참고
MAX_IMAGE_SIZE_BYTES: int = int(os.environ.get("MAX_IMAGE_SIZE_BYTES", 10 * 1024 * 1024))

# 동영상 업로드 최대 크기 (바이트). 500MB
MAX_VIDEO_SIZE_BYTES: int = int(os.environ.get("MAX_VIDEO_SIZE_BYTES", 500 * 1024 * 1024))

# 동영상 프레임 추출: N초마다 1장
FRAME_EXTRACT_INTERVAL_SEC: float = float(os.environ.get("FRAME_EXTRACT_INTERVAL_SEC", "1.0"))

# 허용 동영상 확장자
ALLOWED_VIDEO_EXTENSIONS: frozenset[str] = frozenset({".mp4", ".webm", ".avi", ".mov"})

# CLIP/YOLOWorld 등 원격 다운로드 시 SSL 검증. 기본값 0(비검증)으로 프록시·자체서명 환경에서도 통신 가능. 검증 필요 시 YOLO_DATASET_FACTORY_SSL_VERIFY=1
SSL_VERIFY_FOR_DOWNLOADS: bool = os.environ.get("YOLO_DATASET_FACTORY_SSL_VERIFY", "0").lower() in ("1", "true", "yes")

# 분석(analyze) 시 사용할 기본 후보 클래스. 쉼표 구분 문자열(환경변수) 또는 기본 목록. 검출된 클래스만 제안용으로 반환
_DEFAULT_CANDIDATE_CLASSES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
    "bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe",
    "backpack", "umbrella", "handbag", "tie", "suitcase", "bottle", "cup", "fork", "knife",
    "spoon", "bowl", "banana", "apple", "sandwich", "orange", "broccoli", "carrot", "pizza",
    "donut", "cake", "chair", "couch", "bed", "dining table", "toilet", "tv", "laptop",
    "mouse", "keyboard", "cell phone", "book", "clock", "vase", "scissors", "teddy bear",
    "hair drier", "toothbrush",
]
_candidate_str = os.environ.get("ANALYZE_CANDIDATE_CLASSES", "")
ANALYZE_CANDIDATE_CLASSES: list[str] = (
    [s.strip() for s in _candidate_str.split(",") if s.strip()]
    if _candidate_str.strip()
    else _DEFAULT_CANDIDATE_CLASSES
)
