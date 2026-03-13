<script setup>
import { ref, onMounted } from 'vue'
import { useApi } from '@/composables/useApi'
import { useProgress } from '@/composables/useProgress'
import { useAppStore } from '@/stores/app'

const store = useAppStore()
const api = useApi()
const historyApi = useApi()
const { start, complete } = useProgress()

const file = ref(null)
const projectId = ref('')
const uploadResult = ref(null)
const history = ref([])

function onFile(e) { file.value = e.target.files[0] }

async function loadHistory() {
  try {
    const data = await historyApi.get('/api/versioning/history')
    history.value = data?.versions || data || []
  } catch { /* handled */ }
}

async function upload() {
  if (!file.value) return
  uploadResult.value = null
  start([
    { label: 'Загрузка файла', at: 30 },
    { label: 'Регистрация версии', at: 70 },
    { label: 'Обновление истории', at: 95 },
  ], 8000)
  try {
    uploadResult.value = await api.post('/api/versioning/upload', { project_id: projectId.value }, {
      files: { file: file.value },
    })
    await loadHistory()
  } catch { /* handled */ } finally {
    complete()
  }
}

onMounted(loadHistory)
</script>

<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
    <header class="mb-10 animate-fade-up">
      <span class="text-xs font-mono tracking-[0.2em] uppercase text-sage mb-2 block">Производство</span>
      <h1 class="font-display text-3xl sm:text-4xl text-carbon-900 mb-3">Версионирование</h1>
      <p class="text-carbon-500 font-body">{{ store.cardDescriptions.versioning }}</p>
    </header>

    <!-- Upload -->
    <section class="bg-white rounded-2xl border border-carbon-200/60 p-8 mb-8 animate-fade-up" style="animation-delay:80ms">
      <h2 class="text-sm font-medium text-carbon-700 mb-4">Загрузить новую версию</h2>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-5 mb-6">
        <div>
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">ID проекта</label>
          <input v-model="projectId" type="text" placeholder="project-001"
                 class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                        text-carbon-700 font-mono focus:outline-none focus:border-sage/50 focus:ring-1
                        focus:ring-sage/20 transition-colors" />
        </div>
        <div>
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">Файл документации</label>
          <input type="file" @change="onFile"
                 class="block w-full text-sm text-carbon-500 file:mr-4 file:py-2.5 file:px-4
                        file:rounded-lg file:border-0 file:text-sm file:font-medium
                        file:bg-sage-pale file:text-sage-dark hover:file:bg-sage/10
                        file:cursor-pointer file:transition-colors" />
        </div>
      </div>

      <button @click="upload" :disabled="!file || api.loading.value"
              class="px-6 py-3 bg-sage text-white text-sm font-medium rounded-xl
                     hover:bg-sage-dark disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
        <span v-if="api.loading.value" class="flex items-center gap-2">
          <svg class="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
          </svg>
          Загрузка...
        </span>
        <span v-else>Загрузить</span>
      </button>

      <div v-if="uploadResult" class="mt-4 bg-status-ok/10 border border-status-ok/20 rounded-xl p-4 text-sm text-status-ok">
        Версия {{ uploadResult.version || '' }} загружена успешно.
      </div>
    </section>

    <div v-if="api.error.value" class="bg-status-fail/10 border border-status-fail/20 rounded-xl p-4 mb-8 text-sm text-status-fail">
      {{ api.error.value }}
    </div>

    <!-- History -->
    <section class="bg-white rounded-2xl border border-carbon-200/60 p-8 animate-fade-up" style="animation-delay:160ms">
      <h2 class="font-display text-xl text-carbon-800 mb-6">История версий</h2>

      <div v-if="historyApi.loading.value" class="text-sm text-carbon-400">Загрузка...</div>

      <div v-else-if="history.length" class="space-y-3">
        <div v-for="(v, i) in history" :key="i"
             class="flex items-center gap-4 bg-canvas rounded-xl p-4">
          <div class="w-10 h-10 rounded-lg bg-sage-pale flex items-center justify-center flex-shrink-0">
            <span class="text-xs font-mono text-sage font-bold">v{{ v.version || i + 1 }}</span>
          </div>
          <div class="min-w-0 flex-1">
            <p class="text-sm text-carbon-700 truncate">{{ v.filename || v.file || 'Документ' }}</p>
            <p class="text-xs text-carbon-400">{{ v.uploaded_at || v.date || '' }} {{ v.project_id ? `| ${v.project_id}` : '' }}</p>
          </div>
          <span class="text-xs font-mono text-carbon-300">{{ v.size || '' }}</span>
        </div>
      </div>

      <p v-else class="text-sm text-carbon-400">Нет загруженных версий.</p>
    </section>
  </div>
</template>
