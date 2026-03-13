<script setup>
import { reactive, ref } from 'vue'
import { useApi } from '@/composables/useApi'
import { useProgress } from '@/composables/useProgress'
import { useAppStore } from '@/stores/app'

const store = useAppStore()
const { loading, error, post } = useApi()
const { start, complete } = useProgress()

const form = reactive({
  machine_type: 'фрезерный',
  profile_series: 'ALT F50',
  elements: '',
  output_format: 'G-code',
  notes: '',
})
const result = ref(null)

const machineTypes = ['фрезерный', 'отрезной', 'пробивной', 'обрабатывающий центр']
const outputFormats = ['G-code', 'DXF', 'Elumatec', 'Schirmer', 'PDAS']

async function submit() {
  result.value = null
  start([
    { label: 'Анализ элементов', at: 20 },
    { label: 'Генерация программы', at: 55 },
    { label: 'Оптимизация траекторий', at: 80 },
    { label: 'Финализация', at: 95 },
  ], 10000)
  try {
    result.value = await post('/api/generate-cnc', { ...form })
  } catch { /* handled */ } finally {
    complete()
  }
}
</script>

<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
    <header class="mb-10 animate-fade-up">
      <span class="text-xs font-mono tracking-[0.2em] uppercase text-sage mb-2 block">Производство</span>
      <h1 class="font-display text-3xl sm:text-4xl text-carbon-900 mb-3">Программы ЧПУ</h1>
      <p class="text-carbon-500 font-body">{{ store.cardDescriptions.cnc }}</p>
    </header>

    <section class="bg-white rounded-2xl border border-carbon-200/60 p-8 mb-8 animate-fade-up" style="animation-delay:80ms">
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5 mb-6">
        <div>
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">Тип станка</label>
          <select v-model="form.machine_type"
                  class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                         text-carbon-700 focus:outline-none focus:border-sage/50 focus:ring-1 focus:ring-sage/20">
            <option v-for="t in machineTypes" :key="t" :value="t">{{ t }}</option>
          </select>
        </div>
        <div>
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">Профильная серия</label>
          <input v-model="form.profile_series" type="text"
                 class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                        text-carbon-700 font-mono focus:outline-none focus:border-sage/50 focus:ring-1
                        focus:ring-sage/20 transition-colors" />
        </div>
        <div>
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">Формат вывода</label>
          <select v-model="form.output_format"
                  class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                         text-carbon-700 focus:outline-none focus:border-sage/50 focus:ring-1 focus:ring-sage/20">
            <option v-for="f in outputFormats" :key="f" :value="f">{{ f }}</option>
          </select>
        </div>
      </div>
      <div class="mb-6">
        <label class="block text-xs font-medium text-carbon-500 mb-1.5">Элементы (JSON или список)</label>
        <textarea v-model="form.elements" rows="4"
                  placeholder='[{"profile":"123456","length":1500,"qty":4,"operations":["фрезеровка","отверстие d10"]}]'
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
        <span v-else>Сгенерировать программу</span>
      </button>
    </section>

    <div v-if="error" class="bg-status-fail/10 border border-status-fail/20 rounded-xl p-4 mb-8 text-sm text-status-fail">
      {{ error }}
    </div>

    <section v-if="result" class="bg-white rounded-2xl border border-carbon-200/60 p-8 animate-scale-in">
      <h2 class="font-display text-xl text-carbon-800 mb-6">Программа ЧПУ</h2>

      <div v-if="result.program || result.code" class="bg-carbon-900 rounded-xl p-6 overflow-x-auto mb-6">
        <pre class="text-xs font-mono text-green-400 whitespace-pre-wrap">{{ result.program || result.code }}</pre>
      </div>

      <div v-if="result.summary" class="bg-canvas rounded-xl p-4 text-sm text-carbon-600">
        {{ result.summary }}
      </div>

      <pre v-if="!result.program && !result.code && !result.summary"
           class="bg-canvas rounded-xl p-6 text-xs font-mono text-carbon-600 overflow-x-auto whitespace-pre-wrap">{{ JSON.stringify(result, null, 2) }}</pre>
    </section>
  </div>
</template>
