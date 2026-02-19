"""앱 설정. 데이터셋 루트, 업로드 제한 등."""
import os
from pathlib import Path

# 데이터셋 루트 디렉터리 (YOLO 형식: {root}/{dataset_id}/images/, labels/, data.yaml)
DATASET_ROOT: Path = Path(os.environ.get("DATASET_ROOT", "./datasets")).resolve()

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

# CLIP/YOLOWorld 등 원격 다운로드 시 SSL 검증. 회사 프록시·자체서명 인증서 환경에서는 0으로 설정
SSL_VERIFY_FOR_DOWNLOADS: bool = os.environ.get("YOLO_DATASET_FACTORY_SSL_VERIFY", "1").lower() in ("1", "true", "yes")
