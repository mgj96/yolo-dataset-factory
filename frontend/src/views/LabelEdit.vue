<template>
  <div class="label-edit">
    <h1>라벨 편집</h1>
    <p><router-link :to="backLink">← 라벨링 목록</router-link></p>
    <p v-if="reviewStatus !== null" class="status-line">
      검수 상태: <span class="status-badge" :class="reviewStatus === 'reviewed' || reviewStatus === 'manual_labeled' ? 'status-done' : 'status-pending'">
        {{ reviewStatus === 'reviewed' || reviewStatus === 'manual_labeled' ? '검수완료' : '미검수' }}
      </span>
    </p>
    <div v-if="error" class="error">{{ error }}</div>
    <div v-else class="editor-wrap root-wrap">
      <div class="editor-main">
        <div v-if="!classNames.length" class="class-setup-row">
          <p class="class-setup-notice">클래스가 없어도 사각형을 그릴 수 있습니다. 아래에서 라벨을 추가한 뒤 그리거나, 먼저 그린 뒤 클래스를 설정하면 라벨이 반영됩니다.</p>
          <div class="quick-label-row">
            <input v-model="quickLabelInput" type="text" class="quick-label-input" placeholder="라벨 이름" />
            <button type="button" :disabled="settingClasses || !quickLabelInput.trim()" @click="applyQuickLabel">이 라벨로 추가하고 그리기</button>
          </div>
          <p class="class-setup-desc">클래스가 없습니다. 수동 라벨링을 위해 클래스를 설정하세요. (쉼표 구분 입력 또는 아래 기본 목록 선택)</p>
          <input v-model="customClassNamesInput" type="text" class="class-input" placeholder="person, car, dog" />
          <div v-if="defaultClassNames.length" class="default-classes">
            <span class="default-classes-label">기본 목록에서 선택:</span>
            <select v-model="selectedDefaultIndices" multiple class="default-class-multi">
              <option v-for="(name, idx) in defaultClassNames" :key="idx" :value="idx">{{ name }}</option>
            </select>
          </div>
          <button type="button" :disabled="settingClasses" @click="applyClasses">{{ settingClasses ? '적용 중…' : '클래스 적용' }}</button>
          <p v-if="classSetupError" class="error-inline">{{ classSetupError }}</p>
        </div>
        <div v-if="classNames.length" class="label-selector-row">
          <p class="label-selector-desc">라벨을 클릭한 뒤 이미지에 사각형을 그리세요. 선택한 라벨: <strong>{{ classNames[defaultClassIndex] || `클래스 ${defaultClassIndex}` }}</strong></p>
          <div class="label-list">
            <button
              v-for="(name, idx) in classNames"
              :key="idx"
              type="button"
              class="label-chip"
              :class="{ active: defaultClassIndex === idx }"
              @click="defaultClassIndex = idx"
            >
              {{ name || `클래스 ${idx}` }}
            </button>
          </div>
          <div class="other-label-row">
            <span class="other-label-label">기타:</span>
            <input v-model="otherLabelInput" type="text" class="other-label-input" placeholder="새 라벨 이름" @keydown.enter="applyOtherLabel" />
            <button type="button" class="btn-other-apply" :disabled="settingClasses || !otherLabelInput.trim()" @click="applyOtherLabel">주입</button>
          </div>
        </div>
        <div ref="imageWrap" class="image-wrap" :class="{ 'draw-hint': drawHintActive }">
          <img
            v-if="imageSrc"
            ref="imgEl"
            :key="imageSrcKey"
            :src="imageSrc"
            alt=""
            crossorigin="anonymous"
            @load="onImageLoad"
            @error="onImageError"
          />
          <p v-if="imageLoading" class="image-state-msg">이미지 로딩 중…</p>
          <p v-else-if="imageLoadError" class="image-state-msg image-error">
            이미지를 불러올 수 없습니다. 서버가 실행 중인지, 데이터셋·파일 경로를 확인하세요.
            <a v-if="imageUrl" :href="imageUrl" target="_blank" rel="noopener" class="image-error-link">주소 열기</a>
            <button type="button" class="btn-retry" @click="retryLoadImage">다시 시도</button>
          </p>
          <p v-if="drawHintActive" class="draw-hint-msg">이미지에서 드래그하여 사각형을 그리세요</p>
        </div>
        <div class="actions">
          <button type="button" :disabled="saving" @click="save">{{ saving ? '저장 중…' : '저장' }}</button>
          <button type="button" :disabled="saving" @click="saveAndMarkReviewed" class="btn-reviewed">
            {{ saving ? '저장 중…' : '저장 및 검수 완료' }}
          </button>
        </div>
      </div>
      <aside class="bbox-panel">
        <h3>객체 목록</h3>
        <div class="bbox-actions">
          <button type="button" class="btn-add-box" title="이미지에서 드래그해 사각형을 그리세요" @click="focusImageForDrawing">박스 추가</button>
          <button type="button" class="btn-remove-selected" :disabled="!selectedId" title="선택한 박스 제거" @click="removeSelectedAnnotation">선택한 박스 제거</button>
        </div>
        <ul v-if="bboxList.length" class="bbox-list">
          <li
            v-for="item in bboxList"
            :key="item.id"
            class="bbox-row"
            :class="{ selected: selectedId === item.id }"
            @click="selectAnnotation(item.id)"
          >
            <select
              v-if="classNames.length"
              :value="item.classIndex"
              class="bbox-class-select"
              @change="setBboxClass(item.id, Number(($event.target).value))"
              @click.stop
            >
              <option v-for="(name, idx) in classNames" :key="idx" :value="idx">{{ name || `클래스 ${idx}` }}</option>
            </select>
            <span v-else class="bbox-class">{{ item.className }}</span>
            <span v-if="item.confidence != null" class="bbox-conf">적합성 {{ (item.confidence * 100).toFixed(0) }}%</span>
            <span class="bbox-coords">{{ item.coords }}</span>
            <button type="button" class="btn-delete" title="삭제" @click.stop="deleteAnnotation(item.id)">×</button>
          </li>
        </ul>
        <p v-else class="bbox-empty">bbox가 없습니다. 이미지에 사각형을 그려 추가하세요.</p>
      </aside>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { fetchApi, putApi, datasetImagesUrl } from '../api'

