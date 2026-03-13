<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { useAppStore } from '@/stores/app'

const store = useAppStore()
const route = useRoute()

/** Current category label based on route meta */
const currentCategory = computed(() => {
  const catKey = route.meta?.category
  if (!catKey) return null
  const cat = store.navCategories.find(c => c.key === catKey)
  return cat?.label || null
})

/** Current module label based on route name */
const currentModule = computed(() => {
  if (!route.meta?.category) return null
  for (const cat of store.navCategories) {
    const item = cat.items.find(i => i.id === route.name)
    if (item) return item.label
  }
  return null
})

function toggleSidebar() {
  store.sidebarOpen = !store.sidebarOpen
}

function toggleAiChat() {
  store.showAiChat = !store.showAiChat
}
</script>

<template>
  <header
    class="glass-nav fixed top-0 right-0 left-0 lg:left-[290px] z-50 h-14 flex items-center justify-between px-4 lg:px-6"
  >
    <!-- Left: hamburger + breadcrumb -->
    <div class="flex items-center gap-3">
      <!-- Hamburger (always visible on mobile, hidden on lg) -->
      <button
        class="lg:hidden flex items-center justify-center w-9 h-9 rounded-lg hover:bg-carbon-100 transition-colors"
        @click="toggleSidebar"
        aria-label="Toggle navigation"
      >
        <svg class="w-5 h-5 text-carbon-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
        </svg>
      </button>

      <!-- Breadcrumb -->
      <nav class="flex items-center text-sm" aria-label="Breadcrumb">
        <router-link
          to="/"
          class="text-carbon-400 hover:text-carbon-600 transition-colors font-medium"
        >
          KMD
        </router-link>
        <template v-if="currentCategory">
          <svg class="w-3.5 h-3.5 mx-1.5 text-carbon-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
          </svg>
          <span class="text-carbon-400">{{ currentCategory }}</span>
        </template>
        <template v-if="currentModule">
          <svg class="w-3.5 h-3.5 mx-1.5 text-carbon-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
          </svg>
          <span class="text-carbon-700 font-medium">{{ currentModule }}</span>
        </template>
      </nav>
    </div>

    <!-- Right: AI chat toggle -->
    <div class="flex items-center gap-2">
      <!-- Keyboard shortcut hint -->
      <span class="hidden md:inline-flex items-center gap-1 text-[0.6875rem] text-carbon-400 mr-1">
        <kbd class="px-1.5 py-0.5 rounded bg-carbon-100 text-carbon-500 font-mono text-[0.625rem] border border-carbon-200">
          Ctrl+K
        </kbd>
      </span>

      <!-- AI Chat button -->
      <button
        class="flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all duration-200"
        :class="[
          store.showAiChat
            ? 'bg-sage/10 text-sage-dark'
            : 'text-carbon-500 hover:text-carbon-700 hover:bg-carbon-100'
        ]"
        @click="toggleAiChat"
        aria-label="Toggle AI Chat"
      >
        <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z" />
        </svg>
        <span class="hidden sm:inline">AI</span>
      </button>
    </div>
  </header>
</template>
