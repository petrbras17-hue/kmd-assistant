<script setup>
import { ref, computed, onMounted } from 'vue'
import { useApi } from '@/composables/useApi'
import { useAppStore } from '@/stores/app'

const store = useAppStore()
const { loading, error, get } = useApi()

const nodes = ref([])
const search = ref('')
const selectedCategory = ref('all')

const categories = computed(() => {
  const cats = new Set(nodes.value.map(n => n.category || n.type || 'Общие'))
  return ['all', ...Array.from(cats)]
})

const filteredNodes = computed(() => {
  let filtered = nodes.value
  if (selectedCategory.value !== 'all') {
    filtered = filtered.filter(n => (n.category || n.type || 'Общие') === selectedCategory.value)
  }
  if (search.value.trim()) {
    const q = search.value.toLowerCase()
    filtered = filtered.filter(n =>
      (n.name || '').toLowerCase().includes(q) ||
      (n.description || '').toLowerCase().includes(q) ||
      (n.code || '').toLowerCase().includes(q)
    )
  }
  return filtered
})

async function loadNodes() {
  try {
    const data = await get('/api/nodes-library')
    nodes.value = data?.nodes || data || []
  } catch { /* handled */ }
}

onMounted(loadNodes)
</script>

<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
    <header class="mb-10 animate-fade-up">
      <span class="text-xs font-mono tracking-[0.2em] uppercase text-sage mb-2 block">Производство</span>
      <h1 class="font-display text-3xl sm:text-4xl text-carbon-900 mb-3">Библиотека узлов</h1>
      <p class="text-carbon-500 font-body">{{ store.cardDescriptions.nodeslibrary }}</p>
    </header>

    <!-- Filters -->
    <section class="bg-white rounded-2xl border border-carbon-200/60 p-6 mb-8 animate-fade-up" style="animation-delay:80ms">
      <div class="flex flex-col sm:flex-row gap-4">
        <div class="flex-1">
          <input v-model="search" type="text" placeholder="Поиск по названию или коду..."
                 class="w-full px-4 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                        text-carbon-700 focus:outline-none focus:border-sage/50 focus:ring-1
                        focus:ring-sage/20 transition-colors" />
        </div>
        <div class="flex gap-2 flex-wrap">
          <button v-for="cat in categories" :key="cat"
                  @click="selectedCategory = cat"
                  class="px-3 py-1.5 rounded-lg text-xs font-medium transition-colors"
                  :class="selectedCategory === cat
                    ? 'bg-sage text-white'
                    : 'bg-canvas text-carbon-500 hover:bg-canvas-dark'">
            {{ cat === 'all' ? 'Все' : cat }}
          </button>
        </div>
      </div>
    </section>

    <div v-if="error" class="bg-status-fail/10 border border-status-fail/20 rounded-xl p-4 mb-8 text-sm text-status-fail">
      {{ error }}
    </div>

    <!-- Loading -->
    <div v-if="loading" class="text-center py-12">
      <div class="inline-flex items-center gap-2 text-sm text-carbon-400">
        <svg class="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
        </svg>
        Загрузка библиотеки...
      </div>
    </div>

    <!-- Nodes grid -->
    <section v-else-if="filteredNodes.length" class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      <div v-for="(node, i) in filteredNodes" :key="i"
           class="bg-white rounded-2xl border border-carbon-200/60 p-5
                  hover:border-sage/30 hover:shadow-md hover:shadow-sage/5
                  transition-all duration-300 animate-fade-up"
           :style="{ animationDelay: `${Math.min(i * 40, 400)}ms` }">
        <!-- Preview placeholder -->
        <div class="aspect-square bg-canvas rounded-xl mb-4 flex items-center justify-center">
          <svg class="w-10 h-10 text-carbon-200" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1">
            <path stroke-linecap="round" stroke-linejoin="round"
                  d="M14 10l-2 1m0 0l-2-1m2 1v2.5M20 7l-2 1m2-1l-2-1m2 1v2.5M14 4l-2-1-2 1M4 7l2-1M4 7l2 1M4 7v2.5M12 21l-2-1m2 1l2-1m-2 1v-2.5M6 18l-2-1v-2.5M18 18l2-1v-2.5" />
          </svg>
        </div>

        <h3 class="text-sm font-medium text-carbon-700 mb-1">{{ node.name || node.title }}</h3>
        <p v-if="node.code" class="text-xs font-mono text-sage mb-2">{{ node.code }}</p>
        <p v-if="node.description" class="text-xs text-carbon-400 line-clamp-2">{{ node.description }}</p>
        <div v-if="node.category || node.type" class="mt-3">
          <span class="text-xs bg-canvas text-carbon-400 px-2 py-0.5 rounded font-mono">
            {{ node.category || node.type }}
          </span>
        </div>
      </div>
    </section>

    <p v-else class="text-center text-sm text-carbon-400 py-12">
      {{ search || selectedCategory !== 'all' ? 'Ничего не найдено.' : 'Библиотека пуста.' }}
    </p>
  </div>
</template>