const route = useRoute()
const router = useRouter()
const datasetId = route.params.datasetId
const filename = route.params.filename
const stem = filename.replace(/\.[^.]+$/, '')

const imgEl = ref(null)
const imageWrap = ref(null)
const error = ref('')
const saving = ref(false)
const reviewStatus = ref(null)  // "auto_labeled" | "reviewed" | "manual_labeled"
const classNames = ref([])
const defaultClassNames = ref([])  // 서버에서 내려주는 기본 후보 클래스(클래스 없을 때)
const customClassNamesInput = ref('')
const quickLabelInput = ref('')
const selectedDefaultIndices = ref([])
const settingClasses = ref(false)
const classSetupError = ref('')
const defaultClassIndex = ref(0)
const otherLabelInput = ref('')
const metaObjects = ref([])  // [{ bbox, confidence?, ... }] from meta
const bboxList = ref([])
const selectedId = ref(null)
const drawHintActive = ref(false)
const imageLoading = ref(true)
const imageLoadError = ref(false)
let drawHintTimer = null
let annotator = null
const lifecycleHandlers = []  // { event, callback } for annotator.off on unmount

const imageUrl = computed(() => datasetImagesUrl(datasetId, filename))
const imageSrc = ref('')
const imageSrcKey = ref(0)
const imageErrorAutoRetryDone = ref(false)
let imageErrorRetryTimer = null
let initialLoadTimer = null
const INITIAL_IMAGE_LOAD_DELAY_MS = 400
const backLink = computed(() => ({ name: 'Labeling', query: datasetId ? { dataset_id: datasetId } : {} }))

watch(imageUrl, (url) => {
  if (initialLoadTimer) {
    clearTimeout(initialLoadTimer)
    initialLoadTimer = null
  }
  imageLoadError.value = false
  imageErrorAutoRetryDone.value = false
  if (url) {
    imageLoading.value = true
    imageSrc.value = ''
    initialLoadTimer = setTimeout(() => {
      initialLoadTimer = null
      imageSrc.value = url
    }, INITIAL_IMAGE_LOAD_DELAY_MS)
  } else {
    imageSrc.value = ''
    imageLoading.value = false
  }
}, { immediate: true })

