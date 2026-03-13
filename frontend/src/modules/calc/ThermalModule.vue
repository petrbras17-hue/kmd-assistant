<script setup>
import { reactive, ref } from 'vue'
import { useApi } from '@/composables/useApi'
import { useProgress } from '@/composables/useProgress'
import { useAppStore } from '@/stores/app'

const store = useAppStore()
const { loading, error, post } = useApi()
const { start, complete } = useProgress()

const form = reactive({
  frame_width: 60,
  frame_height: 1400,
  sash_width: 60,
  sash_height: 1200,
  glass_formula: '4-16-4',
  uf: 1.8,
  ug: 1.1,
  psi: 0.06,
  lg: 4.8,
})
const result = ref(null)

async function submit() {
  result.value = null
  start([
    { label: 'Расчёт теплопередачи рамы', at: 30 },
    { label: 'Расчёт стеклопакета', at: 60 },
    { label: 'Определение Uw', at: 90 },
  ], 5000)
  try {
    result.value = await post('/api/calc-thermal', { ...form })
  } catch { /* handled */ } finally {
    complete()
  }
}
</script>

<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
    <header class="mb-10 animate-fade-up">
      <span class="text-xs font-mono tracking-[0.2em] uppercase text-sage mb-2 block">Калькуляторы</span>
      <h1 class="font-display text-3xl sm:text-4xl text-carbon-900 mb-3">Теплотехника</h1>
      <p class="text-carbon-500 font-body">{{ store.cardDescriptions.thermal }}</p>
    </header>

    <section class="bg-white rounded-2xl border border-carbon-200/60 p-8 mb-8 animate-fade-up" style="animation-delay:80ms">
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5 mb-6">
        <div v-for="field in [
          { key: 'frame_width', label: 'Ширина рамы, мм', step: 1 },
          { key: 'frame_height', label: 'Высота рамы, мм', step: 1 },
          { key: 'sash_width', label: 'Ширина створки, мм', step: 1 },
          { key: 'sash_height', label: 'Высота створки, мм', step: 1 },
          { key: 'uf', label: 'Uf рамы, Вт/(м2*К)', step: 0.1 },
          { key: 'ug', label: 'Ug стекла, Вт/(м2*К)', step: 0.1 },
          { key: 'psi', label: 'Psi дист. рамки', step: 0.01 },
          { key: 'lg', label: 'Lg периметр стекла, м', step: 0.1 },
        ]" :key="field.key">
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">{{ field.label }}</label>
          <input v-model.number="form[field.key]" type="number" :step="field.step"
                 class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                        text-carbon-700 font-mono focus:outline-none focus:border-sage/50 focus:ring-1
                        focus:ring-sage/20 transition-colors" />
        </div>
        <div>
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">Формула стеклопакета</label>
          <input v-model="form.glass_formula" type="text"
                 class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                        text-carbon-700 font-mono focus:outline-none focus:border-sage/50 focus:ring-1
                        focus:ring-sage/20 transition-colors" />
        </div>
      </div>

      <button @click="submit" :disabled="loading"
              class="px-6 py-3 bg-sage text-white text-sm font-medium rounded-xl
                     hover:bg-sage-dark disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
        <span v-if="loading" class="flex items-center gap-2">
          <svg class="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
          </svg>
          Расчёт...
        </span>
        <span v-else>Рассчитать Uw</span>
      </button>
    </section>

    <div v-if="error" class="bg-status-fail/10 border border-status-fail/20 rounded-xl p-4 mb-8 text-sm text-status-fail">
      {{ error }}
    </div>

    <section v-if="result" class="bg-white rounded-2xl border border-carbon-200/60 p-8 animate-scale-in">
      <h2 class="font-display text-xl text-carbon-800 mb-6">Результат расчёта</h2>

      <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <div v-if="result.uw !== undefined" class="bg-canvas rounded-xl p-5 text-center">
          <p class="text-3xl font-display text-sage">{{ result.uw }}</p>
          <p class="text-xs text-carbon-400 mt-1 font-mono">Uw, Вт/(м2*К)</p>
        </div>
        <div v-if="result.af !== undefined" class="bg-canvas rounded-xl p-5 text-center">
          <p class="text-2xl font-display text-carbon-700">{{ result.af }}</p>
          <p class="text-xs text-carbon-400 mt-1 font-mono">Af рамы, м2</p>
        </div>
        <div v-if="result.ag !== undefined" class="bg-canvas rounded-xl p-5 text-center">
          <p class="text-2xl font-display text-carbon-700">{{ result.ag }}</p>
          <p class="text-xs text-carbon-400 mt-1 font-mono">Ag стекла, м2</p>
        </div>
      </div>

      <div v-if="result.verdict" class="bg-canvas rounded-xl p-4 text-sm text-carbon-600">
        {{ result.verdict }}
      </div>

      <pre v-if="result.uw === undefined"
           class="bg-canvas rounded-xl p-6 text-xs font-mono text-carbon-600 overflow-x-auto whitespace-pre-wrap">{{ JSON.stringify(result, null, 2) }}</pre>
    </section>
  </div>
</template>
