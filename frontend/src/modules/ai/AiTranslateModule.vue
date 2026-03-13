<script setup>
import { reactive, ref } from 'vue'
import { useApi } from '@/composables/useApi'
import { useProgress } from '@/composables/useProgress'
import { useAppStore } from '@/stores/app'

const store = useAppStore()
const { loading, error, post } = useApi()
const { start, complete } = useProgress()

const form = reactive({
  text: '',
  direction: 'gost_to_en',
  context: 'алюминиевые конструкции',
})
const result = ref(null)

const directions = [
  { value: 'gost_to_en', label: 'ГОСТ / СП -> EN / ISO' },
  { value: 'en_to_gost', label: 'EN / ISO -> ГОСТ / СП' },
]
const contexts = ['алюминиевые конструкции', 'стальные конструкции', 'стеклопакеты', 'фурнитура', 'общестрой']

async function submit() {
  if (!form.text.trim()) return
  result.value = null
  start([
    { label: 'Анализ терминологии', at: 25 },
    { label: 'Поиск соответствий', at: 55 },
    { label: 'Формирование перевода', at: 85 },
  ], 10000)
  try {
    result.value = await post('/api/ai-translate', { ...form })
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
      <h1 class="font-display text-3xl sm:text-4xl text-carbon-900 mb-3">Перевод ГОСТ/EN</h1>
      <p class="text-carbon-500 font-body">{{ store.cardDescriptions.aitranslate }}</p>
    </header>

    <section class="bg-white rounded-2xl border border-carbon-200/60 p-8 mb-8 animate-fade-up" style="animation-delay:80ms">
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-5 mb-6">
        <div>
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">Направление</label>
          <select v-model="form.direction"
                  class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                         text-carbon-700 focus:outline-none focus:border-sage/50 focus:ring-1 focus:ring-sage/20">
            <option v-for="d in directions" :key="d.value" :value="d.value">{{ d.label }}</option>
          </select>
        </div>
        <div>
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">Контекст</label>
          <select v-model="form.context"
                  class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                         text-carbon-700 focus:outline-none focus:border-sage/50 focus:ring-1 focus:ring-sage/20">
            <option v-for="c in contexts" :key="c" :value="c">{{ c }}</option>
          </select>
        </div>
      </div>

      <div class="mb-6">
        <label class="block text-xs font-medium text-carbon-500 mb-1.5">Текст или обозначение норматива</label>
        <textarea v-model="form.text" rows="4"
                  placeholder="Например: ГОСТ 21519-2003 или EN 14351-1:2006"
                  class="w-full px-4 py-3 bg-canvas border border-carbon-200/60 rounded-xl text-sm
                         text-carbon-700 focus:outline-none focus:border-sage/50 focus:ring-1
                         focus:ring-sage/20 transition-colors resize-none" />
      </div>

      <button @click="submit" :disabled="!form.text.trim() || loading"
              class="px-6 py-3 bg-sage text-white text-sm font-medium rounded-xl
                     hover:bg-sage-dark disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
        <span v-if="loading" class="flex items-center gap-2">
          <svg class="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
          </svg>
          Перевод...
        </span>
        <span v-else>Перевести</span>
      </button>
    </section>

    <div v-if="error" class="bg-status-fail/10 border border-status-fail/20 rounded-xl p-4 mb-8 text-sm text-status-fail">
      {{ error }}
    </div>

    <section v-if="result" class="bg-white rounded-2xl border border-carbon-200/60 p-8 animate-scale-in">
      <h2 class="font-display text-xl text-carbon-800 mb-6">Результат перевода</h2>

      <!-- Mapping table -->
      <div v-if="result.mappings?.length" class="overflow-x-auto mb-6">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-carbon-200/60">
              <th class="text-left py-3 px-4 text-xs font-mono text-carbon-400 uppercase">Исходный</th>
              <th class="text-left py-3 px-4 text-xs font-mono text-carbon-400 uppercase">Соответствие</th>
              <th class="text-left py-3 px-4 text-xs font-mono text-carbon-400 uppercase">Примечание</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(m, i) in result.mappings" :key="i"
                class="border-b border-carbon-100 hover:bg-canvas transition-colors">
              <td class="py-3 px-4 font-mono text-carbon-600 text-xs">{{ m.source || m.from }}</td>
              <td class="py-3 px-4 font-mono text-sage text-xs">{{ m.target || m.to }}</td>
              <td class="py-3 px-4 text-carbon-400 text-xs">{{ m.note || '-' }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="result.translation || result.text" class="bg-canvas rounded-xl p-6 text-sm text-carbon-700 leading-relaxed whitespace-pre-line">
        {{ result.translation || result.text }}
      </div>

      <pre v-if="!result.mappings && !result.translation && !result.text"
           class="bg-canvas rounded-xl p-6 text-xs font-mono text-carbon-600 overflow-x-auto whitespace-pre-wrap">{{ JSON.stringify(result, null, 2) }}</pre>
    </section>
  </div>
</template>