function retryLoadImage() {
  imageLoadError.value = false
  imageLoading.value = true
  imageSrcKey.value += 1
  const url = imageUrl.value
  imageSrc.value = url ? `${url}${url.includes('?') ? '&' : '?'}t=${Date.now()}` : ''
}

function normKey(ann, imgW, imgH) {
  const g = ann.target?.selector?.geometry
  if (!g) return ''
  const x = g.x ?? g.bounds?.minX ?? 0
  const y = g.y ?? g.bounds?.minY ?? 0
  const w = g.w ?? (g.bounds?.maxX - g.bounds?.minX) ?? 0
  const h = g.h ?? (g.bounds?.maxY - g.bounds?.minY) ?? 0
  const xc = (x + w / 2) / imgW
  const yc = (y + h / 2) / imgH
  const nw = w / imgW
  const nh = h / imgH
  return [xc, yc, nw, nh].map((v) => v.toFixed(4)).join(',')
}

function refreshBboxList() {
  if (!annotator || !imgEl.value) return
  const list = annotator.getAnnotations?.() ?? annotator.state?.store?.all?.() ?? []
  const imgW = imgEl.value.naturalWidth || imgEl.value.width
  const imgH = imgEl.value.naturalHeight || imgEl.value.height
  const objects = metaObjects.value
  const confByKey = {}
  objects.forEach((o) => {
    const k = (o.bbox && o.bbox.map((v) => Number(v).toFixed(4)).join(',')) || ''
    if (k && o.confidence != null) confByKey[k] = o.confidence
  })
  bboxList.value = list.map((ann) => {
    const classIdx = ann.bodies?.[0]?.value ?? 0
    const className = classNames.value[classIdx] ?? `클래스 ${classIdx}`
    const g = ann.target?.selector?.geometry
    let coords = '—'
    if (g) {
      const x = g.x ?? g.bounds?.minX ?? 0
      const y = g.y ?? g.bounds?.minY ?? 0
      const w = g.w ?? (g.bounds?.maxX - g.bounds?.minX) ?? 0
      const h = g.h ?? (g.bounds?.maxY - g.bounds?.minY) ?? 0
      const xc = ((x + w / 2) / imgW * 100).toFixed(0)
      const yc = ((y + h / 2) / imgH * 100).toFixed(0)
      coords = `중심 ${xc}%, ${yc}%`
    }
    const key = normKey(ann, imgW, imgH)
    const confidence = confByKey[key] ?? null
    return { id: ann.id, classIndex: classIdx, className, confidence, coords }
  })
}

function selectAnnotation(id) {
  selectedId.value = id
  if (annotator?.state?.selection) annotator.state.selection.setSelected(id, true)
}

function deleteAnnotation(id) {
  if (!annotator?.state?.store) return
  annotator.state.store.deleteAnnotation(id)
  if (selectedId.value === id) selectedId.value = null
  refreshBboxList()
}

function focusImageForDrawing() {
  imageWrap.value?.scrollIntoView?.({ behavior: 'smooth', block: 'center' })
  if (drawHintTimer) clearTimeout(drawHintTimer)
  drawHintActive.value = true
  drawHintTimer = setTimeout(() => {
    drawHintActive.value = false
    drawHintTimer = null
  }, 3500)
  // Annotorious v3: drawingEnabled가 true면 이미 그리기 가능. 필요 시 annotator API로 모드 전환
  if (typeof annotator?.setDrawingEnabled === 'function') annotator.setDrawingEnabled(true)
}

function removeSelectedAnnotation() {
  if (selectedId.value) {
    deleteAnnotation(selectedId.value)
  }
}

function setBboxClass(annId, newClassIndex) {
  if (!annotator?.state?.store) return
  const ann = annotator.getAnnotations?.()?.find((a) => a.id === annId)
  if (!ann?.bodies?.[0]) return
  const body = ann.bodies[0]
  try {
    annotator.state.store.updateBody(
      { id: body.id, annotation: ann.id },
      { ...body, value: newClassIndex },
    )
  } catch (_) {}
  refreshBboxList()
}

