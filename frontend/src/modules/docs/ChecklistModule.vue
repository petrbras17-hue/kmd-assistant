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
    { label: 'Загрузка PDF', at: 15 },
    { label: 'Анализ по категориям', at: 50 },
    { label: 'Формирование чек-листа', at: 80 },
    { label: 'Финализация', at: 95 },
  ], 15000)
  try {
    result.value = await post('/api/checklist', null, { files: { file: file.value } })
  } catch { /* handled */ } finally {
    complete()
  }
}

function categoryColor(score) {
  if (score >= 80) return 'bg-status-ok'
  if (score >= 50) return 'bg-status-warn'
  return 'bg-status-fail'
}
</script>

<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
    <header class="mb-10 animate-fade-up">
      <span class="text-xs font-mono tracking-[0.2em] uppercase text-sage mb-2 block">Документация</span>
      <h1 class="font-display text-3xl sm:text-4xl text-carbon-900 mb-3">Чек-лист КМД</h1>
      <p class="text-carbon-500 font-body">{{ store.cardDescriptions.checklist }}</p>
    </header>

    <section class="bg-white rounded-2xl border border-carbon-200/60 p-8 mb-8 animate-fade-up" style="animation-delay:80ms">
      <label class="block text-sm font-medium text-carbon-600 mb-2">PDF-чертёж КМД</label>
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
          Аудит...
        </span>
        <span v-else>Запустить аудит</span>
      </button>
    </section>

    <div v-if="error" class="bg-status-fail/10 border border-status-fail/20 rounded-xl p-4 mb-8 text-sm text-status-fail">
      {{ error }}
    </div>

    <section v-if="result" class="bg-white rounded-2xl border border-carbon-200/60 p-8 animate-scale-in">
      <h2 class="font-display text-xl text-carbon-800 mb-6">Результат аудита</h2>

      <!-- Categories -->
      <div v-if="result.categories?.length" class="space-y-4 mb-8">
        <div v-for="(cat, i) in result.categories" :key="i" class="bg-canvas rounded-xl p-5">
          <div class="flex items-center justify-between mb-3">
            <h3 class="text-sm font-medium text-carbon-700">{{ cat.name || cat.category }}</h3>
            <span class="text-xs font-mono"
                  :class="(cat.score || 0) >= 80 ? 'text-status-ok' : (cat.score || 0) >= 50 ? 'text-status-warn' : 'text-status-fail'">
              {{ cat.score || 0 }}%
            </span>
          </div>
          <div class="w-full h-2 bg-carbon-100 rounded-full overflow-hidden">
            <div class="h-full rounded-full transition-all duration-700"
                 :class="categoryColor(cat.score || 0)"
                 :style="{ width: `${cat.score || 0}%` }" />
          </div>
          <div v-if="cat.items?.length" class="mt-3 space-y-1.5">
            <div v-for="(item, j) in cat.items" :key="j" class="flex items-center gap-2 text-xs">
              <span class="w-1.5 h-1.5 rounded-full flex-shrink-0"
                    :class="item.ok || item.pass ? 'bg-status-ok' : 'bg-status-fail'" />
              <span class="text-carbon-500">{{ item.label || item.check }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Overall score -->
      <div v-if="result.total_score !== undefined" class="bg-canvas rounded-xl p-5 flex items-center gap-4">
        <span class="text-3xl font-display"
              :class="result.total_score >= 80 ? 'text-status-ok' : result.total_score >= 50 ? 'text-status-warn' : 'text-status-fail'">
          {{ result.total_score }}%
        </span>
        <span class="text-sm text-carbon-500">Общая оценка КМД</span>
      </div>

      <pre v-if="!result.categories && result.total_score === undefined"
           class="bg-canvas rounded-xl p-6 text-xs font-mono text-carbon-600 overflow-x-auto whitespace-pre-wrap">{{ JSON.stringify(result, null, 2) }}</pre>
    </section>
  </div>
</template>
