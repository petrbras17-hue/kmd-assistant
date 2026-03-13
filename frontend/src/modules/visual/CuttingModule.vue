<script setup>
import { reactive, ref } from 'vue'
import { useApi } from '@/composables/useApi'
import { useProgress } from '@/composables/useProgress'
import { useAppStore } from '@/stores/app'

const store = useAppStore()
const { loading, error, post } = useApi()
const { start, complete } = useProgress()

const form = reactive({
  stock_length: 6500,
  parts: '',
  kerf: 5,
  algorithm: 'FFD',
})
const result = ref(null)

const algorithms = ['FFD', 'BFD', 'WFD']

async function submit() {
  result.value = null
  start([
    { label: 'Парсинг заготовок', at: 20 },
    { label: 'Оптимизация раскроя', at: 60 },
    { label: 'Генерация карт', at: 90 },
  ], 8000)
  try {
    result.value = await post('/api/optimize-cutting', { ...form })
  } catch { /* handled */ } finally {
    complete()
  }
}
</script>

<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
    <header class="mb-10 animate-fade-up">
      <span class="text-xs font-mono tracking-[0.2em] uppercase text-sage mb-2 block">3D и оптимизация</span>
      <h1 class="font-display text-3xl sm:text-4xl text-carbon-900 mb-3">Раскрой профиля</h1>
      <p class="text-carbon-500 font-body">{{ store.cardDescriptions.cutting }}</p>
    </header>

    <section class="bg-white rounded-2xl border border-carbon-200/60 p-8 mb-8 animate-fade-up" style="animation-delay:80ms">
      <div class="grid grid-cols-1 sm:grid-cols-3 gap-5 mb-6">
        <div>
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">Длина хлыста, мм</label>
          <input v-model.number="form.stock_length" type="number"
                 class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                        text-carbon-700 font-mono focus:outline-none focus:border-sage/50 focus:ring-1
                        focus:ring-sage/20 transition-colors" />
        </div>
        <div>
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">Припуск реза, мм</label>
          <input v-model.number="form.kerf" type="number"
                 class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                        text-carbon-700 font-mono focus:outline-none focus:border-sage/50 focus:ring-1
                        focus:ring-sage/20 transition-colors" />
        </div>
        <div>
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">Алгоритм</label>
          <select v-model="form.algorithm"
                  class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                         text-carbon-700 focus:outline-none focus:border-sage/50 focus:ring-1 focus:ring-sage/20">
            <option v-for="a in algorithms" :key="a" :value="a">{{ a }}</option>
          </select>
        </div>
      </div>
      <div class="mb-6">
        <label class="block text-xs font-medium text-carbon-500 mb-1.5">Детали (длина x кол-во, по строкам)</label>
        <textarea v-model="form.parts" rows="5"
                  placeholder="1500 x 4&#10;1200 x 8&#10;900 x 12&#10;600 x 6"
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
          Оптимизация...
        </span>
        <span v-else>Оптимизировать</span>
      </button>
    </section>

    <div v-if="error" class="bg-status-fail/10 border border-status-fail/20 rounded-xl p-4 mb-8 text-sm text-status-fail">
      {{ error }}
    </div>

    <section v-if="result" class="bg-white rounded-2xl border border-carbon-200/60 p-8 animate-scale-in">
      <h2 class="font-display text-xl text-carbon-800 mb-6">Карты раскроя</h2>

      <!-- Stats -->
      <div v-if="result.stocks_used !== undefined" class="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-8">
        <div class="bg-canvas rounded-xl p-4 text-center">
          <p class="text-2xl font-display text-carbon-800">{{ result.stocks_used }}</p>
          <p class="text-xs text-carbon-400 mt-1 font-mono">Хлыстов</p>
        </div>
        <div class="bg-canvas rounded-xl p-4 text-center">
          <p class="text-2xl font-display text-status-ok">{{ result.efficiency || '-' }}%</p>
          <p class="text-xs text-carbon-400 mt-1 font-mono">Эффективность</p>
        </div>
        <div class="bg-canvas rounded-xl p-4 text-center">
          <p class="text-2xl font-display text-carbon-700">{{ result.total_waste || '-' }}</p>
          <p class="text-xs text-carbon-400 mt-1 font-mono">Отходы, мм</p>
        </div>
        <div class="bg-canvas rounded-xl p-4 text-center">
          <p class="text-2xl font-display text-carbon-700">{{ result.total_parts || '-' }}</p>
          <p class="text-xs text-carbon-400 mt-1 font-mono">Деталей</p>
        </div>
      </div>

      <!-- Cutting maps visualization -->
      <div v-if="result.cuts?.length" class="space-y-4">
        <div v-for="(cut, i) in result.cuts" :key="i" class="bg-canvas rounded-xl p-4">
          <div class="flex items-center gap-2 mb-2">
            <span class="text-xs font-mono text-carbon-400">Хлыст {{ i + 1 }}</span>
            <span v-if="cut.waste" class="text-xs font-mono text-status-warn">отход: {{ cut.waste }} мм</span>
          </div>
          <div class="flex h-8 rounded overflow-hidden border border-carbon-200/40">
            <div v-for="(part, j) in (cut.parts || cut.pieces || [])" :key="j"
                 class="h-full flex items-center justify-center text-[10px] font-mono text-white bg-sage"
                 :style="{ width: `${(part.length || part) / form.stock_length * 100}%`, opacity: 0.6 + (j % 3) * 0.13 }"
                 :title="`${part.length || part} мм`">
              {{ part.length || part }}
            </div>
            <div class="h-full flex-1 bg-carbon-100" />
          </div>
        </div>
      </div>

      <pre v-if="!result.cuts && result.stocks_used === undefined"
           class="bg-canvas rounded-xl p-6 text-xs font-mono text-carbon-600 overflow-x-auto whitespace-pre-wrap">{{ JSON.stringify(result, null, 2) }}</pre>
    </section>
  </div>
</template>