async function applyClasses() {
  const fromInput = customClassNamesInput.value.split(',').map((s) => s.trim()).filter(Boolean)
  const fromDefault = (selectedDefaultIndices.value || [])
    .sort((a, b) => a - b)
    .map((i) => defaultClassNames.value[i])
    .filter(Boolean)
  const combined = [...new Set([...fromInput, ...fromDefault])]
  if (!combined.length) {
    classSetupError.value = '클래스를 입력하거나 기본 목록에서 선택하세요.'
    return
  }
  settingClasses.value = true
  classSetupError.value = ''
  try {
    const data = await putApi(`/api/dataset/${encodeURIComponent(datasetId)}/classes`, { class_names: combined })
    classNames.value = data.class_names || combined
    customClassNamesInput.value = ''
    selectedDefaultIndices.value = []
  } catch (e) {
    classSetupError.value = e?.message || '적용 실패'
  } finally {
    settingClasses.value = false
  }
}

async function applyQuickLabel() {
  const name = quickLabelInput.value.trim()
  if (!name) return
  settingClasses.value = true
  classSetupError.value = ''
  try {
    const data = await putApi(`/api/dataset/${encodeURIComponent(datasetId)}/classes`, { class_names: [name] })
    classNames.value = data.class_names || [name]
    defaultClassIndex.value = 0
    quickLabelInput.value = ''
  } catch (e) {
    classSetupError.value = e?.message || '적용 실패'
  } finally {
    settingClasses.value = false
  }
}

async function applyOtherLabel() {
  const name = otherLabelInput.value.trim()
  if (!name) return
  settingClasses.value = true
  classSetupError.value = ''
  try {
    const combined = [...classNames.value, name]
    const data = await putApi(`/api/dataset/${encodeURIComponent(datasetId)}/classes`, { class_names: combined })
    classNames.value = data.class_names || combined
    defaultClassIndex.value = classNames.value.length - 1
    otherLabelInput.value = ''
  } catch (e) {
    classSetupError.value = e?.message || '주입 실패'
  } finally {
    settingClasses.value = false
  }
}

async function loadMeta() {
  try {
    const [meta, info] = await Promise.all([
      fetchApi(`/api/dataset/${encodeURIComponent(datasetId)}/labels/${encodeURIComponent(stem)}/meta`).catch(() => ({})),
      fetchApi(`/api/dataset/${encodeURIComponent(datasetId)}/info`).catch(() => ({})),
    ])
    reviewStatus.value = meta.status ?? null
    metaObjects.value = meta.objects || []
    classNames.value = info.class_names || []
    defaultClassNames.value = info.default_class_names || []
    if (classNames.value.length && defaultClassIndex.value >= classNames.value.length) defaultClassIndex.value = 0
  } catch (_) {
    reviewStatus.value = null
    metaObjects.value = []
    defaultClassNames.value = []
  }
}

function onImageError() {
  if (!imageErrorAutoRetryDone.value && imageUrl.value) {
    imageErrorAutoRetryDone.value = true
    imageLoading.value = true
    const url = imageUrl.value
    const cacheBust = `${url}${url.includes('?') ? '&' : '?'}t=${Date.now()}`
    imageErrorRetryTimer = setTimeout(() => {
      imageErrorRetryTimer = null
      imageSrcKey.value += 1
      imageSrc.value = cacheBust
    }, 400)
    return
  }
  imageLoading.value = false
  imageLoadError.value = true
}

