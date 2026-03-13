<script setup>
import { reactive, ref } from 'vue'
import { useApi } from '@/composables/useApi'
import { useProgress } from '@/composables/useProgress'
import { useAppStore } from '@/stores/app'

const store = useAppStore()
const { loading, error, post } = useApi()
const { start, complete } = useProgress()

const form = reactive({
  project_name: '',
  object_name: '',
  system_type: 'фасадная система',
  floor_count: 1,
  area: 0,
  wind_region: 'III',
  seismic_zone: 6,
  additional_notes: '',
})
const result = ref(null)

const systemTypes = ['фасадная система', 'оконная система', 'витражная система', 'зенитный фонарь', 'входная группа']

async function submit() {
  result.value = null
  start([
    { label: 'Анализ параметров', at: 15 },
    { label: 'Генерация текста', at: 50 },
    { label: 'Подбор нормативных ссылок', at: 80 },
    { label: 'Финализация', at: 95 },
  ], 20000)
  try {
    result.value = await post('/api/ai-generate-note', { ...form })
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
      <h1 class="font-display text-3xl sm:text-4xl text-carbon-900 mb-3">Пояснительная записка</h1>
      <p class="text-carbon-500 font-body">{{ store.cardDescriptions.ainote }}</p>
    </header>

    <section class="bg-white rounded-2xl border border-carbon-200/60 p-8 mb-8 animate-fade-up" style="animation-delay:80ms">
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-5 mb-6">
        <div>
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">Наименование проекта</label>
          <input v-model="form.project_name" type="text" placeholder="ЖК «Резиденция»"
                 class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                        text-carbon-700 focus:outline-none focus:border-sage/50 focus:ring-1
                        focus:ring-sage/20 transition-colors" />
        </div>
        <div>
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">Объект</label>
          <input v-model="form.object_name" type="text" placeholder="Корпус 2, секция А"
                 class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                        text-carbon-700 focus:outline-none focus:border-sage/50 focus:ring-1
                        focus:ring-sage/20 transition-colors" />
        </div>
        <div>
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">Тип системы</label>
          <select v-model="form.system_type"
                  class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                         text-carbon-700 focus:outline-none focus:border-sage/50 focus:ring-1
                         focus:ring-sage/20 transition-colors">
            <option v-for="t in systemTypes" :key="t" :value="t">{{ t }}</option>
          </select>
        </div>
        <div>
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">Количество этажей</label>
          <input v-model.number="form.floor_count" type="number" min="1"
                 class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                        text-carbon-700 font-mono focus:outline-none focus:border-sage/50 focus:ring-1
                        focus:ring-sage/20 transition-colors" />
        </div>
        <div>
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">Площадь остекления, м2</label>
          <input v-model.number="form.area" type="number" min="0"
                 class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                        text-carbon-700 font-mono focus:outline-none focus:border-sage/50 focus:ring-1
                        focus:ring-sage/20 transition-colors" />
        </div>
        <div>
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">Ветровой район</label>
          <input v-model="form.wind_region" type="text"
                 class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                        text-carbon-700 font-mono focus:outline-none focus:border-sage/50 focus:ring-1
                        focus:ring-sage/20 transition-colors" />
        </div>
      </div>
      <div class="mb-6">
        <label class="block text-xs font-medium text-carbon-500 mb-1.5">Дополнительные указания</label>
        <textarea v-model="form.additional_notes" rows="3" placeholder="Особые условия эксплуатации, требования заказчика..."
                  class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                         text-carbon-700 focus:outline-none focus:border-sage/50 focus:ring-1
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
        <span v-else>Сгенерировать записку</span>
      </button>
    </section>

    <div v-if="error" class="bg-status-fail/10 border border-status-fail/20 rounded-xl p-4 mb-8 text-sm text-status-fail">
      {{ error }}
    </div>

    <section v-if="result" class="bg-white rounded-2xl border border-carbon-200/60 p-8 animate-scale-in">
      <h2 class="font-display text-xl text-carbon-800 mb-6">Пояснительная записка</h2>

      <div v-if="result.text || result.note" class="prose prose-sm max-w-none">
        <div class="bg-canvas rounded-xl p-6 text-sm text-carbon-700 leading-relaxed whitespace-pre-line font-body">
          {{ result.text || result.note }}
        </div>
      </div>

      <div v-if="result.references?.length" class="mt-6">
        <h3 class="text-sm font-medium text-carbon-600 mb-3">Нормативные ссылки</h3>
        <div class="flex flex-wrap gap-2">
          <span v-for="(ref_, i) in result.references" :key="i"
                class="text-xs font-mono text-sage bg-sage-pale px-3 py-1 rounded-lg">
            {{ ref_ }}
          </span>
        </div>
      </div>

      <pre v-if="!result.text && !result.note"
           class="bg-canvas rounded-xl p-6 text-xs font-mono text-carbon-600 overflow-x-auto whitespace-pre-wrap">{{ JSON.stringify(result, null, 2) }}</pre>
    </section>
  </div>
</template>
