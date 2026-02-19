const API_BASE = import.meta.env.VITE_API_BASE ?? (typeof location !== 'undefined' ? `${location.origin.replace(/:\d+$/, ':8081')}` : 'http://localhost:8081')

export function apiBase() {
  return API_BASE
}

export function datasetImagesUrl(datasetId, filename) {
  return `${API_BASE}/api/dataset/${encodeURIComponent(datasetId)}/images/${encodeURIComponent(filename)}`
}

export async function fetchApi(path, options = {}) {
  const url = path.startsWith('http') ? path : `${API_BASE}${path.startsWith('/') ? '' : '/'}${path}`
  const res = await fetch(url, { ...options, headers: { 'Accept': 'application/json', ...options.headers } })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || `HTTP ${res.status}`)
  }
  if (res.headers.get('content-type')?.includes('application/json')) return res.json()
  return res.text()
}

export async function putApi(path, body) {
  return fetchApi(path, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
}

/**
 * 이미지(프레임) 업로드. FormData 사용, Content-Type 은 설정하지 않음.
 * @param {string} datasetId
 * @param {File[]} files
 * @returns {Promise<{ dataset_id: string, saved: { filename: string, path: string }[] }>}
 */
export async function uploadFrames(datasetId, files) {
  const form = new FormData()
  form.append('dataset_id', datasetId)
  for (const file of files) {
    form.append('files', file)
  }
  const url = `${API_BASE}/api/dataset/frames`
  const res = await fetch(url, {
    method: 'POST',
    body: form,
    headers: { Accept: 'application/json' },
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || `HTTP ${res.status}`)
  }
  return res.json()
}
