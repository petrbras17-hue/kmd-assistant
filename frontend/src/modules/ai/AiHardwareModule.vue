<script setup>
import { reactive, ref } from 'vue'
import { useApi } from '@/composables/useApi'
import { useProgress } from '@/composables/useProgress'
import { useAppStore } from '@/stores/app'

const store = useAppStore()
const { loading, error, post } = useApi()
const { start, complete } = useProgress()

const form = reactive({
  system_type: 'фасадная',
  opening_type: 'поворотно-откидная',
  width: 1000,
  height: 1500,
  weight: 60,
  wind_load: 800,
  fire_resistance: false,
  smoke_protection: false,
  budget: 'средний',
})
const result = ref(null)

const systemTypes = ['фасадная', 'оконная', 'дверная', 'раздвижная', 'зенитный фонарь']
const openingTypes = ['глухая', 'поворотная', 'откидная', 'поворотно-откидная', 'раздвижная', 'параллельно-сдвижная', 'складная']
const budgetLevels = ['эконом', 'средний', 'премиум']

async function submit() {
  result.value = null
  start([
    { label: 'Анализ требований', at: 20 },
    { label: 'Подбор фурнитуры', at: 50 },
    { label: 'Проверка совместимости', at: 75 },
    { label: 'Формирование рекомендаций', at: 95 },
  ], 15000)
  try {
    result.value = await post('/api/ai-hardware', { ...form })
  } catch { /* handled */ } finally {
    complete()
  }
}
</script>

<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
    <header class="mb-10 animate-fade-up">
      <span class="text-xs font-mono tracking-[0.2em] uppercase text-sage mb-2 block">
        <span class="inline-block w-1.5 h-1.5 rounded-full bg-sage mr-1.5 animate-pulse-glow" />
        AI инструменты
      </span>
      <h1 class="font-display text-3xl sm:text-4xl text-carbon-900 mb-3">Подбор фурнитуры</h1>
      <p class="text-carbon-500 font-body">{{ store.cardDescriptions.aihardware }}</p>
    </header>

    <section class="bg-white rounded-2xl border border-carbon-200/60 p-8 mb-8 animate-fade-up" style="animation-delay:80ms">
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5 mb-6">
        <div>
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">Тип системы</label>
          <select v-model="form.system_type"
                  class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                         text-carbon-700 focus:outline-none focus:border-sage/50 focus:ring-1 focus:ring-sage/20">
            <option v-for="t in systemTypes" :key="t" :value="t">{{ t }}</option>
          </select>
        </div>
        <div>
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">Тип открывания</label>
          <select v-model="form.opening_type"
                  class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                         text-carbon-700 focus:outline-none focus:border-sage/50 focus:ring-1 focus:ring-sage/20">
            <option v-for="t in openingTypes" :key="t" :value="t">{{ t }}</option>
          </select>
        </div>
        <div>
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">Бюджет</label>
          <select v-model="form.budget"
                  class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                         text-carbon-700 focus:outline-none focus:border-sage/50 focus:ring-1 focus:ring-sage/20">
            <option v-for="b in budgetLevels" :key="b" :value="b">{{ b }}</option>
          </select>
        </div>
        <div v-for="field in [
          { key: 'width', label: 'Ширина, мм' },
          { key: 'height', label: 'Высота, мм' },
          { key: 'weight', label: 'Масса створки, кг' },
          { key: 'wind_load', label: 'Ветровая нагрузка, Па' },
        ]" :key="field.key">
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">{{ field.label }}</label>
          <input v-model.number="form[field.key]" type="number"
                 class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                        text-carbon-700 font-mono focus:outline-none focus:border-sage/50 focus:ring-1
                        focus:ring-sage/20 transition-colors" />
        </div>
        <div class="flex flex-col gap-3 justify-end">
          <label class="flex items-center gap-2 cursor-pointer">
            <input v-model="form.fire_resistance" type="checkbox"
                   class="w-4 h-4 rounded border-carbon-300 text-sage focus:ring-sage/30" />
            <span class="text-xs text-carbon-600">Огнестойкость</span>
          </label>
          <label class="flex items-center gap-2 cursor-pointer">
            <input v-model="form.smoke_protection" type="checkbox"
                   class="w-4 h-4 rounded border-carbon-300 text-sage focus:ring-sage/30" />
            <span class="text-xs text-carbon-600">Дымозащита</span>
          </label>
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
        <span v-else>Подобрать фурнитуру</span>
      </button>
    </section>

    <div v-if="error" class="bg-status-fail/10 border border-status-fail/20 rounded-xl p-4 mb-8 text-sm text-status-fail">
      {{ error }}
    </div>

    <section v-if="result" class="bg-white rounded-2xl border border-carbon-200/60 p-8 animate-scale-in">
      <h2 class="font-display text-xl text-carbon-800 mb-6">Рекомендации</h2>

      <div v-if="result.recommendations?.length || result.items?.length" class="space-y-4 mb-6">
        <div v-for="(item, i) in (result.recommendations || result.items)" :key="i"
             class="bg-canvas rounded-xl p-5">
          <div class="flex items-start justify-between mb-2">
            <h3 class="text-sm font-medium text-carbon-700">{{ item.name || item.product }}</h3>
            <span v-if="item.brand" class="text-xs font-mono text-sage bg-sage-pale px-2 py-0.5 rounded">{{ item.brand }}</span>
          </div>
          <p v-if="item.description" class="text-xs text-carbon-400 mb-2">{{ item.description }}</p>
          <div class="flex flex-wrap gap-3 text-xs">
            <span v-if="item.article" class="text-carbon-400">Арт: <span class="font-mono text-carbon-600">{{ item.article }}</span></span>
            <span v-if="item.price" class="text-carbon-400">Цена: <span class="font-mono text-carbon-600">{{ item.price }}</span></span>
            <span v-if="item.max_weight" class="text-carbon-400">До: <span class="font-mono text-carbon-600">{{ item.max_weight }} кг</span></span>
          </div>
        </div>
      </div>

      <div v-if="result.summary" class="bg-canvas rounded-xl p-4 text-sm text-carbon-600">
        {{ result.summary }}
      </div>

      <pre v-if="!result.recommendations && !result.items && !result.summary"
           class="bg-canvas rounded-xl p-6 text-xs font-mono text-carbon-600 overflow-x-auto whitespace-pre-wrap">{{ JSON.stringify(result, null, 2) }}</pre>
    </section>
  </div>
</template>
