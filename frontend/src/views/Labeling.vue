<template>
  <div class="labeling">
    <h1>작업하기</h1>
    <section class="card">
      <h2>1. 이미지 업로드</h2>
      <p class="step-desc">이미지를 업로드하면 새 세션이 생성됩니다. 업로드하시면 라벨링 작업이 즉시 진행 가능합니다.</p>
      <div class="upload-row">
        <input
          ref="fileInput"
          type="file"
          multiple
          accept="image/*"
          class="file-input"
        />
        <button type="button" :disabled="uploading" @click="doUpload">
          {{ uploading ? '업로드 중…' : '이미지 업로드' }}
        </button>
      </div>
      <p v-if="uploadResult" class="result">{{ uploadResult }}</p>
    </section>
    <section v-if="images.length" class="card">
      <h2>2. 분석 및 설정</h2>
      <p class="step-desc">분석 실행 시 업로드된 이미지로 추론하여 검출된 클래스와 초기 라벨을 제안합니다. 제안값을 수정한 뒤 자동 라벨을 다시 실행할 수 있습니다.</p>
      <button type="button" :disabled="analyzeLoading" @click="runAnalyze">{{ analyzeLoading ? '분석 중…' : '분석 실행' }}</button>
      <p v-if="analyzeResult" class="result">{{ analyzeResult }}</p>
      <p v-if="classNames.length" class="class-summary">클래스: {{ classNames.join(', ') }}</p>
      <label>클래스명 (쉼표 구분) <input v-model="classNamesInput" type="text" placeholder="person, car, dog" /></label>
      <label>적합성(confidence 임계값) <input v-model.number="confThreshold" type="number" min="0.1" max="0.99" step="0.05" class="conf-input" /> (0.1~0.99, 낮을수록 더 많이 검출)</label>
      <button type="button" :disabled="autoLabelLoading" @click="runAutoLabel">{{ autoLabelLoading ? '실행 중…' : '자동 라벨 실행' }}</button>
      <p v-if="autoLabelResult" class="result">{{ autoLabelResult }}</p>
    </section>
    <section v-if="images.length" class="card">
      <h2>3. 라벨링 및 검수</h2>
      <p>이미지별로 bbox를 그리거나 수정한 뒤 저장하고, 검수 완료하면 정제된 데이터로 저장됩니다.</p>
      <label class="refined-toggle">
        <input v-model="showRefinedOnly" type="checkbox" @change="loadImages" />
        정제된 데이터만 보기 (검수 완료된 이미지)
      </label>
      <p v-if="refinedCount !== null" class="refined-count">정제된 데이터: {{ refinedCount }}개</p>
      <ul class="image-list">
        <li v-for="img in images" :key="img.filename">
          <img :src="datasetImagesUrl(effectiveDatasetId, img.filename)" :alt="img.filename" class="thumb" loading="lazy" />
          <span class="name">{{ img.filename }}</span>
          <span class="bbox-summary" :title="bboxSummaryTitle(img.filename)">
            {{ bboxSummaryLabel(img.filename) }}
          </span>
          <span class="status-badge" :class="statusClass(img.filename)">{{ statusLabel(img.filename) }}</span>
          <router-link :to="editLink(img)" class="btn-edit">편집</router-link>
        </li>
      </ul>
    </section>
    <p v-else class="muted">이미지를 업로드하거나, 데이터셋 탭에서 기존 데이터셋을 선택한 뒤 «이 데이터셋으로 작업하기»로 이 페이지에 오세요.</p>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { fetchApi, datasetImagesUrl, uploadFrames } from '../api'

const route = useRoute()
/** 현재 작업 중인 데이터셋/세션 ID. 업로드 응답 또는 쿼리 dataset_id로 설정됨 */
const datasetId = ref('')

const fileInput = ref(null)
const uploading = ref(false)
const uploadResult = ref('')

const images = ref([])
const classNames = ref([])
const classNamesInput = ref('')
const confThreshold = ref(0.25)
const analyzeLoading = ref(false)
const analyzeResult = ref('')
const autoLabelLoading = ref(false)
const autoLabelResult = ref('')
const labelStatuses = ref({})  // stem -> "auto_labeled" | "reviewed" | "manual_labeled"
const labelSummaries = ref({})  // stem -> { bbox_count, confidence_avg }
const showRefinedOnly = ref(false)
const refinedCount = ref(null)

const effectiveDatasetId = computed(() => datasetId.value || '')

function editLink(img) {
  return { name: 'LabelEdit', params: { datasetId: effectiveDatasetId.value, filename: img.filename } }
}

