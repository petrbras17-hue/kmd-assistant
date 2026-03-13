<script setup>
import { reactive, ref } from 'vue'
import { useApi } from '@/composables/useApi'
import { useProgress } from '@/composables/useProgress'
import { useAppStore } from '@/stores/app'

const store = useAppStore()
const { loading, error, post } = useApi()
const { start, complete } = useProgress()

const form = reactive({
  base_material: 'бетон B25',
  load_type: 'растяжение',
  load_value: 5.0,
  panel_weight: 120,
  anchor_count: 4,
  embedment_depth: 80,
  edge_distance: 100,
})
const result = ref(null)

const baseMaterials = ['бетон B15', 'бетон B25', 'бетон B30', 'кирпич полнотелый', 'кирпич пустотелый', 'газобетон D500', 'газобетон D600', 'сталь']
const loadTypes = ['растяжение', 'срез', 'комбинированная']

async function submit() {
  result.value = null
  start([
    { label: 'Анализ основания', at: 25 },
    { label: 'Подбор крепежа', at: 55 },
    { label: 'Проверка несущей способности', at: 85 },
  ], 5000)
  try {
    result.value = await post('/api/calc-fasteners', { ...form })
  } catch { /* handled */ } finally {
    complete()
  }
}
</script>

<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
    <header class="mb-10 animate-fade-up">
      <span class="text-xs font-mono tracking-[0.2em] uppercase text-sage mb-2 block">Калькуляторы</span>
      <h1 class="font-display text-3xl sm:text-4xl text-carbon-900 mb-3">Крепёж</h1>
      <p class="text-carbon-500 font-body">{{ store.cardDescriptions.fasteners }}</p>
    </header>

    <section class="bg-white rounded-2xl border border-carbon-200/60 p-8 mb-8 animate-fade-up" style="animation-delay:80ms">
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5 mb-6">
        <div>
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">Материал основания</label>
          <select v-model="form.base_material"
                  class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                         text-carbon-700 focus:outline-none focus:border-sage/50 focus:ring-1
                         focus:ring-sage/20 transition-colors">
            <option v-for="m in baseMaterials" :key="m" :value="m">{{ m }}</option>
          </select>
        </div>
        <div>
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">Тип нагрузки</label>
          <select v-model="form.load_type"
                  class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                         text-carbon-700 focus:outline-none focus:border-sage/50 focus:ring-1
                         focus:ring-sage/20 transition-colors">
            <option v-for="l in loadTypes" :key="l" :value="l">{{ l }}</option>
          </select>
        </div>
        <div v-for="field in [
          { key: 'load_value', label: 'Нагрузка, кН' },
          { key: 'panel_weight', label: 'Масса панели, кг' },
          { key: 'anchor_count', label: 'Количество точек' },
          { key: 'embedment_depth', label: 'Глубина заделки, мм' },
          { key: 'edge_distance', label: 'Расстояние до края, мм' },
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
          Подбор...
        </span>
        <span v-else>Подобрать крепёж</span>
      </button>
    </section>

    <div v-if="error" class="bg-status-fail/10 border border-status-fail/20 rounded-xl p-4 mb-8 text-sm text-status-fail">
      {{ error }}
    </div>

    <section v-if="result" class="bg-white rounded-2xl border border-carbon-200/60 p-8 animate-scale-in">
      <h2 class="font-display text-xl text-carbon-800 mb-6">Рекомендуемый крепёж</h2>

      <div v-if="result.recommended?.length" class="space-y-4 mb-6">
        <div v-for="(item, i) in result.recommended" :key="i" class="bg-canvas rounded-xl p-5">
          <h3 class="text-sm font-medium text-carbon-700 mb-2">{{ item.name || item.type }}</h3>
          <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 text-xs">
            <div v-if="item.diameter"><span class="text-carbon-400">Диаметр:</span> <span class="font-mono text-carbon-600">{{ item.diameter }}</span></div>
            <div v-if="item.length"><span class="text-carbon-400">Длина:</span> <span class="font-mono text-carbon-600">{{ item.length }}</span></div>
            <div v-if="item.capacity"><span class="text-carbon-400">Несущая:</span> <span class="font-mono text-carbon-600">{{ item.capacity }} кН</span></div>
            <div v-if="item.safety_factor"><span class="text-carbon-400">Запас:</span> <span class="font-mono text-carbon-600">{{ item.safety_factor }}</span></div>
          </div>
        </div>
      </div>

      <div v-if="result.verdict" class="bg-canvas rounded-xl p-4 text-sm text-carbon-600">
        {{ result.verdict }}
      </div>

      <pre v-if="!result.recommended && !result.verdict"
           class="bg-canvas rounded-xl p-6 text-xs font-mono text-carbon-600 overflow-x-auto whitespace-pre-wrap">{{ JSON.stringify(result, null, 2) }}</pre>
    </section>
  </div>
</template>
