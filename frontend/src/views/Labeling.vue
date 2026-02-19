<template>
  <div class="labeling">
    <h1>라벨링</h1>
    <section class="card">
      <h2>1. 데이터셋</h2>
      <label>
        데이터셋 선택
        <select v-model="selectedId" class="select-id">
          <option value="">새 데이터셋 (직접 입력)</option>
          <option v-for="id in datasetIds" :key="id" :value="id">{{ id }}</option>
        </select>
      </label>
      <label v-if="selectedId === ''">
        데이터셋 ID <input v-model="customId" type="text" placeholder="default" />
      </label>
      <div class="row">
        <button type="button" @click="loadImages">이미지 목록 불러오기</button>
      </div>
      <h3 class="sub">이미지 업로드</h3>
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
      <h2>2. 자동 라벨</h2>
      <p v-if="classNames.length">클래스: {{ classNames.join(', ') }}</p>
      <label>클래스명 (쉼표 구분) <input v-model="classNamesInput" type="text" placeholder="person, car, dog" /></label>
      <button type="button" :disabled="autoLabelLoading" @click="runAutoLabel">{{ autoLabelLoading ? '실행 중…' : '자동 라벨 실행' }}</button>
      <p v-if="autoLabelResult" class="result">{{ autoLabelResult }}</p>
    </section>
    <section v-if="images.length" class="card">
      <h2>3. 수정/보완 (오픈소스 에디터)</h2>
      <p>이미지별로 bbox를 그리거나 수정한 뒤 저장할 수 있습니다.</p>
      <ul class="image-list">
        <li v-for="img in images" :key="img.filename">
          <img :src="datasetImagesUrl(datasetId, img.filename)" :alt="img.filename" class="thumb" loading="lazy" />
          <span class="name">{{ img.filename }}</span>
          <router-link :to="editLink(img)" class="btn-edit">편집</router-link>
        </li>
      </ul>
    </section>
    <p v-else class="muted">데이터셋을 선택하거나 새 ID를 입력한 뒤 이미지를 업로드하거나 «이미지 목록 불러오기»를 누르세요.</p>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { fetchApi, datasetImagesUrl, uploadFrames } from '../api'

const datasetIds = ref([])
const selectedId = ref('')
const customId = ref('default')
const datasetId = computed(() => selectedId.value || customId.value || 'default')

const fileInput = ref(null)
const uploading = ref(false)
const uploadResult = ref('')

const images = ref([])
const classNames = ref([])
const classNamesInput = ref('')
const autoLabelLoading = ref(false)
const autoLabelResult = ref('')

function editLink(img) {
  return { name: 'LabelEdit', params: { datasetId: datasetId.value, filename: img.filename } }
}

async function loadDatasetList() {
  try {
    const data = await fetchApi('/api/datasets')
    datasetIds.value = data.dataset_ids || []
  } catch (_) {
    datasetIds.value = []
  }
}

async function loadImages() {
  uploadResult.value = ''
  autoLabelResult.value = ''
  try {
    const data = await fetchApi(`/api/dataset/${encodeURIComponent(datasetId.value)}/images`)
    images.value = data.images || []
    const info = await fetchApi(`/api/dataset/${encodeURIComponent(datasetId.value)}/info`).catch(() => ({}))
    classNames.value = info.class_names || []
    if (classNames.value.length) classNamesInput.value = classNames.value.join(', ')
  } catch (e) {
    images.value = []
    classNames.value = []
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
  uploading.value = true
  uploadResult.value = ''
  try {
    const data = await uploadFrames(datasetId.value, files)
    const n = data.saved?.length ?? 0
    uploadResult.value = `${n}개 업로드됨.`
    input.value = ''
    await loadDatasetList()
    await loadImages()
  } catch (e) {
    uploadResult.value = `업로드 실패: ${e.message}`
  } finally {
    uploading.value = false
  }
}

async function runAutoLabel() {
  const names = classNamesInput.value.split(',').map((s) => s.trim()).filter(Boolean)
  if (!names.length) {
    autoLabelResult.value = '클래스명을 입력하세요.'
    return
  }
  autoLabelLoading.value = true
  autoLabelResult.value = ''
  try {
    const data = await fetchApi(`/api/dataset/${encodeURIComponent(datasetId.value)}/auto-label`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ class_names: names, provider: 'yoloworld', conf_threshold: 0.25 }),
    })
    autoLabelResult.value = `완료: ${data.labeled_count}개 이미지 라벨 생성.`
    classNames.value = data.class_names || names
    loadImages()
  } catch (e) {
    autoLabelResult.value = `오류: ${e.message}`
  } finally {
    autoLabelLoading.value = false
  }
}

onMounted(() => {
  loadDatasetList()
})
</script>

<style scoped>
.labeling { max-width: 720px; }
.card { margin-bottom: 1.5rem; padding: 1rem; border: 1px solid #ddd; border-radius: 8px; }
.card h2 { margin-top: 0; font-size: 1.1rem; }
.card h3.sub { font-size: 0.95rem; margin: 1rem 0 0.5rem; }
.row { margin: 0.5rem 0; }
label { display: block; margin: 0.5rem 0; }
.select-id { margin-left: 0.5rem; padding: 0.35rem; min-width: 200px; }
input[type="text"] { margin-left: 0.5rem; padding: 0.35rem; width: 280px; }
.upload-row { display: flex; align-items: center; gap: 0.5rem; margin: 0.5rem 0; }
.file-input { flex: 1; max-width: 280px; }
button { padding: 0.4rem 0.8rem; cursor: pointer; }
button:disabled { opacity: 0.6; cursor: not-allowed; }
.result { margin-top: 0.5rem; color: #0a0; }
.image-list { list-style: none; padding: 0; margin: 0; }
.image-list li { display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.5rem; padding: 0.25rem 0; border-bottom: 1px solid #eee; }
.thumb { width: 64px; height: 48px; object-fit: cover; border-radius: 4px; }
.name { flex: 1; font-size: 0.9rem; overflow: hidden; text-overflow: ellipsis; }
.btn-edit { padding: 0.3rem 0.6rem; background: #1a1a2e; color: #fff; border-radius: 4px; text-decoration: none; font-size: 0.9rem; }
.btn-edit:hover { opacity: 0.9; }
.muted { color: #666; }
</style>
