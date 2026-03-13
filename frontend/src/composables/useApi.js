import { ref } from 'vue'
import { useAppStore } from '@/stores/app'

const API_BASE = ''
const csrfToken = ref(null)

async function fetchCsrf() {
  if (csrfToken.value) return csrfToken.value
  try {
    const res = await fetch(`${API_BASE}/api/csrf-token`)
    const data = await res.json()
    csrfToken.value = data.csrf_token
    return csrfToken.value
  } catch {
    return null
  }
}

export function useApi() {
  const loading = ref(false)
  const error = ref(null)
  const data = ref(null)

  async function post(endpoint, body, { files } = {}) {
    loading.value = true
    error.value = null
    data.value = null

    try {
      const csrf = await fetchCsrf()
      const headers = {}
      if (csrf) headers['X-CSRF-Token'] = csrf

      let fetchBody
      if (files) {
        const fd = new FormData()
        for (const [key, file] of Object.entries(files)) {
          if (Array.isArray(file)) file.forEach(f => fd.append(key, f))
          else fd.append(key, file)
        }
        if (body) {
          for (const [key, val] of Object.entries(body)) {
            fd.append(key, typeof val === 'object' ? JSON.stringify(val) : val)
          }
        }
        fetchBody = fd
      } else {
        headers['Content-Type'] = 'application/json'
        fetchBody = JSON.stringify(body)
      }

      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: 'POST',
        headers,
        body: fetchBody,
      })

      if (!res.ok) {
        if (res.status === 403) csrfToken.value = null
        const errData = await res.json().catch(() => ({}))
        throw new Error(errData.detail || `Ошибка ${res.status}`)
      }

      data.value = await res.json()
      return data.value
    } catch (e) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function get(endpoint) {
    loading.value = true
    error.value = null
    data.value = null

    try {
      const res = await fetch(`${API_BASE}${endpoint}`)
      if (!res.ok) {
        const errData = await res.json().catch(() => ({}))
        throw new Error(errData.detail || `Ошибка ${res.status}`)
      }
      data.value = await res.json()
      return data.value
    } catch (e) {
      error.value = e.message
      throw e
    } finally {
      loading.value = false
    }
  }

  async function download(endpoint, filename) {
    const res = await fetch(`${API_BASE}${endpoint}`)
    if (!res.ok) throw new Error(`Ошибка загрузки ${res.status}`)
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = filename
    a.click()
    URL.revokeObjectURL(url)
  }

  return { loading, error, data, post, get, download }
}
