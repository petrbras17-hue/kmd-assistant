<script setup>
import { reactive, ref } from 'vue'
import { useApi } from '@/composables/useApi'
import { useProgress } from '@/composables/useProgress'
import { useAppStore } from '@/stores/app'

const store = useAppStore()
const { loading, error, post } = useApi()
const { start, complete } = useProgress()

const form = reactive({
  wind_region: 'III',
  terrain_type: 'B',
  height: 30,
  panel_width: 1500,
  panel_height: 3000,
  building_width: 40,
  building_height: 60,
})
const result = ref(null)

const windRegions = ['Ia', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII']
const terrainTypes = ['A', 'B', 'C']

async function submit() {
  result.value = null
  start([
    { label: 'Определение w0', at: 25 },
    { label: 'Расчёт коэффициентов', at: 55 },
    { label: 'Ветровая нагрузка', at: 85 },
  ], 4000)
  try {
    result.value = await post('/api/calc-wind', { ...form })
  } catch { /* handled */ } finally {
    complete()
  }
}
</script>

<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
    <header class="mb-10 animate-fade-up">
      <span class="text-xs font-mono tracking-[0.2em] uppercase text-sage mb-2 block">Калькуляторы</span>
      <h1 class="font-display text-3xl sm:text-4xl text-carbon-900 mb-3">Ветровая нагрузка</h1>
      <p class="text-carbon-500 font-body">{{ store.cardDescriptions.wind }}</p>
    </header>

    <section class="bg-white rounded-2xl border border-carbon-200/60 p-8 mb-8 animate-fade-up" style="animation-delay:80ms">
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5 mb-6">
        <div>
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">Ветровой район</label>
          <select v-model="form.wind_region"
                  class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                         text-carbon-700 font-mono focus:outline-none focus:border-sage/50 focus:ring-1
                         focus:ring-sage/20 transition-colors">
            <option v-for="r in windRegions" :key="r" :value="r">{{ r }}</option>
          </select>
        </div>
        <div>
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">Тип местности</label>
          <select v-model="form.terrain_type"
                  class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                         text-carbon-700 font-mono focus:outline-none focus:border-sage/50 focus:ring-1
                         focus:ring-sage/20 transition-colors">
            <option v-for="t in terrainTypes" :key="t" :value="t">{{ t }}</option>
          </select>
        </div>
        <div v-for="field in [
          { key: 'height', label: 'Высота установки, м' },
          { key: 'panel_width', label: 'Ширина панели, мм' },
          { key: 'panel_height', label: 'Высота панели, мм' },
          { key: 'building_width', label: 'Ширина здания, м' },
          { key: 'building_height', label: 'Высота здания, м' },
        ]" :key="field.key">
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">{{ field.label }}</label>
          <input v-model.number="form[field.key]" type="number"
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
        <span v-else>Рассчитать</span>
      </button>
    </section>

    <div v-if="error" class="bg-status-fail/10 border border-status-fail/20 rounded-xl p-4 mb-8 text-sm text-status-fail">
      {{ error }}
    </div>

    <section v-if="result" class="bg-white rounded-2xl border border-carbon-200/60 p-8 animate-scale-in">
      <h2 class="font-display text-xl text-carbon-800 mb-6">Результат расчёта</h2>

      <div class="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
        <div v-for="(val, key) in { w0: result.w0, k_z: result.k_z, w_norm: result.w_norm, w_calc: result.w_calc }" :key="key"
             v-show="val !== undefined"
             class="bg-canvas rounded-xl p-4 text-center">
          <p class="text-xl font-display text-carbon-800">{{ val }}</p>
          <p class="text-xs text-carbon-400 mt-1 font-mono">{{ key }}</p>
        </div>
      </div>

      <div v-if="result.pressure !== undefined" class="bg-sage-pale rounded-xl p-5 flex items-center gap-4">
        <span class="text-3xl font-display text-sage">{{ result.pressure }}</span>
        <span class="text-sm text-carbon-600">Па — расчётная ветровая нагрузка</span>
      </div>

      <div v-if="result.verdict" class="mt-4 bg-canvas rounded-xl p-4 text-sm text-carbon-600">
        {{ result.verdict }}
      </div>

      <pre v-if="result.w0 === undefined && result.pressure === undefined"
           class="bg-canvas rounded-xl p-6 text-xs font-mono text-carbon-600 overflow-x-auto whitespace-pre-wrap">{{ JSON.stringify(result, null, 2) }}</pre>
    </section>
  </div>
</template>
