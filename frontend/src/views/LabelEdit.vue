<template>
  <div class="label-edit">
    <h1>라벨 편집</h1>
    <p><router-link :to="backLink">← 라벨링 목록</router-link></p>
    <div v-if="error" class="error">{{ error }}</div>
    <div v-else class="editor-wrap">
      <div ref="imageWrap" class="image-wrap">
        <img
          ref="imgEl"
          :src="imageUrl"
          alt=""
          crossorigin="anonymous"
          @load="onImageLoad"
        />
      </div>
      <div class="actions">
        <button type="button" :disabled="saving" @click="save">{{ saving ? '저장 중…' : '저장' }}</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onUnmounted } from 'vue'
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
let annotator = null

const imageUrl = computed(() => datasetImagesUrl(datasetId, filename))
const backLink = computed(() => ({ name: 'Labeling' }))

function onImageLoad() {
  if (!imgEl.value) return
  import('@annotorious/annotorious').then(({ createImageAnnotator }) => {
    if (annotator) {
      try { annotator.destroy() } catch (_) {}
    }
    annotator = createImageAnnotator(imgEl.value, {
      drawingEnabled: true,
    })
    loadYoloIntoAnnotator()
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

onUnmounted(() => {
  if (annotator) {
    try { annotator.destroy() } catch (_) {}
    annotator = null
  }
})
</script>

<style scoped>
.label-edit { max-width: 900px; }
.editor-wrap { margin-top: 1rem; }
.image-wrap { margin-bottom: 1rem; max-width: 100%; overflow: auto; }
.image-wrap img { max-width: 100%; height: auto; display: block; }
.actions { margin-top: 0.5rem; }
button { padding: 0.4rem 1rem; cursor: pointer; }
button:disabled { opacity: 0.6; cursor: not-allowed; }
.error { color: #c00; margin: 0.5rem 0; }
</style>
