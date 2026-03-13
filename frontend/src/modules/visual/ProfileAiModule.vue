<script setup>
import { reactive, ref } from 'vue'
import { useApi } from '@/composables/useApi'
import { useProgress } from '@/composables/useProgress'
import { useAppStore } from '@/stores/app'

const store = useAppStore()
const { loading, error, post } = useApi()
const { start, complete } = useProgress()

const form = reactive({
  application: 'фасад',
  thermal_class: 'тёплый',
  max_height: 4000,
  max_width: 1500,
  wind_load: 600,
  fire_resistance: false,
  budget: 'средний',
  preferred_brands: '',
})
const result = ref(null)

const applications = ['фасад', 'окно', 'дверь', 'входная группа', 'зенитный фонарь', 'перегородка']
const thermalClasses = ['холодный', 'тёплый', 'высокоизолирующий']
const budgetLevels = ['эконом', 'средний', 'премиум']

async function submit() {
  result.value = null
  start([
    { label: 'Анализ требований', at: 20 },
    { label: 'Поиск по каталогам', at: 50 },
    { label: 'Ранжирование вариантов', at: 80 },
    { label: 'Формирование рекомендаций', at: 95 },
  ], 12000)
  try {
    result.value = await post('/api/recommend-profile', { ...form })
  } catch { /* handled */ } finally {
    complete()
  }
}
</script>

<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
    <header class="mb-10 animate-fade-up">
      <span class="text-xs font-mono tracking-[0.2em] uppercase text-sage mb-2 block">3D и оптимизация</span>
      <h1 class="font-display text-3xl sm:text-4xl text-carbon-900 mb-3">Подбор системы</h1>
      <p class="text-carbon-500 font-body">{{ store.cardDescriptions.profileai }}</p>
    </header>

    <section class="bg-white rounded-2xl border border-carbon-200/60 p-8 mb-8 animate-fade-up" style="animation-delay:80ms">
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5 mb-6">
        <div>
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">Назначение</label>
          <select v-model="form.application"
                  class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                         text-carbon-700 focus:outline-none focus:border-sage/50 focus:ring-1 focus:ring-sage/20">
            <option v-for="a in applications" :key="a" :value="a">{{ a }}</option>
          </select>
        </div>
        <div>
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">Термоизоляция</label>
          <select v-model="form.thermal_class"
                  class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                         text-carbon-700 focus:outline-none focus:border-sage/50 focus:ring-1 focus:ring-sage/20">
            <option v-for="t in thermalClasses" :key="t" :value="t">{{ t }}</option>
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
          { key: 'max_height', label: 'Макс. высота, мм' },
          { key: 'max_width', label: 'Макс. ширина, мм' },
          { key: 'wind_load', label: 'Ветровая нагрузка, Па' },
        ]" :key="field.key">
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">{{ field.label }}</label>
          <input v-model.number="form[field.key]" type="number"
                 class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                        text-carbon-700 font-mono focus:outline-none focus:border-sage/50 focus:ring-1
                        focus:ring-sage/20 transition-colors" />
        </div>
        <div class="flex items-end">
          <label class="flex items-center gap-2 cursor-pointer">
            <input v-model="form.fire_resistance" type="checkbox"
                   class="w-4 h-4 rounded border-carbon-300 text-sage focus:ring-sage/30" />
            <span class="text-xs text-carbon-600">Огнестойкость</span>
          </label>
        </div>
        <div>
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">Предпочтительные бренды</label>
          <input v-model="form.preferred_brands" type="text" placeholder="ALUTECH, Schuco, Reynaers"
                 class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                        text-carbon-700 focus:outline-none focus:border-sage/50 focus:ring-1
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
        <span v-else>Подобрать систему</span>
      </button>
    </section>

    <div v-if="error" class="bg-status-fail/10 border border-status-fail/20 rounded-xl p-4 mb-8 text-sm text-status-fail">
      {{ error }}
    </div>

    <section v-if="result" class="bg-white rounded-2xl border border-carbon-200/60 p-8 animate-scale-in">
      <h2 class="font-display text-xl text-carbon-800 mb-6">Рекомендуемые системы</h2>

      <div v-if="result.recommendations?.length || result.systems?.length" class="space-y-4">
        <div v-for="(sys, i) in (result.recommendations || result.systems)" :key="i"
             class="bg-canvas rounded-xl p-5">
          <div class="flex items-start justify-between mb-3">
            <div>
              <h3 class="text-sm font-medium text-carbon-700">{{ sys.name || sys.series }}</h3>
              <span v-if="sys.brand" class="text-xs text-sage font-mono">{{ sys.brand }}</span>
            </div>
            <span v-if="sys.score" class="text-sm font-display text-sage bg-sage-pale px-3 py-1 rounded-lg">
              {{ sys.score }}/10
            </span>
          </div>
          <p v-if="sys.description" class="text-xs text-carbon-400 mb-3">{{ sys.description }}</p>
          <div class="flex flex-wrap gap-3 text-xs">
            <span v-if="sys.uf" class="text-carbon-400">Uf: <span class="font-mono text-carbon-600">{{ sys.uf }}</span></span>
            <span v-if="sys.depth" class="text-carbon-400">Глубина: <span class="font-mono text-carbon-600">{{ sys.depth }} мм</span></span>
            <span v-if="sys.max_glass" class="text-carbon-400">Макс. стекло: <span class="font-mono text-carbon-600">{{ sys.max_glass }} мм</span></span>
            <span v-if="sys.price_level" class="text-carbon-400">Цена: <span class="font-mono text-carbon-600">{{ sys.price_level }}</span></span>
          </div>
        </div>
      </div>

      <div v-if="result.summary" class="mt-6 bg-canvas rounded-xl p-4 text-sm text-carbon-600">
        {{ result.summary }}
      </div>

      <pre v-if="!result.recommendations && !result.systems && !result.summary"
           class="bg-canvas rounded-xl p-6 text-xs font-mono text-carbon-600 overflow-x-auto whitespace-pre-wrap">{{ JSON.stringify(result, null, 2) }}</pre>
    </section>
  </div>
</template>
