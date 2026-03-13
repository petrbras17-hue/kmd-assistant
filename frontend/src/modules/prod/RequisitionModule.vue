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
    { label: 'Чтение спецификации', at: 20 },
    { label: 'Расчёт потребности', at: 50 },
    { label: 'Формирование заявки', at: 80 },
    { label: 'Финализация', at: 95 },
  ], 12000)
  try {
    result.value = await post('/api/generate-requisition', null, { files: { file: file.value } })
  } catch { /* handled */ } finally {
    complete()
  }
}
</script>

<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
    <header class="mb-10 animate-fade-up">
      <span class="text-xs font-mono tracking-[0.2em] uppercase text-sage mb-2 block">Производство</span>
      <h1 class="font-display text-3xl sm:text-4xl text-carbon-900 mb-3">Заявка на материалы</h1>
      <p class="text-carbon-500 font-body">{{ store.cardDescriptions.requisition }}</p>
    </header>

    <section class="bg-white rounded-2xl border border-carbon-200/60 p-8 mb-8 animate-fade-up" style="animation-delay:80ms">
      <label class="block text-sm font-medium text-carbon-600 mb-2">Спецификация (XLSX)</label>
      <input type="file" accept=".xlsx,.xls" @change="onFile"
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
          Формирование...
        </span>
        <span v-else>Сформировать заявку</span>
      </button>
    </section>

    <div v-if="error" class="bg-status-fail/10 border border-status-fail/20 rounded-xl p-4 mb-8 text-sm text-status-fail">
      {{ error }}
    </div>

    <section v-if="result" class="bg-white rounded-2xl border border-carbon-200/60 p-8 animate-scale-in">
      <h2 class="font-display text-xl text-carbon-800 mb-6">Заявка на закупку</h2>

      <div v-if="result.items?.length || result.materials?.length" class="overflow-x-auto mb-6">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-carbon-200/60">
              <th class="text-left py-3 px-3 text-xs font-mono text-carbon-400 uppercase">N</th>
              <th class="text-left py-3 px-3 text-xs font-mono text-carbon-400 uppercase">Наименование</th>
              <th class="text-left py-3 px-3 text-xs font-mono text-carbon-400 uppercase">Артикул</th>
              <th class="text-right py-3 px-3 text-xs font-mono text-carbon-400 uppercase">Кол-во</th>
              <th class="text-left py-3 px-3 text-xs font-mono text-carbon-400 uppercase">Ед.</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(item, i) in (result.items || result.materials)" :key="i"
                class="border-b border-carbon-100 hover:bg-canvas transition-colors">
              <td class="py-3 px-3 font-mono text-carbon-500">{{ i + 1 }}</td>
              <td class="py-3 px-3 text-carbon-700">{{ item.name || item.material }}</td>
              <td class="py-3 px-3 font-mono text-xs text-carbon-500">{{ item.article || '-' }}</td>
              <td class="py-3 px-3 text-right font-mono text-carbon-600">{{ item.quantity || item.qty }}</td>
              <td class="py-3 px-3 text-carbon-400 text-xs">{{ item.unit || 'шт' }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="result.total_weight || result.total_cost" class="flex gap-4">
        <div v-if="result.total_weight" class="bg-canvas rounded-xl p-4 text-center flex-1">
          <p class="text-xl font-display text-carbon-700">{{ result.total_weight }}</p>
          <p class="text-xs text-carbon-400 mt-1 font-mono">Общий вес, кг</p>
        </div>
        <div v-if="result.total_cost" class="bg-canvas rounded-xl p-4 text-center flex-1">
          <p class="text-xl font-display text-carbon-700">{{ result.total_cost }}</p>
          <p class="text-xs text-carbon-400 mt-1 font-mono">Ориент. стоимость</p>
        </div>
      </div>

      <pre v-if="!result.items && !result.materials"
           class="bg-canvas rounded-xl p-6 text-xs font-mono text-carbon-600 overflow-x-auto whitespace-pre-wrap">{{ JSON.stringify(result, null, 2) }}</pre>
    </section>
  </div>
</template>
