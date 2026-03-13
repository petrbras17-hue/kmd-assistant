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
  system_series: 'ALT F50',
  construction_type: 'витраж',
  width: 3000,
  height: 4000,
  floors: 1,
  openings: [],
  glass_formula: '6-16Ar-4И',
  color: 'RAL 7016',
  fire_resistance: '',
  notes: '',
})
const result = ref(null)

const systemSeries = ['ALT F50', 'ALT F50 NL', 'ALT C48', 'ALT W62', 'ALT W72', 'Schuco FWS 50', 'Schuco FWS 60', 'Reynaers CW 50', 'Reynaers CW 60']
const constructionTypes = ['витраж', 'окно', 'дверь', 'фасад', 'входная группа', 'зенитный фонарь']

function addOpening() {
  form.openings.push({ type: 'поворотно-откидная', x: 0, y: 0, w: 800, h: 1200 })
}
function removeOpening(idx) {
  form.openings.splice(idx, 1)
}

async function submit() {
  result.value = null
  start([
    { label: 'Анализ параметров', at: 10 },
    { label: 'Расчёт конструктива', at: 30 },
    { label: 'Генерация спецификации', at: 55 },
    { label: 'Формирование КМД', at: 80 },
    { label: 'Финализация', at: 95 },
  ], 30000)
  try {
    result.value = await post('/api/ai-generate-kmd', { ...form })
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
      <h1 class="font-display text-3xl sm:text-4xl text-carbon-900 mb-3">Генерация КМД</h1>
      <p class="text-carbon-500 font-body">{{ store.cardDescriptions.aigenkmd }}</p>
    </header>

    <section class="bg-white rounded-2xl border border-carbon-200/60 p-8 mb-8 animate-fade-up" style="animation-delay:80ms">
      <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-5 mb-6">
        <div class="sm:col-span-2 lg:col-span-3">
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">Наименование проекта</label>
          <input v-model="form.project_name" type="text" placeholder="ЖК «Резиденция», корпус 2"
                 class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                        text-carbon-700 focus:outline-none focus:border-sage/50 focus:ring-1
                        focus:ring-sage/20 transition-colors" />
        </div>
        <div>
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">Профильная серия</label>
          <select v-model="form.system_series"
                  class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                         text-carbon-700 focus:outline-none focus:border-sage/50 focus:ring-1 focus:ring-sage/20">
            <option v-for="s in systemSeries" :key="s" :value="s">{{ s }}</option>
          </select>
        </div>
        <div>
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">Тип конструкции</label>
          <select v-model="form.construction_type"
                  class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                         text-carbon-700 focus:outline-none focus:border-sage/50 focus:ring-1 focus:ring-sage/20">
            <option v-for="t in constructionTypes" :key="t" :value="t">{{ t }}</option>
          </select>
        </div>
        <div>
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">Цвет (RAL)</label>
          <input v-model="form.color" type="text"
                 class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                        text-carbon-700 font-mono focus:outline-none focus:border-sage/50 focus:ring-1
                        focus:ring-sage/20 transition-colors" />
        </div>
        <div v-for="field in [
          { key: 'width', label: 'Ширина, мм' },
          { key: 'height', label: 'Высота, мм' },
        ]" :key="field.key">
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">{{ field.label }}</label>
          <input v-model.number="form[field.key]" type="number"
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

      <!-- Openings -->
      <div class="mb-6">
        <div class="flex items-center justify-between mb-3">
          <label class="text-xs font-medium text-carbon-500">Открывания</label>
          <button @click="addOpening" class="text-xs text-sage hover:text-sage-dark transition-colors font-medium">
            + Добавить открывание
          </button>
        </div>
        <div v-for="(op, i) in form.openings" :key="i"
             class="flex items-center gap-3 mb-2 bg-canvas rounded-lg p-3">
          <span class="text-xs font-mono text-carbon-400 w-6">{{ i + 1 }}</span>
          <input v-model="op.type" type="text" placeholder="Тип"
                 class="flex-1 px-2 py-1.5 bg-white border border-carbon-200/60 rounded text-xs text-carbon-700" />
          <input v-model.number="op.w" type="number" placeholder="Ш"
                 class="w-16 px-2 py-1.5 bg-white border border-carbon-200/60 rounded text-xs font-mono text-carbon-700" />
          <span class="text-xs text-carbon-300">x</span>
          <input v-model.number="op.h" type="number" placeholder="В"
                 class="w-16 px-2 py-1.5 bg-white border border-carbon-200/60 rounded text-xs font-mono text-carbon-700" />
          <button @click="removeOpening(i)" class="text-xs text-status-fail hover:text-status-fail/80">x</button>
        </div>
      </div>

      <div class="mb-6">
        <label class="block text-xs font-medium text-carbon-500 mb-1.5">Примечания</label>
        <textarea v-model="form.notes" rows="2"
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
          Генерация КМД...
        </span>
        <span v-else>Сгенерировать КМД</span>
      </button>
    </section>

    <div v-if="error" class="bg-status-fail/10 border border-status-fail/20 rounded-xl p-4 mb-8 text-sm text-status-fail">
      {{ error }}
    </div>

    <section v-if="result" class="bg-white rounded-2xl border border-carbon-200/60 p-8 animate-scale-in">
      <h2 class="font-display text-xl text-carbon-800 mb-6">Сгенерированный КМД</h2>

      <!-- Spec table -->
      <div v-if="result.spec?.length || result.elements?.length" class="overflow-x-auto mb-6">
        <table class="w-full text-sm">
          <thead>
            <tr class="border-b border-carbon-200/60">
              <th class="text-left py-3 px-3 text-xs font-mono text-carbon-400 uppercase">Поз.</th>
              <th class="text-left py-3 px-3 text-xs font-mono text-carbon-400 uppercase">Элемент</th>
              <th class="text-left py-3 px-3 text-xs font-mono text-carbon-400 uppercase">Профиль</th>
              <th class="text-right py-3 px-3 text-xs font-mono text-carbon-400 uppercase">Длина</th>
              <th class="text-right py-3 px-3 text-xs font-mono text-carbon-400 uppercase">Кол-во</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(el, i) in (result.spec || result.elements)" :key="i"
                class="border-b border-carbon-100 hover:bg-canvas transition-colors">
              <td class="py-3 px-3 font-mono text-carbon-500">{{ el.pos || i + 1 }}</td>
              <td class="py-3 px-3 text-carbon-700">{{ el.name || el.element }}</td>
              <td class="py-3 px-3 text-carbon-500 font-mono text-xs">{{ el.profile || el.article || '-' }}</td>
              <td class="py-3 px-3 text-right font-mono text-carbon-600">{{ el.length || '-' }}</td>
              <td class="py-3 px-3 text-right font-mono text-carbon-600">{{ el.qty || el.quantity || '-' }}</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div v-if="result.notes || result.description" class="bg-canvas rounded-xl p-6 text-sm text-carbon-600 whitespace-pre-line">
        {{ result.notes || result.description }}
      </div>

      <pre v-if="!result.spec && !result.elements && !result.notes && !result.description"
           class="bg-canvas rounded-xl p-6 text-xs font-mono text-carbon-600 overflow-x-auto whitespace-pre-wrap">{{ JSON.stringify(result, null, 2) }}</pre>
    </section>
  </div>
</template>
