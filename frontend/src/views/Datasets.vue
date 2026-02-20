<template>
  <div class="datasets root-wrap">
    <h1>데이터셋</h1>
    <section class="card">
      <h2>데이터셋 목록</h2>
      <p class="step-desc">기존 데이터셋을 선택해 이어하기 또는 학습 경로를 확인하세요.</p>
      <label>
        데이터셋 선택
        <select v-model="selectedId" class="select-id">
          <option value="">선택하세요</option>
          <option v-for="id in datasetIds" :key="id" :value="id">{{ id }}</option>
        </select>
      </label>
      <label v-if="selectedId === '' && datasetIds.length === 0" class="muted">등록된 데이터셋이 없습니다. 작업하기에서 이미지를 업로드하면 세션이 생성됩니다.</label>
    </section>
    <template v-if="selectedId">
      <section class="card">
        <h2>선택한 데이터셋: {{ selectedId }}</h2>
        <div class="row">
          <router-link :to="workLink" class="btn-work">이 데이터셋으로 작업하기</router-link>
        </div>
        <p v-if="imageCount !== null" class="summary">이미지 {{ imageCount }}개</p>
        <p v-if="refinedCount !== null" class="refined-count">정제된 데이터(검수 완료): {{ refinedCount }}개</p>
      </section>
      <section class="card card-train">
        <h2>이 데이터셋으로 학습하려면</h2>
        <p>아래 경로와 CLI 예시를 사용해 학습을 실행할 수 있습니다. 검수 완료한 정제된 데이터만 학습에 쓰려면 작업하기에서 «정제된 데이터만 보기»로 확인하세요.</p>
        <label v-if="dataYamlPath" class="block-label">data.yaml 경로</label>
        <pre v-if="dataYamlPath" class="path-block">{{ dataYamlPath }}</pre>
        <label class="block-label">CLI 예시 (복사 후 터미널에서 실행)</label>
        <pre class="path-block">{{ trainCommandExample || '—' }}</pre>
      </section>
    </template>
  </div>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { fetchApi } from '../api'

const router = useRouter()
const datasetIds = ref([])
const selectedId = ref('')
const dataYamlPath = ref('')
const trainCommandExample = ref('')
const imageCount = ref(null)
const refinedCount = ref(null)

const workLink = ref({ name: 'Labeling', query: {} })

function updateWorkLink() {
  if (selectedId.value) {
    workLink.value = { name: 'Labeling', query: { dataset_id: selectedId.value } }
  } else {
    workLink.value = { name: 'Labeling', query: {} }
  }
}

async function loadDatasetList() {
  try {
    const data = await fetchApi('/api/datasets')
    datasetIds.value = data.dataset_ids || []
  } catch (_) {
    datasetIds.value = []
  }
}

async function loadSelectedInfo() {
  const id = selectedId.value
  if (!id) {
    dataYamlPath.value = ''
    trainCommandExample.value = ''
    imageCount.value = null
    refinedCount.value = null
    return
  }
  updateWorkLink()
  try {
    const [imagesData, info] = await Promise.all([
      fetchApi(`/api/dataset/${encodeURIComponent(id)}/images`).catch(() => ({ images: [] })),
      fetchApi(`/api/dataset/${encodeURIComponent(id)}/info?refined_only=true`).catch(() => ({})),
    ])
    const images = imagesData.images || []
    imageCount.value = images.length
    dataYamlPath.value = info.data_yaml_path || ''
    trainCommandExample.value = info.train_command_example || ''
    refinedCount.value = info.refined_count ?? null
  } catch (_) {
    imageCount.value = null
    refinedCount.value = null
    dataYamlPath.value = ''
    trainCommandExample.value = ''
  }
}

watch(selectedId, () => {
  loadSelectedInfo()
})

onMounted(() => {
  loadDatasetList()
  if (selectedId.value) loadSelectedInfo()
  else updateWorkLink()
})
</script>

<style scoped>
.datasets { max-width: 720px; }
.root-wrap { margin: 0; }
.card { margin-bottom: 1.5rem; padding: 1rem; border: 1px solid #ddd; border-radius: 8px; }
.card h2 { margin-top: 0; font-size: 1.1rem; }
.step-desc { font-size: 0.9rem; color: #555; margin: 0.25rem 0 0.75rem; }
.row { margin: 0.5rem 0; }
.select-id { margin-left: 0.5rem; padding: 0.35rem; min-width: 200px; }
.btn-work { display: inline-block; padding: 0.4rem 1rem; background: #1a1a2e; color: #fff; border-radius: 6px; text-decoration: none; font-size: 0.95rem; }
.btn-work:hover { opacity: 0.9; }
.summary { font-size: 0.9rem; margin: 0.25rem 0; }
.refined-count { font-size: 0.9rem; color: #066; margin: 0.25rem 0; }
.block-label { display: block; margin-top: 0.75rem; font-weight: 600; }
.path-block { margin: 0.25rem 0; padding: 0.5rem; background: #f5f5f5; border-radius: 4px; overflow-x: auto; font-size: 0.85rem; white-space: pre-wrap; word-break: break-all; }
.card-train { margin-top: 0; }
.muted { font-size: 0.9rem; color: #666; margin-left: 0.5rem; }
label { display: block; margin: 0.5rem 0; }
</style>
