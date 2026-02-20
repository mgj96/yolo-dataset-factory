# 라벨 편집 화면 주의사항

라벨 편집 뷰(`LabelEdit.vue`)에서 자주 발생할 수 있는 이슈와 재발 방지 규칙을 정리한다.

---

## 1. 객체 목록이 기존 라벨 로드 후 비어 보이는 현상

### 1.1 증상

- 편집 화면 진입 시 **객체 목록(bbox 목록) 사이드바**에 기존 YOLO 라벨이 반영되지 않고, "bbox가 없습니다"만 표시된다.
- 이미지 위에는 bbox가 그려져 있거나, 새로 그린 bbox만 목록에 나타나는 경우.

### 1.2 원인

- **비동기 호출 순서**: `loadYoloIntoAnnotator()`는 API로 라벨을 fetch한 뒤 `annotator.setAnnotations(...)`로 반영하는 **async** 함수인데, 호출 시 `await` 없이 사용되고 있었다.
- 그 다음 줄에서 곧바로 `refreshBboxList()`가 실행되므로, **setAnnotations가 끝나기 전에** 목록을 갱신하게 된다.
- 이 시점에는 annotator store에 annotation이 없어 `getAnnotations()` / `store.all()` 결과가 빈 배열이 되고, 객체 목록이 비어 보인다.

### 1.3 재발 방지 규칙

| 규칙 | 설명 |
|------|------|
| **Annotator 로드 후 UI 갱신은 반드시 await 이후** | 라벨/메타를 불러와 annotator에 반영하는 함수(`loadYoloIntoAnnotator` 등)는 **async**이므로, **await**한 뒤에 `refreshBboxList()` 등 UI 목록 갱신을 호출한다. |
| **동적 import 콜백 내부에서의 async** | `import('@annotorious/annotorious').then(callback)` 사용 시, callback을 `async`로 두고 내부에서 `await loadYoloIntoAnnotator()` 후 `refreshBboxList()`를 호출한다. |

### 1.4 수정 요약

- `frontend/src/views/LabelEdit.vue`의 `onImageLoad` 내부:
  - `import(...).then(({ createImageAnnotator }) => { ... })` → `async ({ createImageAnnotator }) => { ... }` 로 변경.
  - `loadYoloIntoAnnotator()` → `await loadYoloIntoAnnotator()` 로 변경하여, 라벨 로드 완료 후에만 `refreshBboxList()`가 실행되도록 함.

---

## 2. 객체 목록이 비어 있을 때 (라벨 데이터 관점)

편집 화면에서 **객체 목록이 계속 비어 있고** "bbox가 없습니다"만 보이는 경우, **UI 버그가 아니라 그 이미지에 대한 라벨 데이터가 서버에 없거나 비어 있는 경우**이다.

### 2.1 제가 라벨을 못 넣은 건가요? / 진짜 검출이 없는 건가요?

- **코드 쪽**: 앞서 수정한 것은 “이미 저장된 라벨”을 **올바른 타이밍에** 목록에 반영하는 부분이다. “라벨을 코드에서 임의로 넣지 않은 것”이 원인이 아니다.
- **데이터 쪽**: 객체 목록은 백엔드의 **labels/{dataset_id}/labels/{stem}.txt** 내용을 API로 받아와서 표시한다. 그 파일이 없거나 내용이 비어 있으면 목록은 빈 상태로 보인다.

### 2.2 목록이 비어 나오는 경우

| 상황 | 설명 |
|------|------|
| **자동 라벨을 아직 실행하지 않음** | 해당 이미지에 대한 `labels/{stem}.txt` 파일이 없음. API는 빈 문자열을 반환하고, 목록은 빈 상태로 표시된다. |
| **자동 라벨 실행 후에도 해당 이미지에서 검출 0건** | YOLO-World 추론 결과가 해당 이미지에서 비어 있거나, 적합성(confidence) 임계값 때문에 모두 걸러짐. 이 경우 **진짜 분석되는 게 없는 것**이다. `write_yolo_label(..., [])`로 빈 파일이 저장되어 목록이 비어 보인다. |

### 2.3 확인 방법

1. **자동 라벨 실행 여부**: 라벨링 화면에서 클래스명·임계값 입력 후 «자동 라벨 실행»을 한 번이라도 실행했는지 확인.
2. **응답 결과**: 자동 라벨 API 응답의 `total_boxes`, `images_with_boxes`로 전체 검출 수·객체가 있는 이미지 수 확인.
3. **임계값**: 적합성(confidence) 임계값이 너무 높으면 검출이 적어지거나 0이 될 수 있음. 낮춰서 다시 실행해 보기(예: 0.25 → 0.15).
4. **파일 직접 확인**(선택): 데이터셋 루트 아래 `{dataset_id}/labels/{이미지파일명에서 확장자 제외}.txt` 파일 존재 여부 및 내용(한 줄당 한 객체) 확인.

---

## 3. 참고

- 객체 목록 데이터 소스: `annotator.getAnnotations()` 또는 `annotator.state?.store?.all()`.
- 목록 갱신은 `createAnnotation` / `updateAnnotation` / `deleteAnnotation` 이벤트에서도 호출되므로, 새로 그리거나 수정·삭제한 bbox는 이벤트 핸들러를 통해 갱신된다. **초기 로드 직후**만 §1과 같은 타이밍 이슈가 발생한다.
