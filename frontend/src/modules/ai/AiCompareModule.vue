<script setup>
import { ref } from 'vue'
import { useApi } from '@/composables/useApi'
import { useProgress } from '@/composables/useProgress'
import { useAppStore } from '@/stores/app'

const store = useAppStore()
const { loading, error, post } = useApi()
const { start, complete } = useProgress()

const pdf1 = ref(null)
const pdf2 = ref(null)
const result = ref(null)

function onPdf1(e) { pdf1.value = e.target.files[0] }
function onPdf2(e) { pdf2.value = e.target.files[0] }

async function submit() {
  if (!pdf1.value || !pdf2.value) return
  result.value = null
  start([
    { label: 'Загрузка чертежей', at: 10 },
    { label: 'AI распознавание', at: 30 },
    { label: 'Визуальное сравнение', at: 60 },
    { label: 'Детекция различий', at: 85 },
    { label: 'Формирование отчёта', at: 95 },
  ], 30000)
  try {
    result.value = await post('/api/ai-compare-visual', null, {
      files: { pdf1: pdf1.value, pdf2: pdf2.value },
    })
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
      <h1 class="font-display text-3xl sm:text-4xl text-carbon-900 mb-3">Сравнение чертежей</h1>
      <p class="text-carbon-500 font-body">{{ store.cardDescriptions.aicompare }}</p>
    </header>

    <section class="bg-white rounded-2xl border border-carbon-200/60 p-8 mb-8 animate-fade-up" style="animation-delay:80ms">
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-6 mb-6">
        <div>
          <label class="block text-sm font-medium text-carbon-600 mb-2">Чертёж 1 (PDF)</label>
          <input type="file" accept=".pdf" @change="onPdf1"
                 class="block w-full text-sm text-carbon-500 file:mr-4 file:py-2.5 file:px-4
                        file:rounded-lg file:border-0 file:text-sm file:font-medium
                        file:bg-sage-pale file:text-sage-dark hover:file:bg-sage/10
                        file:cursor-pointer file:transition-colors" />
          <p v-if="pdf1" class="mt-2 text-xs text-carbon-400 font-mono truncate">{{ pdf1.name }}</p>
        </div>
        <div>
          <label class="block text-sm font-medium text-carbon-600 mb-2">Чертёж 2 (PDF)</label>
          <input type="file" accept=".pdf" @change="onPdf2"
                 class="block w-full text-sm text-carbon-500 file:mr-4 file:py-2.5 file:px-4
                        file:rounded-lg file:border-0 file:text-sm file:font-medium
                        file:bg-sage-pale file:text-sage-dark hover:file:bg-sage/10
                        file:cursor-pointer file:transition-colors" />
          <p v-if="pdf2" class="mt-2 text-xs text-carbon-400 font-mono truncate">{{ pdf2.name }}</p>
        </div>
      </div>

      <button @click="submit" :disabled="!pdf1 || !pdf2 || loading"
              class="px-6 py-3 bg-sage text-white text-sm font-medium rounded-xl
                     hover:bg-sage-dark disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
        <span v-if="loading" class="flex items-center gap-2">
          <svg class="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
          </svg>
          AI сравнение...
        </span>
        <span v-else>Сравнить визуально</span>
      </button>
    </section>

    <div v-if="error" class="bg-status-fail/10 border border-status-fail/20 rounded-xl p-4 mb-8 text-sm text-status-fail">
      {{ error }}
    </div>

    <section v-if="result" class="bg-white rounded-2xl border border-carbon-200/60 p-8 animate-scale-in">
      <h2 class="font-display text-xl text-carbon-800 mb-6">Результат AI сравнения</h2>

      <div v-if="result.differences?.length" class="space-y-3 mb-6">
        <div v-for="(diff, i) in result.differences" :key="i"
             class="bg-canvas rounded-xl p-4">
          <div class="flex items-center gap-2 mb-2">
            <span class="text-xs font-mono px-2 py-0.5 rounded"
                  :class="diff.severity === 'critical' ? 'bg-status-fail/10 text-status-fail' :
                          diff.severity === 'major' ? 'bg-status-warn/10 text-status-warn' :
                          'bg-status-info/10 text-status-info'">
              {{ diff.severity || 'info' }}
            </span>
            <span v-if="diff.area || diff.region" class="text-xs text-carbon-400 font-mono">{{ diff.area || diff.region }}</span>
          </div>
          <p class="text-sm text-carbon-700">{{ diff.description || diff.text }}</p>
        </div>
      </div>

      <div v-if="result.similarity !== undefined" class="bg-sage-pale rounded-xl p-5 flex items-center gap-4">
        <span class="text-3xl font-display text-sage">{{ result.similarity }}%</span>
        <span class="text-sm text-carbon-600">Визуальное сходство чертежей</span>
      </div>

      <div v-if="result.summary" class="mt-4 bg-canvas rounded-xl p-4 text-sm text-carbon-600 whitespace-pre-line">
        {{ result.summary }}
      </div>

      <pre v-if="!result.differences && result.similarity === undefined && !result.summary"
           class="bg-canvas rounded-xl p-6 text-xs font-mono text-carbon-600 overflow-x-auto whitespace-pre-wrap">{{ JSON.stringify(result, null, 2) }}</pre>
    </section>
  </div>
</template>
