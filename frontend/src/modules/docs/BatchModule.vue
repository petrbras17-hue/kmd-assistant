<script setup>
import { ref } from 'vue'
import { useApi } from '@/composables/useApi'
import { useProgress } from '@/composables/useProgress'
import { useAppStore } from '@/stores/app'

const store = useAppStore()
const { loading, error, post } = useApi()
const { start, complete } = useProgress()

const file = ref(null)
const result = ref(null)

function onFile(e) { file.value = e.target.files[0] }

async function submit() {
  if (!file.value) return
  result.value = null
  start([
    { label: 'Загрузка архива', at: 10 },
    { label: 'Распаковка файлов', at: 25 },
    { label: 'Обработка документов', at: 60 },
    { label: 'Агрегация результатов', at: 85 },
    { label: 'Финализация', at: 95 },
  ], 30000)
  try {
    result.value = await post('/api/batch-process', null, { files: { file: file.value } })
  } catch { /* handled */ } finally {
    complete()
  }
}
</script>

<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
    <header class="mb-10 animate-fade-up">
      <span class="text-xs font-mono tracking-[0.2em] uppercase text-sage mb-2 block">Документация</span>
      <h1 class="font-display text-3xl sm:text-4xl text-carbon-900 mb-3">Пакетная обработка</h1>
      <p class="text-carbon-500 font-body">{{ store.cardDescriptions.batch }}</p>
    </header>

    <section class="bg-white rounded-2xl border border-carbon-200/60 p-8 mb-8 animate-fade-up" style="animation-delay:80ms">
      <label class="block text-sm font-medium text-carbon-600 mb-2">Архив проекта (ZIP)</label>
      <input type="file" accept=".zip" @change="onFile"
             class="block w-full text-sm text-carbon-500 file:mr-4 file:py-2.5 file:px-4
                    file:rounded-lg file:border-0 file:text-sm file:font-medium
                    file:bg-sage-pale file:text-sage-dark hover:file:bg-sage/10
                    file:cursor-pointer file:transition-colors" />
      <p v-if="file" class="mt-2 text-xs text-carbon-400 font-mono truncate">{{ file.name }}</p>

      <button @click="submit" :disabled="!file || loading"
              class="mt-6 px-6 py-3 bg-sage text-white text-sm font-medium rounded-xl
                     hover:bg-sage-dark disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
        <span v-if="loading" class="flex items-center gap-2">
          <svg class="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
          </svg>
          Обработка...
        </span>
        <span v-else>Запустить обработку</span>
      </button>
    </section>

    <div v-if="error" class="bg-status-fail/10 border border-status-fail/20 rounded-xl p-4 mb-8 text-sm text-status-fail">
      {{ error }}
    </div>

    <section v-if="result" class="bg-white rounded-2xl border border-carbon-200/60 p-8 animate-scale-in">
      <h2 class="font-display text-xl text-carbon-800 mb-6">Результаты пакетной обработки</h2>

      <!-- Summary stats -->
      <div v-if="result.total !== undefined" class="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
        <div class="bg-canvas rounded-xl p-4 text-center">
          <p class="text-2xl font-display text-carbon-800">{{ result.total }}</p>
          <p class="text-xs text-carbon-400 mt-1 font-mono">Всего</p>
        </div>
        <div class="bg-canvas rounded-xl p-4 text-center">
          <p class="text-2xl font-display text-status-ok">{{ result.success || 0 }}</p>
          <p class="text-xs text-carbon-400 mt-1 font-mono">Успешно</p>
        </div>
        <div class="bg-canvas rounded-xl p-4 text-center">
          <p class="text-2xl font-display text-status-warn">{{ result.warnings || 0 }}</p>
          <p class="text-xs text-carbon-400 mt-1 font-mono">С замечаниями</p>
        </div>
        <div class="bg-canvas rounded-xl p-4 text-center">
          <p class="text-2xl font-display text-status-fail">{{ result.errors || 0 }}</p>
          <p class="text-xs text-carbon-400 mt-1 font-mono">Ошибки</p>
        </div>
      </div>

      <!-- Files list -->
      <div v-if="result.results?.length" class="space-y-3">
        <div v-for="(r, i) in result.results" :key="i"
             class="bg-canvas rounded-xl p-4 flex items-start gap-3">
          <span class="w-2 h-2 rounded-full mt-1.5 flex-shrink-0"
                :class="r.status === 'ok' ? 'bg-status-ok' : r.status === 'warn' ? 'bg-status-warn' : 'bg-status-fail'" />
          <div class="min-w-0 flex-1">
            <p class="text-sm font-medium text-carbon-700 truncate">{{ r.filename || r.file }}</p>
            <p class="text-xs text-carbon-400 mt-0.5">{{ r.message || r.detail || r.status }}</p>
          </div>
        </div>
      </div>

      <pre v-if="!result.results && result.total === undefined"
           class="bg-canvas rounded-xl p-6 text-xs font-mono text-carbon-600 overflow-x-auto whitespace-pre-wrap">{{ JSON.stringify(result, null, 2) }}</pre>
    </section>
  </div>
</template>
