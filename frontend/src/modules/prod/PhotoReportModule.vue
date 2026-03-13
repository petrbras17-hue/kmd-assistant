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
  stage: 'монтаж',
  date: new Date().toISOString().split('T')[0],
  description: '',
})
const photos = ref([])
const result = ref(null)

const stages = ['подготовка', 'доставка', 'монтаж', 'остекление', 'герметизация', 'приёмка', 'другое']

function onPhotos(e) {
  photos.value = Array.from(e.target.files)
}

async function submit() {
  if (!photos.value.length) return
  result.value = null
  start([
    { label: 'Загрузка фотографий', at: 20 },
    { label: 'Обработка изображений', at: 50 },
    { label: 'Формирование отчёта', at: 80 },
    { label: 'Финализация', at: 95 },
  ], 15000)
  try {
    result.value = await post('/api/generate-photo-report', form, {
      files: { photos: photos.value },
    })
  } catch { /* handled */ } finally {
    complete()
  }
}
</script>

<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
    <header class="mb-10 animate-fade-up">
      <span class="text-xs font-mono tracking-[0.2em] uppercase text-sage mb-2 block">Производство</span>
      <h1 class="font-display text-3xl sm:text-4xl text-carbon-900 mb-3">Фотоотчёт</h1>
      <p class="text-carbon-500 font-body">{{ store.cardDescriptions.photoreport }}</p>
    </header>

    <section class="bg-white rounded-2xl border border-carbon-200/60 p-8 mb-8 animate-fade-up" style="animation-delay:80ms">
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-5 mb-6">
        <div>
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">Проект</label>
          <input v-model="form.project_name" type="text"
                 class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                        text-carbon-700 focus:outline-none focus:border-sage/50 focus:ring-1
                        focus:ring-sage/20 transition-colors" />
        </div>
        <div>
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">Этап</label>
          <select v-model="form.stage"
                  class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                         text-carbon-700 focus:outline-none focus:border-sage/50 focus:ring-1 focus:ring-sage/20">
            <option v-for="s in stages" :key="s" :value="s">{{ s }}</option>
          </select>
        </div>
        <div>
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">Дата</label>
          <input v-model="form.date" type="date"
                 class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                        text-carbon-700 font-mono focus:outline-none focus:border-sage/50 focus:ring-1
                        focus:ring-sage/20 transition-colors" />
        </div>
      </div>
      <div class="mb-6">
        <label class="block text-xs font-medium text-carbon-500 mb-1.5">Описание</label>
        <textarea v-model="form.description" rows="2"
                  class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                         text-carbon-700 focus:outline-none focus:border-sage/50 focus:ring-1
                         focus:ring-sage/20 transition-colors resize-none" />
      </div>
      <div class="mb-6">
        <label class="block text-xs font-medium text-carbon-500 mb-1.5">Фотографии</label>
        <input type="file" accept="image/*" multiple @change="onPhotos"
               class="block w-full text-sm text-carbon-500 file:mr-4 file:py-2.5 file:px-4
                      file:rounded-lg file:border-0 file:text-sm file:font-medium
                      file:bg-sage-pale file:text-sage-dark hover:file:bg-sage/10
                      file:cursor-pointer file:transition-colors" />
        <p v-if="photos.length" class="mt-2 text-xs text-carbon-400 font-mono">
          Выбрано файлов: {{ photos.length }}
        </p>
      </div>

      <button @click="submit" :disabled="!photos.length || loading"
              class="px-6 py-3 bg-sage text-white text-sm font-medium rounded-xl
                     hover:bg-sage-dark disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
        <span v-if="loading" class="flex items-center gap-2">
          <svg class="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
            <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
            <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
          </svg>
          Формирование...
        </span>
        <span v-else>Сформировать отчёт</span>
      </button>
    </section>

    <div v-if="error" class="bg-status-fail/10 border border-status-fail/20 rounded-xl p-4 mb-8 text-sm text-status-fail">
      {{ error }}
    </div>

    <section v-if="result" class="bg-white rounded-2xl border border-carbon-200/60 p-8 animate-scale-in">
      <h2 class="font-display text-xl text-carbon-800 mb-6">Фотоотчёт</h2>

      <div v-if="result.report || result.text" class="bg-canvas rounded-xl p-6 text-sm text-carbon-700 leading-relaxed whitespace-pre-line mb-6">
        {{ result.report || result.text }}
      </div>

      <div v-if="result.photos?.length" class="grid grid-cols-2 sm:grid-cols-3 gap-4">
        <div v-for="(p, i) in result.photos" :key="i"
             class="bg-canvas rounded-xl overflow-hidden">
          <div class="aspect-[4/3] bg-carbon-100 flex items-center justify-center text-xs text-carbon-300">
            {{ p.filename || `Фото ${i + 1}` }}
          </div>
          <p v-if="p.caption" class="p-3 text-xs text-carbon-500">{{ p.caption }}</p>
        </div>
      </div>

      <pre v-if="!result.report && !result.text && !result.photos"
           class="bg-canvas rounded-xl p-6 text-xs font-mono text-carbon-600 overflow-x-auto whitespace-pre-wrap">{{ JSON.stringify(result, null, 2) }}</pre>
    </section>
  </div>
</template>