async function onImageLoad() {
  imageLoadError.value = false
  imageLoading.value = false
  await loadMeta()
  if (!imgEl.value) return
  import('@annotorious/annotorious').then(async ({ createImageAnnotator }) => {
    if (annotator) {
      lifecycleHandlers.forEach(({ event, callback }) => {
        try { if (annotator.off) annotator.off(event, callback) } catch (_) {}
      })
      lifecycleHandlers.length = 0
      try { annotator.destroy() } catch (_) {}
    }
    annotator = createImageAnnotator(imgEl.value, {
      drawingEnabled: true,
    })
    await loadYoloIntoAnnotator()
    refreshBboxList()
    if (annotator.on) {
      const onCreate = (ann) => {
        const idx = defaultClassIndex.value
        const body = ann.bodies?.[0]
        if (body != null && annotator?.state?.store) {
          try {
            annotator.state.store.updateBody(
              { id: body.id, annotation: ann.id },
              { ...body, value: idx }
            )
          } catch (_) {}
        }
        refreshBboxList()
      }
      const onUpdate = () => refreshBboxList()
      const onDelete = () => refreshBboxList()
      const onSelectionChanged = (selected) => {
        selectedId.value = selected?.length ? (selected[0]?.id ?? null) : null
      }
      annotator.on('createAnnotation', onCreate)
      annotator.on('updateAnnotation', onUpdate)
      annotator.on('deleteAnnotation', onDelete)
      annotator.on('selectionChanged', onSelectionChanged)
      lifecycleHandlers.push(
        { event: 'createAnnotation', callback: onCreate },
        { event: 'updateAnnotation', callback: onUpdate },
        { event: 'deleteAnnotation', callback: onDelete },
        { event: 'selectionChanged', callback: onSelectionChanged },
      )
    }
  }).catch((e) => {
    error.value = `에디터 로드 실패: ${e.message}`
  })
}

function yoloLineToAnnotation(line, imgWidth, imgHeight) {
  const parts = line.trim().split(/\s+/)
  if (parts.length < 5) return null
  const classIdx = parseInt(parts[0], 10)
  const xc = parseFloat(parts[1])
  const yc = parseFloat(parts[2])
  const w = parseFloat(parts[3])
  const h = parseFloat(parts[4])
  const x = (xc - w / 2) * imgWidth
  const y = (yc - h / 2) * imgHeight
  const width = w * imgWidth
  const height = h * imgHeight
  return {
    target: {
      selector: {
        type: 'RECTANGLE',
        geometry: {
          x, y, w: width, h: height,
          bounds: { minX: x, minY: y, maxX: x + width, maxY: y + height },
        },
      },
    },
    bodies: [{ purpose: 'class_index', value: classIdx }],
  }
}

function annotationToYoloLine(ann, imgWidth, imgHeight) {
  const sel = ann.target?.selector
  if (!sel || sel.type !== 'RECTANGLE') return null
  const g = sel.geometry
  const x = g.x ?? g.bounds?.minX ?? 0
  const y = g.y ?? g.bounds?.minY ?? 0
  const w = g.w ?? (g.bounds?.maxX - g.bounds?.minX) ?? 0
  const h = g.h ?? (g.bounds?.maxY - g.bounds?.minY) ?? 0
  const xc = (x + w / 2) / imgWidth
  const yc = (y + h / 2) / imgHeight
  const nw = w / imgWidth
  const nh = h / imgHeight
  const classIdx = ann.bodies?.[0]?.value ?? 0
  return `${classIdx} ${xc.toFixed(6)} ${yc.toFixed(6)} ${nw.toFixed(6)} ${nh.toFixed(6)}`
}

async function loadYoloIntoAnnotator() {
  if (!annotator || !imgEl.value) return
  try {
    const text = await fetchApi(`/api/dataset/${encodeURIComponent(datasetId)}/labels/${encodeURIComponent(stem)}`)
    const imgW = imgEl.value.naturalWidth || imgEl.value.width
    const imgH = imgEl.value.naturalHeight || imgEl.value.height
    const lines = (text || '').trim().split('\n').filter(Boolean)
    const annotations = lines
      .map((line) => yoloLineToAnnotation(line, imgW, imgH))
      .filter(Boolean)
    if (annotations.length) annotator.setAnnotations(annotations, true)
  } catch (_) {}
}

