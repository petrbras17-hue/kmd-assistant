<script setup>
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAppStore } from '@/stores/app'

const router = useRouter()
const store = useAppStore()

const categories = computed(() =>
  store.navCategories.map(cat => ({
    key: cat.key,
    label: cat.label,
    description: store.catalogDescriptions[cat.key],
    count: cat.items.length,
    firstRoute: cat.items[0]?.id,
    icon: categoryIcons[cat.key],
  }))
)

const categoryIcons = {
  docs: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z',
  calc: 'M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z',
  visual: 'M14 10l-2 1m0 0l-2-1m2 1v2.5M20 7l-2 1m2-1l-2-1m2 1v2.5M14 4l-2-1-2 1M4 7l2-1M4 7l2 1M4 7v2.5M12 21l-2-1m2 1l2-1m-2 1v-2.5M6 18l-2-1v-2.5M18 18l2-1v-2.5',
  ai: 'M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z',
  prod: 'M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z',
  analytics: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z',
}

function openCategory(routeName) {
  if (routeName) router.push({ name: routeName })
}
</script>

<template>
  <div class="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
    <!-- Hero -->
    <section class="text-center mb-20 animate-fade-up">
      <div class="inline-block mb-6">
        <span class="text-xs font-mono tracking-[0.3em] uppercase text-sage">
          Платформа проектирования
        </span>
      </div>
      <h1 class="font-display text-5xl sm:text-6xl lg:text-7xl font-semibold text-carbon-900 mb-6 leading-tight">
        KMD Assistant
      </h1>
      <p class="max-w-2xl mx-auto text-lg text-carbon-500 font-body leading-relaxed">
        Инженерная платформа для работы с конструкциями металлических дверей.
        Проверка, расчёт, генерация и контроль — в&nbsp;едином интерфейсе.
      </p>
      <div class="mt-8 w-16 h-px bg-sage/40 mx-auto" />
    </section>

    <!-- Category Grid -->
    <section class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
      <article
        v-for="(cat, idx) in categories"
        :key="cat.key"
        class="group relative bg-white rounded-2xl border border-carbon-200/60 p-8
               hover:border-sage/40 hover:shadow-lg hover:shadow-sage/5
               transition-all duration-500 cursor-pointer animate-fade-up"
        :style="{ animationDelay: `${idx * 80}ms` }"
        @click="openCategory(cat.firstRoute)"
      >
        <!-- Icon -->
        <div class="w-12 h-12 rounded-xl bg-sage-pale flex items-center justify-center mb-5
                    group-hover:bg-sage/10 transition-colors duration-300">
          <svg class="w-6 h-6 text-sage" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
            <path stroke-linecap="round" stroke-linejoin="round" :d="cat.icon" />
          </svg>
        </div>

        <!-- Content -->
        <h2 class="font-display text-2xl text-carbon-800 mb-2">
          {{ cat.label }}
        </h2>
        <p class="text-sm text-carbon-400 font-body leading-relaxed mb-6">
          {{ cat.description }}
        </p>

        <!-- Footer -->
        <div class="flex items-center justify-between">
          <span class="text-xs font-mono text-carbon-300">
            {{ cat.count }} {{ cat.count === 1 ? 'модуль' : 'модулей' }}
          </span>
          <span class="text-xs text-sage font-medium opacity-0 group-hover:opacity-100
                       transform translate-x-2 group-hover:translate-x-0
                       transition-all duration-300">
            Открыть модуль &rarr;
          </span>
        </div>

        <!-- Decorative corner -->
        <div class="absolute top-0 right-0 w-20 h-20 bg-gradient-to-bl from-sage/[0.03] to-transparent
                    rounded-tr-2xl rounded-bl-[4rem] opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
      </article>
    </section>

    <!-- Footer note -->
    <footer class="mt-20 text-center">
      <p class="text-xs font-mono text-carbon-300 tracking-wide">
        v2.0 &middot; {{ categories.reduce((a, c) => a + c.count, 0) }} модулей &middot; Vue 3 + Vite
      </p>
    </footer>
  </div>
</template>
