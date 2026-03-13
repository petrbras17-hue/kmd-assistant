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
    { label: 'Загрузка чертежа', at: 10 },
    { label: 'AI анализ структуры', at: 30 },
    { label: 'Проверка соответствия ГОСТ', at: 55 },
    { label: 'Выявление замечаний', at: 80 },
    { label: 'Формирование ревью', at: 95 },
  ], 25000)
  try {
    result.value = await post('/api/ai-review', null, { files: { file: file.value } })
  } catch { /* handled */ } finally {
    complete()
  }
}
</script>

<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
    <header class="mb-10 animate-fade-up">
      <span class="text-xs font-mono tracking-[0.2em] uppercase text-sage mb-2 block">
        <span class="inline-block w-1.5 h-1.5 rounded-full bg-sage mr-1.5 animate-pulse-glow" />
        AI инструменты
      </span>
      <h1 class="font-display text-3xl sm:text-4xl text-carbon-900 mb-3">Ревью чертежа</h1>
      <p class="text-carbon-500 font-body">{{ store.cardDescriptions.aireview }}</p>
    </header>

    <section class="bg-white rounded-2xl border border-carbon-200/60 p-8 mb-8 animate-fade-up" style="animation-delay:80ms">
      <label class="block text-sm font-medium text-carbon-600 mb-2">PDF-чертёж</label>
      <input type="file" accept=".pdf" @change="onFile"
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
          AI анализ...
        </span>
        <span v-else>Запустить ревью</span>
      </button>
    </section>

    <div v-if="error" class="bg-status-fail/10 border border-status-fail/20 rounded-xl p-4 mb-8 text-sm text-status-fail">
      {{ error }}
    </div>

    <section v-if="result" class="bg-white rounded-2xl border border-carbon-200/60 p-8 animate-scale-in">
      <h2 class="font-display text-xl text-carbon-800 mb-6">AI ревью</h2>

      <!-- Issues -->
      <div v-if="result.issues?.length" class="space-y-3 mb-6">
        <div v-for="(issue, i) in result.issues" :key="i"
             class="bg-canvas rounded-xl p-4 flex items-start gap-3">
          <span class="w-6 h-6 rounded-lg flex items-center justify-center flex-shrink-0 text-xs font-mono mt-0.5"
                :class="issue.severity === 'error' ? 'bg-status-fail/10 text-status-fail' :
                        issue.severity === 'warning' ? 'bg-status-warn/10 text-status-warn' :
                        'bg-status-info/10 text-status-info'">
            {{ i + 1 }}
          </span>
          <div>
            <p class="text-sm font-medium text-carbon-700">{{ issue.title || issue.message }}</p>
            <p v-if="issue.detail || issue.suggestion" class="text-xs text-carbon-400 mt-1">
              {{ issue.detail || issue.suggestion }}
            </p>
            <span v-if="issue.gost" class="inline-block mt-1.5 text-xs font-mono text-sage bg-sage-pale px-2 py-0.5 rounded">
              {{ issue.gost }}
            </span>
          </div>
        </div>
      </div>

      <!-- Summary text -->
      <div v-if="result.summary || result.review" class="bg-canvas rounded-xl p-6">
        <p class="text-sm text-carbon-600 leading-relaxed whitespace-pre-line">{{ result.summary || result.review }}</p>
      </div>

      <!-- Score -->
      <div v-if="result.score !== undefined" class="mt-6 bg-sage-pale rounded-xl p-5 flex items-center gap-4">
        <span class="text-3xl font-display text-sage">{{ result.score }}/10</span>
        <span class="text-sm text-carbon-600">Оценка качества чертежа</span>
      </div>

      <pre v-if="!result.issues && !result.summary && !result.review && result.score === undefined"
           class="bg-canvas rounded-xl p-6 text-xs font-mono text-carbon-600 overflow-x-auto whitespace-pre-wrap">{{ JSON.stringify(result, null, 2) }}</pre>
    </section>
  </div>
</template>
