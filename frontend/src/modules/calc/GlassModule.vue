<script setup>
import { reactive, ref } from 'vue'
import { useApi } from '@/composables/useApi'
import { useProgress } from '@/composables/useProgress'
import { useAppStore } from '@/stores/app'

const store = useAppStore()
const { loading, error, post } = useApi()
const { start, complete } = useProgress()

const form = reactive({
  glass_layers: [4, 4],
  gaps: [16],
  gas_fill: 'воздух',
  coating: 'без покрытия',
  warm_edge: false,
  width: 1200,
  height: 1400,
})
const result = ref(null)

const gasFills = ['воздух', 'аргон', 'криптон', 'ксенон']
const coatings = ['без покрытия', 'И-стекло', 'К-стекло', 'мультифункциональное', 'солнцезащитное']

function addLayer() {
  form.glass_layers.push(4)
  form.gaps.push(16)
}
function removeLayer() {
  if (form.glass_layers.length > 2) {
    form.glass_layers.pop()
    form.gaps.pop()
  }
}

async function submit() {
  result.value = null
  start([
    { label: 'Расчёт формулы', at: 30 },
    { label: 'Определение характеристик', at: 65 },
    { label: 'Результат', at: 95 },
  ], 4000)
  try {
    result.value = await post('/api/calc-glass', { ...form })
  } catch { /* handled */ } finally {
    complete()
  }
}
</script>

<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
    <header class="mb-10 animate-fade-up">
      <span class="text-xs font-mono tracking-[0.2em] uppercase text-sage mb-2 block">Калькуляторы</span>
      <h1 class="font-display text-3xl sm:text-4xl text-carbon-900 mb-3">Стеклопакет</h1>
      <p class="text-carbon-500 font-body">{{ store.cardDescriptions.glass }}</p>
    </header>

    <section class="bg-white rounded-2xl border border-carbon-200/60 p-8 mb-8 animate-fade-up" style="animation-delay:80ms">
      <!-- Glass formula builder -->
      <div class="mb-6">
        <label class="block text-xs font-medium text-carbon-500 mb-3">Формула стеклопакета</label>
        <div class="flex flex-wrap items-center gap-2">
          <template v-for="(glass, i) in form.glass_layers" :key="'g'+i">
            <input v-model.number="form.glass_layers[i]" type="number" min="3" max="12" step="1"
                   class="w-16 px-2 py-2 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                          text-center font-mono text-carbon-700 focus:outline-none focus:border-sage/50" />
            <template v-if="i < form.gaps.length">
              <span class="text-carbon-300">-</span>
              <input v-model.number="form.gaps[i]" type="number" min="6" max="24" step="2"
                     class="w-16 px-2 py-2 bg-sage-pale border border-sage/20 rounded-lg text-sm
                            text-center font-mono text-sage-dark focus:outline-none focus:border-sage/50" />
              <span class="text-carbon-300">-</span>
            </template>
          </template>
        </div>
        <div class="flex gap-2 mt-3">
          <button @click="addLayer"
                  class="text-xs text-sage hover:text-sage-dark transition-colors font-medium">+ стекло</button>
          <button v-if="form.glass_layers.length > 2" @click="removeLayer"
                  class="text-xs text-status-fail hover:text-status-fail/80 transition-colors font-medium">- стекло</button>
        </div>
      </div>

      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5 mb-6">
        <div>
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">Газовое заполнение</label>
          <select v-model="form.gas_fill"
                  class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                         text-carbon-700 focus:outline-none focus:border-sage/50 focus:ring-1
                         focus:ring-sage/20 transition-colors">
            <option v-for="g in gasFills" :key="g" :value="g">{{ g }}</option>
          </select>
        </div>
        <div>
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">Покрытие</label>
          <select v-model="form.coating"
                  class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                         text-carbon-700 focus:outline-none focus:border-sage/50 focus:ring-1
                         focus:ring-sage/20 transition-colors">
            <option v-for="c in coatings" :key="c" :value="c">{{ c }}</option>
          </select>
        </div>
        <div class="flex items-end gap-3">
          <label class="flex items-center gap-2 cursor-pointer">
            <input v-model="form.warm_edge" type="checkbox"
                   class="w-4 h-4 rounded border-carbon-300 text-sage focus:ring-sage/30" />
            <span class="text-xs text-carbon-600">Тёплая дист. рамка</span>
          </label>
        </div>
        <div>
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">Ширина, мм</label>
          <input v-model.number="form.width" type="number"
                 class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                        text-carbon-700 font-mono focus:outline-none focus:border-sage/50 focus:ring-1
                        focus:ring-sage/20 transition-colors" />
        </div>
        <div>
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">Высота, мм</label>
          <input v-model.number="form.height" type="number"
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
      <h2 class="font-display text-xl text-carbon-800 mb-6">Характеристики стеклопакета</h2>

      <div v-if="result.formula" class="bg-canvas rounded-xl p-4 mb-6 text-center">
        <p class="text-lg font-mono text-sage">{{ result.formula }}</p>
        <p class="text-xs text-carbon-400 mt-1">Формула стеклопакета</p>
      </div>

      <div class="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-6">
        <div v-for="(val, key) in { Ug: result.ug, 'Толщина': result.thickness, 'Масса': result.weight, 'Lt': result.lt }" :key="key"
             v-show="val !== undefined"
             class="bg-canvas rounded-xl p-4 text-center">
          <p class="text-xl font-display text-carbon-800">{{ val }}</p>
          <p class="text-xs text-carbon-400 mt-1 font-mono">{{ key }}</p>
        </div>
      </div>

      <pre v-if="!result.formula && result.ug === undefined"
           class="bg-canvas rounded-xl p-6 text-xs font-mono text-carbon-600 overflow-x-auto whitespace-pre-wrap">{{ JSON.stringify(result, null, 2) }}</pre>
    </section>
  </div>
</template>