function stem(filename) {
  return filename.replace(/\.[^.]+$/, '')
}

function statusLabel(filename) {
  const s = labelStatuses.value[stem(filename)]
  if (s === 'reviewed' || s === 'manual_labeled') return '검수완료'
  return '미검수'
}

function statusClass(filename) {
  const s = labelStatuses.value[stem(filename)]
  if (s === 'reviewed' || s === 'manual_labeled') return 'status-done'
  return 'status-pending'
}

function bboxSummaryLabel(filename) {
  const sum = labelSummaries.value[stem(filename)]
  if (!sum) return '—'
  const n = sum.bbox_count ?? 0
  const conf = sum.confidence_avg
  if (conf != null && !Number.isNaN(conf)) return `${n}개 객체 · 적합성 ${(conf * 100).toFixed(0)}%`
  return `${n}개 객체`
}

function bboxSummaryTitle(filename) {
  const sum = labelSummaries.value[stem(filename)]
  if (!sum) return ''
  const conf = sum.confidence_avg
  if (conf != null && !Number.isNaN(conf)) return `평균 적합성(confidence): ${(conf * 100).toFixed(1)}%`
  return '라벨 위치(bbox 개수)'
}

async function loadImages() {
  const id = effectiveDatasetId.value
  if (!id) return
  uploadResult.value = ''
  autoLabelResult.value = ''
  analyzeResult.value = ''
  try {
    const data = await fetchApi(`/api/dataset/${encodeURIComponent(id)}/images`)
    images.value = data.images || []
    const info = await fetchApi(
      `/api/dataset/${encodeURIComponent(id)}/info${showRefinedOnly.value ? '?refined_only=true' : ''}`
    ).catch(() => ({}))
    classNames.value = info.class_names || []
    if (classNames.value.length) classNamesInput.value = classNames.value.join(', ')
    refinedCount.value = info.refined_count ?? null
    const labelsUrl = `/api/dataset/${encodeURIComponent(id)}/labels${showRefinedOnly.value ? '?refined_only=true' : ''}`
    const labelsData = await fetchApi(labelsUrl).catch(() => [])
    const statusMap = {}
    const summaryMap = {}
    const refinedStems = new Set(labelsData.map((l) => l.stem))
    for (const item of labelsData) {
      statusMap[item.stem] = item.status
      summaryMap[item.stem] = { bbox_count: item.bbox_count ?? 0, confidence_avg: item.confidence_avg ?? null }
    }
    labelStatuses.value = statusMap
    labelSummaries.value = summaryMap
    if (showRefinedOnly.value) {
      images.value = refinedStems.size
        ? (data.images || []).filter((img) => refinedStems.has(stem(img.filename)))
        : []
    }
  } catch (e) {
    images.value = []
    classNames.value = []
    labelStatuses.value = {}
    labelSummaries.value = {}
    uploadResult.value = `오류: ${e.message}`
  }
}

async function doUpload() {
  const input = fileInput.value
  if (!input?.files?.length) {
    uploadResult.value = '파일을 선택하세요.'
    return
  }
  const files = Array.from(input.files)
  const isNewSession = !effectiveDatasetId.value
  uploading.value = true
  uploadResult.value = ''
  try {
    const data = await uploadFrames(effectiveDatasetId.value || undefined, files, isNewSession)
    datasetId.value = data.dataset_id
    const n = data.saved?.length ?? 0
    uploadResult.value = `${n}개 업로드됨.` + (isNewSession ? ' (새 세션 생성됨)' : '')
    input.value = ''
    await loadImages()
  } catch (e) {
    uploadResult.value = `업로드 실패: ${e.message}`
  } finally {
    uploading.value = false
  }
}

async function runAnalyze() {
  const id = effectiveDatasetId.value
  if (!id) {
    analyzeResult.value = '먼저 이미지를 업로드하세요.'
    return
  }
  analyzeLoading.value = true
  analyzeResult.value = ''
  const controller = new AbortController()
  const timeoutMs = 5 * 60 * 1000
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const data = await fetchApi(`/api/dataset/${encodeURIComponent(id)}/analyze`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ conf_threshold: confThreshold.value }),
      signal: controller.signal,
    })
    clearTimeout(timeoutId)
    classNames.value = data.suggested_class_names || []
    classNamesInput.value = classNames.value.join(', ')
    confThreshold.value = data.suggested_conf_threshold ?? confThreshold.value
    const total = data.total_boxes ?? 0
    const withBoxes = data.images_with_boxes ?? 0
    analyzeResult.value = `완료: 제안 클래스 ${classNames.value.length}개, bbox ${total}개, 객체 있는 이미지 ${withBoxes}개.`
    await loadImages()
  } catch (e) {
    clearTimeout(timeoutId)
    analyzeResult.value = e?.name === 'AbortError' ? '오류: 요청 시간이 초과되었습니다.' : `오류: ${e.message}`
  } finally {
    analyzeLoading.value = false
  }
}

