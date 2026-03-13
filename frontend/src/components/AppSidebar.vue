<script setup>
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAppStore } from '@/stores/app'

const store = useAppStore()
const router = useRouter()
const route = useRoute()

/** Category icon map */
const categoryIcons = {
  docs: 'M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z',
  calc: 'M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z',
  visual: 'M14 10l-2 1m0 0l-2-1m2 1v2.5M20 7l-2 1m2-1l-2-1m2 1v2.5M14 4l-2-1-2 1M4 7l2-1M4 7l2 1M4 7v2.5M12 21l-2-1m2 1l2-1m-2 1v-2.5M6 18l-2-1v-2.5M18 18l2-1v-2.5',
  ai: 'M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z',
  prod: 'M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z',
  analytics: 'M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z',
}

/** Check if a nav item is the active route */
function isActive(itemId) {
  return route.name === itemId
}

/** Navigate to a module */
function navigateTo(itemId) {
  router.push({ name: itemId })
  // Close sidebar on mobile after navigation
  if (window.innerWidth < 1024) {
    store.sidebarOpen = false
  }
}

/** Close sidebar (mobile overlay tap) */
function closeSidebar() {
  store.sidebarOpen = false
}
</script>

<template>
  <!-- Mobile overlay -->
  <Transition name="fade">
    <div
      v-if="store.sidebarOpen"
      class="sidebar-overlay lg:hidden"
      @click="closeSidebar"
    />
  </Transition>

  <!-- Sidebar -->
  <aside
    class="sidebar"
    :class="{
      'collapsed': !store.sidebarOpen,
      'lg:translate-x-0': true,
    }"
    role="navigation"
    aria-label="Main navigation"
  >
    <!-- Logo -->
    <div class="px-6 pt-7 pb-5">
      <div class="flex items-center gap-3 mb-1">
        <div class="w-8 h-8 rounded-lg bg-sage/20 flex items-center justify-center">
          <svg class="w-4 h-4 text-sage-light" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M2.25 12.75V12A2.25 2.25 0 014.5 9.75h15A2.25 2.25 0 0121.75 12v.75m-8.69-6.44l-2.12-2.12a1.5 1.5 0 00-1.061-.44H4.5A2.25 2.25 0 002.25 6v12a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9a2.25 2.25 0 00-2.25-2.25h-5.379a1.5 1.5 0 01-1.06-.44z" />
          </svg>
        </div>
        <h1 class="font-display text-lg font-semibold text-white tracking-wide">
          KMD Assistant
        </h1>
      </div>
      <p class="text-[0.625rem] tracking-[0.15em] uppercase text-carbon-400 pl-11">
        ALDMEGA LAB &middot; v3.0 | 32 modules
      </p>
    </div>

    <!-- Search -->
    <div class="px-4 mb-4 relative">
      <svg
        class="absolute left-7 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-carbon-500 pointer-events-none"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
        stroke-width="2"
      >
        <path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
      </svg>
      <input
        v-model="store.navSearch"
        type="text"
        class="sidebar-search"
        placeholder="Поиск модуля..."
      />
    </div>

    <!-- Navigation categories -->
    <nav class="pb-6">
      <div v-for="cat in store.navCategories" :key="cat.key">
        <!-- Category header -->
        <button
          class="nav-category w-full"
          @click="store.toggleCategory(cat.key)"
          :aria-expanded="store.openCategories.includes(cat.key)"
        >
          <span class="flex items-center gap-2">
            <svg class="w-3 h-3 opacity-60" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" :d="categoryIcons[cat.key]" />
            </svg>
            {{ cat.label }}
          </span>
          <svg
            class="w-3 h-3 transition-transform duration-200"
            :class="{ 'rotate-180': store.openCategories.includes(cat.key) }"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            stroke-width="2"
          >
            <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        <!-- Items -->
        <Transition name="collapse">
          <div
            v-show="store.openCategories.includes(cat.key)"
            class="overflow-hidden"
          >
            <router-link
              v-for="item in store.filteredItems(cat)"
              :key="item.id"
              :to="{ name: item.id }"
              class="group flex items-center gap-2.5 px-6 py-[0.45rem] text-[0.8125rem] transition-all duration-200 cursor-pointer"
              :class="[
                isActive(item.id)
                  ? 'text-sage-light bg-sage/10 border-r-2 border-sage'
                  : 'text-carbon-300 hover:text-white hover:bg-white/[0.03]'
              ]"
              @click="window.innerWidth < 1024 && (store.sidebarOpen = false)"
            >
              <span class="truncate">{{ item.label }}</span>
              <span
                v-if="item.ai"
                class="ml-auto flex-shrink-0 text-[0.5625rem] px-1.5 py-0.5 rounded bg-sage/15 text-sage-light font-medium tracking-wide"
              >
                AI
              </span>
            </router-link>
          </div>
        </Transition>
      </div>
    </nav>
  </aside>
</template>

<style scoped>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.collapse-enter-active {
  transition: max-height 0.3s ease, opacity 0.25s ease;
  max-height: 500px;
}
.collapse-leave-active {
  transition: max-height 0.25s ease, opacity 0.15s ease;
  max-height: 500px;
}
.collapse-enter-from,
.collapse-leave-to {
  max-height: 0;
  opacity: 0;
}
</style>
