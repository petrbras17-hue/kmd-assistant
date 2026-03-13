<script setup>
import { ref } from 'vue'
import { useApi } from '@/composables/useApi'
import { useProgress } from '@/composables/useProgress'
import { useAppStore } from '@/stores/app'

const store = useAppStore()
const { loading, error, post } = useApi()
const { progress, start, complete } = useProgress()

const file1 = ref(null)
const file2 = ref(null)
const result = ref(null)

function onFile1(e) { file1.value = e.target.files[0] }
function onFile2(e) { file2.value = e.target.files[0] }

async function submit() {
  if (!file1.value || !file2.value) return
  result.value = null
  start([
    { label: 'Чтение файлов', at: 20 },
    { label: 'Парсинг спецификаций', at: 50 },
    { label: 'Сравнение данных', at: 80 },
    { label: 'Формирование отчёта', at: 95 },
  ], 12000)
  try {
    result.value = await post('/api/compare', null, {
      files: { file1: file1.value, file2: file2.value },
    })
  } catch { /* error handled by useApi */ } finally {
    complete()
  }
}
</script>

<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
    <!-- Header -->
    <header class="mb-10 animate-fade-up">
      <span class="text-xs font-mono tracking-[0.2em] uppercase text-sage mb-2 block">Документация</span>
      <h1 class="font-display text-3xl sm:text-4xl text-carbon-900 mb-3">Сравнение спецификаций</h1>
      <p class="text-carbon-500 font-body">{{ store.cardDescriptions.compare }}</p>
    </header>

    <!-- Input -->
    <section class="bg-white rounded-2xl border border-carbon-200/60 p-8 mb-8 animate-fade-up" style="animation-delay:80ms">
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-6 mb-6">
        <div>
          <label class="block text-sm font-medium text-carbon-600 mb-2">Файл 1 (XLSX)</label>
          <input type="file" accept=".xlsx,.xls" @change="onFile1"
                 class="block w-full text-sm text-carbon-500 file:mr-4 file:py-2.5 file:px-4
                        file:rounded-lg file:border-0 file:text-sm file:font-medium
                        file:bg-sage-pale file:text-sage-dark hover:file:bg-sage/10
                        file:cursor-pointer file:transition-colors" />
          <p v-if="file1" class="mt-2 text-xs text-carbon-400 font-mono truncate">{{ file1.name }}</p>
        </div>
        <div>
          <label class="block text-sm font-medium text-carbon-600 mb-2">Файл 2 (XLSX)</label>
          <input type="file" accept=".xlsx,.xls" @change="onFile2"
                 class="block w-full text-sm text-carbon-500 file:mr-4 file:py-2.5 file:px-4
                        file:rounded-lg file:border-0 file:text-sm file:font-medium
                        file:bg-sage-pale file:text-sage-dark hover:file:bg-sage/10
                        file:cursor-pointer file:transition-colors" />
          <p v-if="file2" class="mt-2 text-xs text-carbon-400 font-mono truncate">{{ file2.name }}</p>
        </div>
      </div>

      <button
        @click="submit"
        :disabled="!file1 || !file2 || loading"
        class="px-6 py-3 bg-sage text-white text-sm font-medium rounded-xl
               hover:bg-sage-dark disabled:opacity-40 disabled:cursor-not-allowed
               transition-colors duration-200"
      >
        <span v-if="loading" class="flex items-center gap-2">
          <svg class="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
          </svg>
          Сравнение...
        </span>
        <span v-else>Сравнить</span>
      </button>
    </section>

    <!-- Error -->
    <div v-if="error" class="bg-status-fail/10 border border-status-fail/20 rounded-xl p-4 mb-8 text-sm text-status-fail">
      {{ error }}
    </div>

    <!-- Results -->
    <section v-if="result" class="bg-white rounded-2xl border border-carbon-200/60 p-8 animate-scale-in">
      <h2 class="font-display text-xl text-carbon-800 mb-6">Результат сравнения</h2>

      <!-- Summary -->
      <div v-if="result.summary" class="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
        <div v-for="(val, key) in result.summary" :key="key"
             class="bg-canvas rounded-xl p-4 text-center">
          <p class="text-2xl font-display text-carbon-800">{{ val }}</p>
          <p class="text-xs text-carbon-400 mt-1 font-mono">{{ key }}</p>
        </div>
      </div>

      <!-- Differences table -->
      <div v-if="result.differences?.length" class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-carbon-200/60">
              <th class="text-left py-3 px-4 text-xs font-mono text-carbon-400 uppercase">Позиция</th>
              <th class="text-left py-3 px-4 text-xs font-mono text-carbon-400 uppercase">Поле</th>
              <th class="text-left py-3 px-4 text-xs font-mono text-carbon-400 uppercase">Файл 1</th>
              <th class="text-left py-3 px-4 text-xs font-mono text-carbon-400 uppercase">Файл 2</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(diff, i) in result.differences" :key="i"
                class="border-b border-carbon-100 hover:bg-canvas transition-colors">
              <td class="py-3 px-4 font-mono text-carbon-600">{{ diff.position || diff.row }}</td>
              <td class="py-3 px-4 text-carbon-600">{{ diff.field || diff.column }}</td>
              <td class="py-3 px-4 text-status-fail">{{ diff.value1 || diff.file1 }}</td>
              <td class="py-3 px-4 text-status-ok">{{ diff.value2 || diff.file2 }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Raw JSON fallback -->
      <pre v-if="!result.differences && !result.summary"
           class="bg-canvas rounded-xl p-6 text-xs font-mono text-carbon-600 overflow-x-auto whitespace-pre-wrap">{{ JSON.stringify(result, null, 2) }}</pre>
    </section>
  </div>
</template>