async function runAutoLabel() {
  const names = classNamesInput.value.split(',').map((s) => s.trim()).filter(Boolean)
  if (!names.length) {
    autoLabelResult.value = '클래스명을 입력하세요.'
    return
  }
  const conf = Number(confThreshold.value)
  if (Number.isNaN(conf) || conf < 0.1 || conf > 0.99) {
    autoLabelResult.value = '적합성(confidence)은 0.1~0.99 사이로 입력하세요.'
    return
  }
  autoLabelLoading.value = true
  autoLabelResult.value = ''
  const controller = new AbortController()
  const timeoutMs = 5 * 60 * 1000
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const data = await fetchApi(`/api/dataset/${encodeURIComponent(effectiveDatasetId.value)}/auto-label`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ class_names: names, provider: 'yoloworld', conf_threshold: conf }),
      signal: controller.signal,
    })
    clearTimeout(timeoutId)
    const total = data.total_boxes ?? 0
    const withBoxes = data.images_with_boxes ?? data.labeled_count ?? 0
    autoLabelResult.value = `완료: ${data.labeled_count}개 이미지 라벨 생성. (bbox ${total}개, 객체 있는 이미지 ${withBoxes}개)`
    classNames.value = data.class_names || names
    loadImages()
  } catch (e) {
    clearTimeout(timeoutId)
    autoLabelResult.value = e?.name === 'AbortError' ? '오류: 요청 시간이 초과되었습니다. (최대 5분, 첫 실행 시 모델 다운로드로 더 걸릴 수 있음)' : `오류: ${e.message}`
  } finally {
    autoLabelLoading.value = false
  }
}

function applyQueryDatasetId() {
  const q = route.query?.dataset_id
  if (q && typeof q === 'string' && q.trim()) {
    datasetId.value = q.trim()
    loadImages()
  }
}

onMounted(() => {
  applyQueryDatasetId()
})

watch(() => route.query?.dataset_id, (newId) => {
  if (newId && typeof newId === 'string' && newId.trim()) {
    datasetId.value = newId.trim()
    loadImages()
  }
})
</script>

<style scoped>
.labeling { max-width: 720px; }
.card { margin-bottom: 1.5rem; padding: 1rem; border: 1px solid #ddd; border-radius: 8px; }
.card h2 { margin-top: 0; font-size: 1.1rem; }
.step-desc { font-size: 0.9rem; color: #555; margin: 0.25rem 0 0.75rem; }
.class-summary { font-size: 0.9rem; margin: 0.5rem 0; }
.refined-toggle { display: flex; align-items: center; gap: 0.5rem; margin: 0.5rem 0; font-size: 0.9rem; }
.refined-count { font-size: 0.9rem; color: #066; margin: 0.25rem 0; }
label { display: block; margin: 0.5rem 0; }
input[type="text"] { margin-left: 0.5rem; padding: 0.35rem; width: 280px; }
.conf-input { margin-left: 0.5rem; padding: 0.35rem; width: 4rem; }
.upload-row { display: flex; align-items: center; gap: 0.5rem; margin: 0.5rem 0; }
.file-input { flex: 1; max-width: 280px; }
button { padding: 0.4rem 0.8rem; cursor: pointer; }
button:disabled { opacity: 0.6; cursor: not-allowed; }
.result { margin-top: 0.5rem; color: #0a0; }
.image-list { list-style: none; padding: 0; margin: 0; }
.image-list li { display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.5rem; padding: 0.25rem 0; border-bottom: 1px solid #eee; }
.thumb { width: 64px; height: 48px; object-fit: cover; border-radius: 4px; }
.name { flex: 1; font-size: 0.9rem; overflow: hidden; text-overflow: ellipsis; }
.bbox-summary { font-size: 0.8rem; color: #555; min-width: 6rem; }
.btn-edit { padding: 0.3rem 0.6rem; background: #1a1a2e; color: #fff; border-radius: 4px; text-decoration: none; font-size: 0.9rem; }
.btn-edit:hover { opacity: 0.9; }
.status-badge { font-size: 0.75rem; padding: 0.2rem 0.4rem; border-radius: 4px; }
.status-pending { background: #fee; color: #c00; }
.status-done { background: #efe; color: #080; }
.muted { color: #666; }
</style>
