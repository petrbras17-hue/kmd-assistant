<script setup>
import { ref } from 'vue'
import { useApi } from '@/composables/useApi'
import { useProgress } from '@/composables/useProgress'
import { useAppStore } from '@/stores/app'

const store = useAppStore()
const { loading, error, post } = useApi()
const { start, complete } = useProgress()

const question = ref('')
const result = ref(null)
const history = ref([])

async function submit() {
  if (!question.value.trim()) return
  result.value = null
  const q = question.value.trim()
  start([
    { label: 'Поиск в базе знаний', at: 25 },
    { label: 'Анализ нормативов', at: 55 },
    { label: 'Формирование ответа', at: 85 },
  ], 12000)
  try {
    result.value = await post('/api/ai-gost', { question: q })
    history.value.unshift({ question: q, answer: result.value.answer || result.value.text || JSON.stringify(result.value) })
    if (history.value.length > 10) history.value.pop()
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
      <h1 class="font-display text-3xl sm:text-4xl text-carbon-900 mb-3">Консультант ГОСТ</h1>
      <p class="text-carbon-500 font-body">{{ store.cardDescriptions.aigost }}</p>
    </header>

    <section class="bg-white rounded-2xl border border-carbon-200/60 p-8 mb-8 animate-fade-up" style="animation-delay:80ms">
      <label class="block text-sm font-medium text-carbon-600 mb-2">Ваш вопрос</label>
      <textarea v-model="question" rows="3"
                placeholder="Например: Какой минимальный Uw для жилых зданий по ГОСТ 26602.1?"
                class="w-full px-4 py-3 bg-canvas border border-carbon-200/60 rounded-xl text-sm
                       text-carbon-700 focus:outline-none focus:border-sage/50 focus:ring-1
                       focus:ring-sage/20 transition-colors resize-none"
                @keydown.meta.enter="submit"
                @keydown.ctrl.enter="submit" />
      <div class="flex items-center justify-between mt-4">
        <span class="text-xs text-carbon-300">Cmd+Enter для отправки</span>
        <button @click="submit" :disabled="!question.trim() || loading"
                class="px-6 py-3 bg-sage text-white text-sm font-medium rounded-xl
                       hover:bg-sage-dark disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
          <span v-if="loading" class="flex items-center gap-2">
            <svg class="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
              <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
              <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
            </svg>
            Поиск...
          </span>
          <span v-else>Спросить</span>
        </button>
      </div>
    </section>

    <div v-if="error" class="bg-status-fail/10 border border-status-fail/20 rounded-xl p-4 mb-8 text-sm text-status-fail">
      {{ error }}
    </div>

    <section v-if="result" class="bg-white rounded-2xl border border-carbon-200/60 p-8 mb-8 animate-scale-in">
      <h2 class="font-display text-xl text-carbon-800 mb-6">Ответ</h2>

      <div class="bg-canvas rounded-xl p-6 text-sm text-carbon-700 leading-relaxed whitespace-pre-line">
        {{ result.answer || result.text || result.response }}
      </div>

      <div v-if="result.sources?.length" class="mt-6">
        <h3 class="text-sm font-medium text-carbon-600 mb-3">Источники</h3>
        <div class="space-y-2">
          <div v-for="(src, i) in result.sources" :key="i"
               class="flex items-start gap-2 text-xs text-carbon-500">
            <span class="font-mono text-sage">{{ i + 1 }}.</span>
            <span>{{ typeof src === 'string' ? src : src.title || src.name || JSON.stringify(src) }}</span>
          </div>
        </div>
      </div>

      <pre v-if="!result.answer && !result.text && !result.response"
           class="bg-canvas rounded-xl p-6 text-xs font-mono text-carbon-600 overflow-x-auto whitespace-pre-wrap mt-4">{{ JSON.stringify(result, null, 2) }}</pre>
    </section>

    <!-- History -->
    <section v-if="history.length > 1" class="space-y-4">
      <h3 class="text-sm font-medium text-carbon-400">Предыдущие вопросы</h3>
      <div v-for="(h, i) in history.slice(1)" :key="i"
           class="bg-white rounded-xl border border-carbon-200/40 p-5">
        <p class="text-xs font-medium text-carbon-500 mb-2">{{ h.question }}</p>
        <p class="text-xs text-carbon-400 line-clamp-3">{{ h.answer }}</p>
      </div>
    </section>
  </div>
</template>
