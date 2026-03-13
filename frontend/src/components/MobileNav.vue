<script setup>
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAppStore } from '@/stores/app'

const store = useAppStore()
const router = useRouter()
const route = useRoute()

/** Navigation items for the bottom bar */
const navItems = [
  { key: 'home', label: 'Home', route: '/', icon: 'M2.25 12l8.954-8.955c.44-.439 1.152-.439 1.591 0L21.75 12M4.5 9.75v10.125c0 .621.504 1.125 1.125 1.125H9.75v-4.875c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125V21h4.125c.621 0 1.125-.504 1.125-1.125V9.75M8.25 21h8.25' },
  { key: 'docs', label: 'Docs', route: '/module/compare', icon: 'M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z' },
  { key: 'ai', label: 'AI', route: '/module/aireview', icon: 'M9.75 3.104v5.714a2.25 2.25 0 01-.659 1.591L5 14.5M9.75 3.104c-.251.023-.501.05-.75.082m.75-.082a24.301 24.301 0 014.5 0m0 0v5.714c0 .597.237 1.17.659 1.591L19.8 15.3M14.25 3.104c.251.023.501.05.75.082M19.8 15.3l-1.57.393A9.065 9.065 0 0112 15a9.065 9.065 0 00-6.23.693L5 14.5m14.8.8l1.402 1.402c1.232 1.232.65 3.318-1.067 3.611A48.309 48.309 0 0112 21c-2.773 0-5.491-.235-8.135-.687-1.718-.293-2.3-2.379-1.067-3.61L5 14.5' },
  { key: 'prod', label: 'Prod', route: '/module/projects', icon: 'M20.25 14.15v4.25c0 1.094-.787 2.036-1.872 2.18-2.087.277-4.216.42-6.378.42s-4.291-.143-6.378-.42c-1.085-.144-1.872-1.086-1.872-2.18v-4.25m16.5 0a2.18 2.18 0 00.75-1.661V8.706c0-1.081-.768-2.015-1.837-2.175a48.114 48.114 0 00-3.413-.387m4.5 8.006c-.194.165-.42.295-.673.38A23.978 23.978 0 0112 15.75c-2.648 0-5.195-.429-7.577-1.22a2.016 2.016 0 01-.673-.38m0 0A2.18 2.18 0 013 12.489V8.706c0-1.081.768-2.015 1.837-2.175a48.111 48.111 0 013.413-.387m7.5 0V5.25A2.25 2.25 0 0013.5 3h-3a2.25 2.25 0 00-2.25 2.25v.894m7.5 0a48.667 48.667 0 00-7.5 0' },
  { key: 'menu', label: 'Menu', route: null, icon: 'M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5' },
]

/** Determine which tab is active */
const activeKey = computed(() => {
  const cat = route.meta?.category
  if (!cat && route.path === '/') return 'home'
  if (cat === 'docs') return 'docs'
  if (cat === 'ai') return 'ai'
  if (cat === 'prod') return 'prod'
  return null
})

function handleTap(item) {
  if (item.key === 'menu') {
    store.sidebarOpen = !store.sidebarOpen
    return
  }
  if (item.route) {
    router.push(item.route)
  }
}
</script>

<template>
  <nav
    class="fixed bottom-0 left-0 right-0 z-50 lg:hidden"
    role="navigation"
    aria-label="Mobile navigation"
  >
    <!-- Glass background -->
    <div class="glass-nav border-t border-carbon-200/50 px-2 py-1.5 flex items-center justify-around">
      <button
        v-for="item in navItems"
        :key="item.key"
        class="flex flex-col items-center gap-0.5 px-3 py-1.5 rounded-xl transition-all duration-200 min-w-[3.5rem]"
        :class="[
          activeKey === item.key
            ? 'text-sage-dark bg-sage/10'
            : 'text-carbon-400 hover:text-carbon-600 active:bg-carbon-100'
        ]"
        @click="handleTap(item)"
      >
        <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
          <path stroke-linecap="round" stroke-linejoin="round" :d="item.icon" />
        </svg>
        <span class="text-[0.5625rem] font-medium tracking-wide">{{ item.label }}</span>
      </button>
    </div>
  </nav>
</template>
