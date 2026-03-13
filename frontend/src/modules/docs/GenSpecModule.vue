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
    { label: 'Загрузка файла', at: 15 },
    { label: 'Распознавание элементов', at: 45 },
    { label: 'Формирование ведомости', at: 75 },
    { label: 'Финализация', at: 95 },
  ], 18000)
  try {
    result.value = await post('/api/generate-spec', null, { files: { file: file.value } })
  } catch { /* handled */ } finally {
    complete()
  }
}
</script>

<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
    <header class="mb-10 animate-fade-up">
      <span class="text-xs font-mono tracking-[0.2em] uppercase text-sage mb-2 block">Документация</span>
      <h1 class="font-display text-3xl sm:text-4xl text-carbon-900 mb-3">Генерация спецификации</h1>
      <p class="text-carbon-500 font-body">{{ store.cardDescriptions.genspec }}</p>
    </header>

    <section class="bg-white rounded-2xl border border-carbon-200/60 p-8 mb-8 animate-fade-up" style="animation-delay:80ms">
      <label class="block text-sm font-medium text-carbon-600 mb-2">Чертёж (PDF или DXF)</label>
      <input type="file" accept=".pdf,.dxf" @change="onFile"
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
          Генерация...
        </span>
        <span v-else>Сформировать ведомость</span>
      </button>
    </section>

    <div v-if="error" class="bg-status-fail/10 border border-status-fail/20 rounded-xl p-4 mb-8 text-sm text-status-fail">
      {{ error }}
    </div>

    <section v-if="result" class="bg-white rounded-2xl border border-carbon-200/60 p-8 animate-scale-in">
      <h2 class="font-display text-xl text-carbon-800 mb-6">Ведомость элементов</h2>

      <div v-if="result.spec?.length || result.items?.length" class="overflow-x-auto">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-carbon-200/60">
              <th class="text-left py-3 px-3 text-xs font-mono text-carbon-400 uppercase">Поз.</th>
              <th class="text-left py-3 px-3 text-xs font-mono text-carbon-400 uppercase">Наименование</th>
              <th class="text-left py-3 px-3 text-xs font-mono text-carbon-400 uppercase">Профиль</th>
              <th class="text-right py-3 px-3 text-xs font-mono text-carbon-400 uppercase">Длина</th>
              <th class="text-right py-3 px-3 text-xs font-mono text-carbon-400 uppercase">Кол-во</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(item, i) in (result.spec || result.items)" :key="i"
                class="border-b border-carbon-100 hover:bg-canvas transition-colors">
              <td class="py-3 px-3 font-mono text-carbon-500">{{ item.pos || item.position || i + 1 }}</td>
              <td class="py-3 px-3 text-carbon-700">{{ item.name || item.element }}</td>
              <td class="py-3 px-3 text-carbon-500 font-mono text-xs">{{ item.profile || item.article || '-' }}</td>
              <td class="py-3 px-3 text-right font-mono text-carbon-600">{{ item.length || '-' }}</td>
              <td class="py-3 px-3 text-right font-mono text-carbon-600">{{ item.qty || item.quantity || '-' }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <pre v-if="!result.spec && !result.items"
           class="bg-canvas rounded-xl p-6 text-xs font-mono text-carbon-600 overflow-x-auto whitespace-pre-wrap">{{ JSON.stringify(result, null, 2) }}</pre>
    </section>
  </div>
</template>
