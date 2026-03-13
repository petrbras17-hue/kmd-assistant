<script setup>
import { ref } from 'vue'
import { useApi } from '@/composables/useApi'
import { useProgress } from '@/composables/useProgress'
import { useAppStore } from '@/stores/app'

const store = useAppStore()
const { loading, error, post } = useApi()
const { start, complete } = useProgress()

const pdfFile = ref(null)
const xlsxFile = ref(null)
const result = ref(null)

function onPdf(e) { pdfFile.value = e.target.files[0] }
function onXlsx(e) { xlsxFile.value = e.target.files[0] }

async function submit() {
  if (!pdfFile.value || !xlsxFile.value) return
  result.value = null
  start([
    { label: 'Загрузка файлов', at: 15 },
    { label: 'Парсинг PDF', at: 35 },
    { label: 'Парсинг XLSX', at: 55 },
    { label: 'Кросс-валидация', at: 80 },
    { label: 'Формирование отчёта', at: 95 },
  ], 20000)
  try {
    result.value = await post('/api/cross-validate', null, {
      files: { pdf_file: pdfFile.value, xlsx_file: xlsxFile.value },
    })
  } catch { /* handled */ } finally {
    complete()
  }
}
</script>

<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
    <header class="mb-10 animate-fade-up">
      <span class="text-xs font-mono tracking-[0.2em] uppercase text-sage mb-2 block">Документация</span>
      <h1 class="font-display text-3xl sm:text-4xl text-carbon-900 mb-3">Кросс-валидация</h1>
      <p class="text-carbon-500 font-body">{{ store.cardDescriptions.crossval }}</p>
    </header>

    <section class="bg-white rounded-2xl border border-carbon-200/60 p-8 mb-8 animate-fade-up" style="animation-delay:80ms">
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-6 mb-6">
        <div>
          <label class="block text-sm font-medium text-carbon-600 mb-2">PDF-чертёж</label>
          <input type="file" accept=".pdf" @change="onPdf"
                 class="block w-full text-sm text-carbon-500 file:mr-4 file:py-2.5 file:px-4
                        file:rounded-lg file:border-0 file:text-sm file:font-medium
                        file:bg-sage-pale file:text-sage-dark hover:file:bg-sage/10
                        file:cursor-pointer file:transition-colors" />
          <p v-if="pdfFile" class="mt-2 text-xs text-carbon-400 font-mono truncate">{{ pdfFile.name }}</p>
        </div>
        <div>
          <label class="block text-sm font-medium text-carbon-600 mb-2">Спецификация (XLSX)</label>
          <input type="file" accept=".xlsx,.xls" @change="onXlsx"
                 class="block w-full text-sm text-carbon-500 file:mr-4 file:py-2.5 file:px-4
                        file:rounded-lg file:border-0 file:text-sm file:font-medium
                        file:bg-sage-pale file:text-sage-dark hover:file:bg-sage/10
                        file:cursor-pointer file:transition-colors" />
          <p v-if="xlsxFile" class="mt-2 text-xs text-carbon-400 font-mono truncate">{{ xlsxFile.name }}</p>
        </div>
      </div>

      <button @click="submit" :disabled="!pdfFile || !xlsxFile || loading"
              class="px-6 py-3 bg-sage text-white text-sm font-medium rounded-xl
                     hover:bg-sage-dark disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
        <span v-if="loading" class="flex items-center gap-2">
          <svg class="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
          </svg>
          Валидация...
        </span>
        <span v-else>Валидировать</span>
      </button>
    </section>

    <div v-if="error" class="bg-status-fail/10 border border-status-fail/20 rounded-xl p-4 mb-8 text-sm text-status-fail">
      {{ error }}
    </div>

    <section v-if="result" class="bg-white rounded-2xl border border-carbon-200/60 p-8 animate-scale-in">
      <h2 class="font-display text-xl text-carbon-800 mb-6">Результат кросс-валидации</h2>

      <div v-if="result.mismatches?.length" class="space-y-3 mb-6">
        <div v-for="(m, i) in result.mismatches" :key="i"
             class="bg-canvas rounded-xl p-4 flex items-start gap-3">
          <span class="w-2 h-2 rounded-full bg-status-fail mt-1.5 flex-shrink-0" />
          <div>
            <p class="text-sm font-medium text-carbon-700">{{ m.field || m.element }}</p>
            <p class="text-xs text-carbon-400">PDF: {{ m.pdf_value }} | XLSX: {{ m.xlsx_value }}</p>
          </div>
        </div>
      </div>

      <div v-if="result.match_rate !== undefined" class="bg-canvas rounded-xl p-5 flex items-center gap-4">
        <span class="text-3xl font-display"
              :class="result.match_rate >= 90 ? 'text-status-ok' : result.match_rate >= 70 ? 'text-status-warn' : 'text-status-fail'">
          {{ result.match_rate }}%
        </span>
        <span class="text-sm text-carbon-500">Совпадение данных</span>
      </div>

      <pre v-if="!result.mismatches && result.match_rate === undefined"
           class="bg-canvas rounded-xl p-6 text-xs font-mono text-carbon-600 overflow-x-auto whitespace-pre-wrap">{{ JSON.stringify(result, null, 2) }}</pre>
    </section>
  </div>
</template>
