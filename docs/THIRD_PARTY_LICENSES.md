# 제3자 오픈소스 라이선스

본 프로젝트에서 사용하는 오픈소스와 라이선스 요약입니다.

## 라벨링 UI (이미지 bbox 편집)

| 프로젝트 | 라이선스 | 사용 방식 | 링크 |
|----------|----------|-----------|------|
| **Annotorious** | BSD 3-Clause | Vue 프론트엔드에서 bbox 그리기/수정 UI로 임베드 (`@annotorious/annotorious` npm 패키지) | [annotorious/annotorious](https://github.com/annotorious/annotorious) |

- **Annotorious**: 브라우저에서 이미지에 사각형(bbox) 어노테이션을 그리거나 수정하는 JavaScript 라이브러리. 본 프로젝트에서는 라벨 편집 화면(`/labeling` → 이미지별 «편집»)에서 사용하며, YOLO 형식(정규화 좌표)과 변환하여 API로 저장합니다.

## 기타

- **Vue**, **Vue Router**, **Vite**: 각 패키지 라이선스에 따름 (MIT 등). `frontend/package.json` 참고.