async function save() {
  if (!annotator || !imgEl.value) return
  saving.value = true
  error.value = ''
  try {
    const imgW = imgEl.value.naturalWidth || imgEl.value.width
    const imgH = imgEl.value.naturalHeight || imgEl.value.height
    const list = annotator.getAnnotations()
    const lines = list
      .map((ann) => annotationToYoloLine(ann, imgW, imgH))
      .filter(Boolean)
    const content = lines.join('\n')
    await putApi(`/api/dataset/${encodeURIComponent(datasetId)}/labels/${encodeURIComponent(stem)}`, { content })
    error.value = ''
    alert('저장되었습니다.')
  } catch (e) {
    error.value = `저장 실패: ${e.message}`
  } finally {
    saving.value = false
  }
}

async function saveAndMarkReviewed() {
  if (!annotator || !imgEl.value) return
  saving.value = true
  error.value = ''
  try {
    const imgW = imgEl.value.naturalWidth || imgEl.value.width
    const imgH = imgEl.value.naturalHeight || imgEl.value.height
    const list = annotator.getAnnotations()
    const lines = list
      .map((ann) => annotationToYoloLine(ann, imgW, imgH))
      .filter(Boolean)
    const content = lines.join('\n')
    await putApi(`/api/dataset/${encodeURIComponent(datasetId)}/labels/${encodeURIComponent(stem)}`, { content })
    await putApi(`/api/dataset/${encodeURIComponent(datasetId)}/labels/${encodeURIComponent(stem)}/meta`, {
      status: 'reviewed',
    })
    reviewStatus.value = 'reviewed'
    error.value = ''
    alert('저장되었고 검수 완료로 표시했습니다.')
  } catch (e) {
    error.value = `저장 실패: ${e.message}`
  } finally {
    saving.value = false
  }
}

onUnmounted(() => {
  if (drawHintTimer) {
    clearTimeout(drawHintTimer)
    drawHintTimer = null
  }
  if (initialLoadTimer) {
    clearTimeout(initialLoadTimer)
    initialLoadTimer = null
  }
  if (imageErrorRetryTimer) {
    clearTimeout(imageErrorRetryTimer)
    imageErrorRetryTimer = null
  }
  if (annotator) {
    lifecycleHandlers.forEach(({ event, callback }) => {
      try { if (annotator.off) annotator.off(event, callback) } catch (_) {}
    })
    lifecycleHandlers.length = 0
    try { annotator.destroy() } catch (_) {}
    annotator = null
  }
})
</script>

