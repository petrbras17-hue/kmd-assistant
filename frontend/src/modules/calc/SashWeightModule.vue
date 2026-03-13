<script setup>
import { reactive, ref } from 'vue'
import { useApi } from '@/composables/useApi'
import { useProgress } from '@/composables/useProgress'
import { useAppStore } from '@/stores/app'

const store = useAppStore()
const { loading, error, post } = useApi()
const { start, complete } = useProgress()

const form = reactive({
  width: 800,
  height: 1400,
  profile_weight: 1.2,
  glass_thickness: 40,
  glass_density: 2500,
  hardware_weight: 3.5,
  opening_type: 'поворотно-откидная',
})
const result = ref(null)

const openingTypes = ['поворотная', 'откидная', 'поворотно-откидная', 'раздвижная', 'параллельно-сдвижная']

async function submit() {
  result.value = null
  start([
    { label: 'Расчёт массы профиля', at: 30 },
    { label: 'Расчёт массы стеклопакета', at: 60 },
    { label: 'Суммарная масса', at: 90 },
  ], 4000)
  try {
    result.value = await post('/api/calc-sash-weight', { ...form })
  } catch { /* handled */ } finally {
    complete()
  }
}
</script>

<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
    <header class="mb-10 animate-fade-up">
      <span class="text-xs font-mono tracking-[0.2em] uppercase text-sage mb-2 block">Калькуляторы</span>
      <h1 class="font-display text-3xl sm:text-4xl text-carbon-900 mb-3">Вес створки</h1>
      <p class="text-carbon-500 font-body">{{ store.cardDescriptions.sashweight }}</p>
    </header>

    <section class="bg-white rounded-2xl border border-carbon-200/60 p-8 mb-8 animate-fade-up" style="animation-delay:80ms">
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5 mb-6">
        <div>
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">Тип открывания</label>
          <select v-model="form.opening_type"
                  class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                         text-carbon-700 focus:outline-none focus:border-sage/50 focus:ring-1
                         focus:ring-sage/20 transition-colors">
            <option v-for="t in openingTypes" :key="t" :value="t">{{ t }}</option>
          </select>
        </div>
        <div v-for="field in [
          { key: 'width', label: 'Ширина створки, мм' },
          { key: 'height', label: 'Высота створки, мм' },
          { key: 'profile_weight', label: 'Масса профиля, кг/м' },
          { key: 'glass_thickness', label: 'Толщина стеклопакета, мм' },
          { key: 'glass_density', label: 'Плотность стекла, кг/м3' },
          { key: 'hardware_weight', label: 'Масса фурнитуры, кг' },
        ]" :key="field.key">
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">{{ field.label }}</label>
          <input v-model.number="form[field.key]" type="number" step="0.1"
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
        <span v-else>Рассчитать массу</span>
      </button>
    </section>

    <div v-if="error" class="bg-status-fail/10 border border-status-fail/20 rounded-xl p-4 mb-8 text-sm text-status-fail">
      {{ error }}
    </div>

    <section v-if="result" class="bg-white rounded-2xl border border-carbon-200/60 p-8 animate-scale-in">
      <h2 class="font-display text-xl text-carbon-800 mb-6">Результат расчёта</h2>

      <div class="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
        <div v-if="result.profile_mass !== undefined" class="bg-canvas rounded-xl p-4 text-center">
          <p class="text-xl font-display text-carbon-700">{{ result.profile_mass }}</p>
          <p class="text-xs text-carbon-400 mt-1 font-mono">Профиль, кг</p>
        </div>
        <div v-if="result.glass_mass !== undefined" class="bg-canvas rounded-xl p-4 text-center">
          <p class="text-xl font-display text-carbon-700">{{ result.glass_mass }}</p>
          <p class="text-xs text-carbon-400 mt-1 font-mono">Стеклопакет, кг</p>
        </div>
        <div v-if="result.hardware_mass !== undefined" class="bg-canvas rounded-xl p-4 text-center">
          <p class="text-xl font-display text-carbon-700">{{ result.hardware_mass }}</p>
          <p class="text-xs text-carbon-400 mt-1 font-mono">Фурнитура, кг</p>
        </div>
        <div v-if="result.total_mass !== undefined" class="bg-sage-pale rounded-xl p-4 text-center">
          <p class="text-2xl font-display text-sage">{{ result.total_mass }}</p>
          <p class="text-xs text-sage-dark mt-1 font-mono">Итого, кг</p>
        </div>
      </div>

      <div v-if="result.max_allowed !== undefined"
           class="bg-canvas rounded-xl p-4 flex items-center gap-3">
        <span class="w-2.5 h-2.5 rounded-full"
              :class="(result.total_mass || 0) <= result.max_allowed ? 'bg-status-ok' : 'bg-status-fail'" />
        <span class="text-sm text-carbon-600">
          Допустимая масса: {{ result.max_allowed }} кг.
          {{ (result.total_mass || 0) <= result.max_allowed ? 'Масса в пределах нормы.' : 'Превышение допустимой массы!' }}
        </span>
      </div>

      <pre v-if="result.total_mass === undefined"
           class="bg-canvas rounded-xl p-6 text-xs font-mono text-carbon-600 overflow-x-auto whitespace-pre-wrap">{{ JSON.stringify(result, null, 2) }}</pre>
    </section>
  </div>
</template>
