<script setup>
import { reactive, ref, onMounted } from 'vue'
import { useApi } from '@/composables/useApi'
import { useAppStore } from '@/stores/app'

const store = useAppStore()
const listApi = useApi()
const createApi = useApi()

const projects = ref([])
const showForm = ref(false)
const form = reactive({
  name: '',
  code: '',
  client: '',
  address: '',
  description: '',
})

async function loadProjects() {
  try {
    const data = await listApi.get('/api/projects/list')
    projects.value = data?.projects || data || []
  } catch { /* handled */ }
}

async function createProject() {
  if (!form.name.trim()) return
  try {
    await createApi.post('/api/projects/create', { ...form })
    showForm.value = false
    form.name = ''
    form.code = ''
    form.client = ''
    form.address = ''
    form.description = ''
    await loadProjects()
  } catch { /* handled */ }
}

onMounted(loadProjects)
</script>

<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
    <header class="mb-10 animate-fade-up">
      <span class="text-xs font-mono tracking-[0.2em] uppercase text-sage mb-2 block">Производство</span>
      <h1 class="font-display text-3xl sm:text-4xl text-carbon-900 mb-3">Проекты</h1>
      <p class="text-carbon-500 font-body">{{ store.cardDescriptions.projects }}</p>
    </header>

    <!-- Create button -->
    <div class="mb-8 animate-fade-up" style="animation-delay:80ms">
      <button @click="showForm = !showForm"
              class="px-5 py-2.5 bg-sage text-white text-sm font-medium rounded-xl
                     hover:bg-sage-dark transition-colors">
        {{ showForm ? 'Отмена' : 'Новый проект' }}
      </button>
    </div>

    <!-- Create form -->
    <Transition name="fade">
      <section v-if="showForm" class="bg-white rounded-2xl border border-carbon-200/60 p-8 mb-8">
        <h2 class="text-sm font-medium text-carbon-700 mb-4">Создание проекта</h2>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-5 mb-6">
          <div>
            <label class="block text-xs font-medium text-carbon-500 mb-1.5">Наименование *</label>
            <input v-model="form.name" type="text" placeholder="ЖК «Резиденция»"
                   class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                          text-carbon-700 focus:outline-none focus:border-sage/50 focus:ring-1
                          focus:ring-sage/20 transition-colors" />
          </div>
          <div>
            <label class="block text-xs font-medium text-carbon-500 mb-1.5">Шифр</label>
            <input v-model="form.code" type="text" placeholder="2024-KMD-001"
                   class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                          text-carbon-700 font-mono focus:outline-none focus:border-sage/50 focus:ring-1
                          focus:ring-sage/20 transition-colors" />
          </div>
          <div>
            <label class="block text-xs font-medium text-carbon-500 mb-1.5">Заказчик</label>
            <input v-model="form.client" type="text"
                   class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                          text-carbon-700 focus:outline-none focus:border-sage/50 focus:ring-1
                          focus:ring-sage/20 transition-colors" />
          </div>
          <div>
            <label class="block text-xs font-medium text-carbon-500 mb-1.5">Адрес</label>
            <input v-model="form.address" type="text"
                   class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                          text-carbon-700 focus:outline-none focus:border-sage/50 focus:ring-1
                          focus:ring-sage/20 transition-colors" />
          </div>
          <div class="sm:col-span-2">
            <label class="block text-xs font-medium text-carbon-500 mb-1.5">Описание</label>
            <textarea v-model="form.description" rows="2"
                      class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                             text-carbon-700 focus:outline-none focus:border-sage/50 focus:ring-1
                             focus:ring-sage/20 transition-colors resize-none" />
          </div>
        </div>

        <button @click="createProject" :disabled="!form.name.trim() || createApi.loading.value"
                class="px-6 py-3 bg-sage text-white text-sm font-medium rounded-xl
                       hover:bg-sage-dark disabled:opacity-40 disabled:cursor-not-allowed transition-colors">
          {{ createApi.loading.value ? 'Создание...' : 'Создать' }}
        </button>

        <div v-if="createApi.error.value" class="mt-4 text-sm text-status-fail">{{ createApi.error.value }}</div>
      </section>
    </Transition>

    <!-- Projects list -->
    <section class="bg-white rounded-2xl border border-carbon-200/60 p-8 animate-fade-up" style="animation-delay:160ms">
      <h2 class="font-display text-xl text-carbon-800 mb-6">Список проектов</h2>

      <div v-if="listApi.loading.value" class="text-sm text-carbon-400">Загрузка...</div>

      <div v-else-if="projects.length" class="space-y-3">
        <div v-for="(p, i) in projects" :key="i"
             class="bg-canvas rounded-xl p-5 hover:bg-canvas-dark transition-colors">
          <div class="flex items-start justify-between mb-2">
            <h3 class="text-sm font-medium text-carbon-700">{{ p.name }}</h3>
            <span v-if="p.code" class="text-xs font-mono text-sage bg-sage-pale px-2 py-0.5 rounded">{{ p.code }}</span>
          </div>
          <p v-if="p.client || p.address" class="text-xs text-carbon-400">
            {{ [p.client, p.address].filter(Boolean).join(' | ') }}
          </p>
          <p v-if="p.description" class="text-xs text-carbon-400 mt-1">{{ p.description }}</p>
          <div v-if="p.created_at || p.status" class="flex gap-3 mt-2 text-xs text-carbon-300">
            <span v-if="p.status" class="font-mono">{{ p.status }}</span>
            <span v-if="p.created_at">{{ p.created_at }}</span>
          </div>
        </div>
      </div>

      <p v-else class="text-sm text-carbon-400">Нет проектов. Создайте первый.</p>
    </section>
  </div>
</template>
