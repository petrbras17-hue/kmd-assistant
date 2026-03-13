<script setup>
import { reactive, ref } from 'vue'
import { useApi } from '@/composables/useApi'
import { useProgress } from '@/composables/useProgress'
import { useAppStore } from '@/stores/app'

const store = useAppStore()
const { loading, error, post } = useApi()
const { start, complete } = useProgress()

const form = reactive({
  project_name: '',
  items: '',
  label_size: '50x25',
  include_logo: true,
  include_date: true,
})
const result = ref(null)

const labelSizes = ['50x25', '70x35', '100x50', '40x20']

async function submit() {
  result.value = null
  start([
    { label: 'Парсинг элементов', at: 25 },
    { label: 'Генерация QR-кодов', at: 60 },
    { label: 'Формирование макета', at: 90 },
  ], 8000)
  try {
    result.value = await post('/api/generate-qr', { ...form })
  } catch { /* handled */ } finally {
    complete()
  }
}
</script>

<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
    <header class="mb-10 animate-fade-up">
      <span class="text-xs font-mono tracking-[0.2em] uppercase text-sage mb-2 block">Производство</span>
      <h1 class="font-display text-3xl sm:text-4xl text-carbon-900 mb-3">Маркировка</h1>
      <p class="text-carbon-500 font-body">{{ store.cardDescriptions.qrlabels }}</p>
    </header>

    <section class="bg-white rounded-2xl border border-carbon-200/60 p-8 mb-8 animate-fade-up" style="animation-delay:80ms">
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-5 mb-6">
        <div>
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">Проект</label>
          <input v-model="form.project_name" type="text" placeholder="Наименование проекта"
                 class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                        text-carbon-700 focus:outline-none focus:border-sage/50 focus:ring-1
                        focus:ring-sage/20 transition-colors" />
        </div>
        <div>
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">Размер этикетки</label>
          <select v-model="form.label_size"
                  class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                         text-carbon-700 focus:outline-none focus:border-sage/50 focus:ring-1 focus:ring-sage/20">
            <option v-for="s in labelSizes" :key="s" :value="s">{{ s }} мм</option>
          </select>
        </div>
      </div>
      <div class="flex gap-4 mb-6">
        <label class="flex items-center gap-2 cursor-pointer">
          <input v-model="form.include_logo" type="checkbox"
                 class="w-4 h-4 rounded border-carbon-300 text-sage focus:ring-sage/30" />
          <span class="text-xs text-carbon-600">Логотип</span>
        </label>
        <label class="flex items-center gap-2 cursor-pointer">
          <input v-model="form.include_date" type="checkbox"
                 class="w-4 h-4 rounded border-carbon-300 text-sage focus:ring-sage/30" />
          <span class="text-xs text-carbon-600">Дата</span>
        </label>
      </div>
      <div class="mb-6">
        <label class="block text-xs font-medium text-carbon-500 mb-1.5">Элементы (JSON или по строкам)</label>
        <textarea v-model="form.items" rows="4"
                  placeholder='Поз. 1 — Стойка 1500мм&#10;Поз. 2 — Ригель 1200мм'
                  class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                         text-carbon-700 font-mono focus:outline-none focus:border-sage/50 focus:ring-1
                         focus:ring-sage/20 transition-colors resize-none" />
      </div>

      <button @click="submit" :disabled="loading"
              class="px-6 py-3 bg-sage text-white text-sm font-medium rounded-xl
                     hover:bg-sage-dark disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
        <span v-if="loading" class="flex items-center gap-2">
          <svg class="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
          </svg>
          Генерация...
        </span>
        <span v-else>Сгенерировать этикетки</span>
      </button>
    </section>

    <div v-if="error" class="bg-status-fail/10 border border-status-fail/20 rounded-xl p-4 mb-8 text-sm text-status-fail">
      {{ error }}
    </div>

    <section v-if="result" class="bg-white rounded-2xl border border-carbon-200/60 p-8 animate-scale-in">
      <h2 class="font-display text-xl text-carbon-800 mb-6">QR-этикетки</h2>

      <div v-if="result.labels?.length" class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4 mb-6">
        <div v-for="(lbl, i) in result.labels" :key="i"
             class="bg-canvas rounded-xl p-4 text-center">
          <div v-if="lbl.qr_data_url || lbl.qr_base64"
               class="w-20 h-20 mx-auto mb-2 bg-white rounded p-1">
            <img :src="lbl.qr_data_url || `data:image/png;base64,${lbl.qr_base64}`"
                 class="w-full h-full object-contain" alt="QR" />
          </div>
          <div v-else class="w-20 h-20 mx-auto mb-2 bg-white rounded flex items-center justify-center text-xs text-carbon-300 font-mono">
            QR
          </div>
          <p class="text-xs font-mono text-carbon-600 truncate">{{ lbl.label || lbl.id || `Поз. ${i + 1}` }}</p>
        </div>
      </div>

      <div v-if="result.total" class="bg-canvas rounded-xl p-4 text-sm text-carbon-600">
        Сгенерировано {{ result.total }} этикеток.
      </div>

      <pre v-if="!result.labels && !result.total"
           class="bg-canvas rounded-xl p-6 text-xs font-mono text-carbon-600 overflow-x-auto whitespace-pre-wrap">{{ JSON.stringify(result, null, 2) }}</pre>
    </section>
  </div>
</template>
