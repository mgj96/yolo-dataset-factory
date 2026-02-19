#!/usr/bin/env bash
# YOLO Dataset Factory: API(8081) + Vue(8100) 한 번에 가동.
# 실행 시 기존 8081/8100 포트 프로세스를 kill 한 뒤 재시작.
# 종료: Ctrl+C 시 두 프로세스 모두 정리.

set -e
cd "$(dirname "$0")"

API_PORT="${SERVER_PORT:-8081}"
VUE_PORT="${VUE_PORT:-8100}"
LOG_TS=$(date '+%Y-%m-%d %H:%M:%S')

# 기존 포트 사용 프로세스 종료 (있으면)
kill_port() {
  local port=$1
  local pids
  pids=$(lsof -ti :"${port}" 2>/dev/null) || true
  if [ -n "$pids" ]; then
    echo "[${LOG_TS}] Killing existing process(es) on port ${port}: ${pids}"
    echo "$pids" | xargs kill -9 2>/dev/null || true
    sleep 1
  fi
}

cleanup() {
  echo "[${LOG_TS}] Stopping API and Vue..."
  kill 0 2>/dev/null || true
  exit 0
}
trap cleanup SIGINT SIGTERM

kill_port "${API_PORT}"
kill_port "${VUE_PORT}"

echo "[${LOG_TS}] ---"
echo "[${LOG_TS}] UI(오픈소스 Vue 프론트엔드) 위치: $(pwd)/frontend/"
echo "[${LOG_TS}]   → 브라우저: http://localhost:${VUE_PORT}"
echo "[${LOG_TS}] API: http://localhost:${API_PORT}  (문서: http://localhost:${API_PORT}/docs)"
echo "[${LOG_TS}] ---"

echo "[${LOG_TS}] Starting API on 0.0.0.0:${API_PORT}"
python3 -m uvicorn main:app --host 0.0.0.0 --port "${API_PORT}" &
API_PID=$!

if [ ! -d "frontend/node_modules" ]; then
  echo "[${LOG_TS}] frontend/node_modules 없음. 'cd frontend && npm install' 실행 후 다시 시도하세요."
  exit 1
fi
echo "[${LOG_TS}] Starting Vue dev server on 0.0.0.0:${VUE_PORT}"
(cd frontend && npm run dev -- --port "${VUE_PORT}" --host) &
VUE_PID=$!

wait $API_PID $VUE_PID