<style scoped>
.label-edit { max-width: 1200px; }
.root-wrap { margin-top: 1rem; display: flex; gap: 1rem; flex-wrap: wrap; }
.editor-main { flex: 1; min-width: 280px; }
.class-setup-row { margin-bottom: 1rem; padding: 0.75rem; background: #f8f9fa; border-radius: 8px; }
.class-setup-notice { font-size: 0.9rem; color: #555; margin: 0 0 0.75rem; }
.quick-label-row { display: flex; flex-wrap: wrap; align-items: center; gap: 0.5rem; margin-bottom: 0.75rem; }
.quick-label-input { padding: 0.4rem; width: 140px; }
.class-setup-desc { font-size: 0.9rem; color: #555; margin: 0 0 0.5rem; }
.class-input { width: 100%; max-width: 400px; padding: 0.4rem; margin-bottom: 0.5rem; }
.default-classes { margin: 0.5rem 0; }
.default-classes-label { font-size: 0.85rem; display: block; margin-bottom: 0.25rem; }
.default-class-multi { min-height: 120px; width: 100%; max-width: 280px; padding: 0.25rem; }
.error-inline { color: #c00; font-size: 0.9rem; margin-top: 0.5rem; }
.label-selector-row { margin-bottom: 0.75rem; }
.label-selector-desc { font-size: 0.9rem; color: #555; margin: 0 0 0.5rem; }
.label-list { display: flex; flex-wrap: wrap; gap: 0.35rem; }
.label-chip { padding: 0.35rem 0.6rem; border-radius: 6px; border: 1px solid #ccc; background: #fff; cursor: pointer; font-size: 0.9rem; }
.label-chip:hover { background: #eee; }
.label-chip.active { background: #1a1a2e; color: #fff; border-color: #1a1a2e; }
.other-label-row { display: flex; flex-wrap: wrap; align-items: center; gap: 0.5rem; margin-top: 0.5rem; }
.other-label-label { font-size: 0.9rem; color: #555; }
.other-label-input { padding: 0.35rem 0.5rem; width: 140px; font-size: 0.9rem; }
.btn-other-apply { padding: 0.35rem 0.6rem; font-size: 0.85rem; }
.bbox-class-select { min-width: 6rem; padding: 0.2rem 0.35rem; font-size: 0.85rem; }
.editor-wrap .image-wrap { margin-bottom: 0.5rem; max-width: 100%; overflow: auto; position: relative; min-height: 240px; background: #f0f0f0; border-radius: 6px; }
.image-wrap img { max-width: 100%; height: auto; display: block; }
.image-state-msg { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); margin: 0; padding: 0.75rem 1rem; background: rgba(255,255,255,0.95); border-radius: 8px; font-size: 0.9rem; color: #555; text-align: center; max-width: 90%; }
.image-state-msg.image-error { color: #c00; display: flex; flex-direction: column; align-items: center; gap: 0.5rem; }
.image-error-link { font-size: 0.85rem; color: #06c; }
.btn-retry { margin-top: 0.25rem; padding: 0.35rem 0.75rem; font-size: 0.9rem; cursor: pointer; border-radius: 6px; border: 1px solid #ccc; background: #fff; }
.btn-retry:hover { background: #f0f0f0; }
.image-wrap.draw-hint { outline: 2px solid #1a1a2e; outline-offset: 4px; border-radius: 4px; }
.draw-hint-msg { position: absolute; bottom: 0.5rem; left: 50%; transform: translateX(-50%); margin: 0; padding: 0.4rem 0.75rem; background: #1a1a2e; color: #fff; border-radius: 6px; font-size: 0.9rem; white-space: nowrap; pointer-events: none; }
.bbox-panel { width: 280px; flex-shrink: 0; border: 1px solid #ddd; border-radius: 8px; padding: 0.75rem; background: #fafafa; max-height: 70vh; overflow: auto; }
.bbox-panel h3 { margin: 0 0 0.5rem; font-size: 0.95rem; }
.bbox-actions { display: flex; flex-wrap: wrap; gap: 0.35rem; margin-bottom: 0.5rem; }
.btn-add-box { padding: 0.3rem 0.6rem; font-size: 0.85rem; }
.btn-remove-selected { padding: 0.3rem 0.6rem; font-size: 0.85rem; }
.bbox-list { list-style: none; padding: 0; margin: 0; }
.bbox-row { display: flex; flex-wrap: wrap; align-items: center; gap: 0.35rem; padding: 0.4rem 0.5rem; margin-bottom: 0.25rem; border-radius: 4px; cursor: pointer; border: 1px solid transparent; }
.bbox-row:hover { background: #eee; }
.bbox-row.selected { background: #e0e8ff; border-color: #1a1a2e; }
.bbox-class { font-weight: 600; font-size: 0.9rem; min-width: 4rem; }
.bbox-conf { font-size: 0.75rem; color: #666; }
.bbox-coords { font-size: 0.75rem; color: #888; flex: 1; }
.btn-delete { margin-left: auto; padding: 0.1rem 0.4rem; font-size: 1.1rem; line-height: 1.2; border: none; background: transparent; color: #c00; cursor: pointer; border-radius: 4px; }
.btn-delete:hover { background: #fee; }
.bbox-empty { font-size: 0.85rem; color: #666; margin: 0; }
.status-line { margin: 0.5rem 0; }
.status-badge { padding: 0.2rem 0.5rem; border-radius: 4px; font-size: 0.9rem; }
.status-pending { background: #fee; color: #c00; }
.status-done { background: #efe; color: #080; }
.actions { margin-top: 0.5rem; display: flex; gap: 0.5rem; flex-wrap: wrap; }
button { padding: 0.4rem 1rem; cursor: pointer; }
.btn-reviewed { background: #1a1a2e; color: #fff; border: none; border-radius: 4px; }
.btn-reviewed:hover:not(:disabled) { opacity: 0.9; }
button:disabled { opacity: 0.6; cursor: not-allowed; }
.error { color: #c00; margin: 0.5rem 0; }
</style>
