<script setup>
import { onMounted } from 'vue'
import { useAppStore } from '@/stores/app'
import AppSidebar from '@/components/AppSidebar.vue'
import TopBar from '@/components/TopBar.vue'
import MobileNav from '@/components/MobileNav.vue'
import AiChatPanel from '@/components/AiChatPanel.vue'
import ProgressBar from '@/components/ProgressBar.vue'

const store = useAppStore()

onMounted(() => {
  store.loadState()
})
</script>

<template>
  <div class="min-h-screen bg-canvas">
    <!-- Sidebar overlay (mobile) -->
    <Transition name="fade">
      <div
        v-if="store.sidebarOpen"
        class="sidebar-overlay lg:hidden"
        @click="store.sidebarOpen = false"
      />
    </Transition>

    <!-- Sidebar -->
    <AppSidebar />

    <!-- Main content -->
    <div
      class="transition-all duration-500 ease-out"
      :class="store.sidebarOpen ? 'lg:ml-[290px]' : 'ml-0'"
    >
      <!-- Top bar -->
      <TopBar />

      <!-- Progress bar -->
      <ProgressBar v-if="store.aiProgress.active" />

      <!-- Page content -->
      <main class="pt-16 pb-20 lg:pb-8">
        <router-view v-slot="{ Component, route }">
          <Transition name="tab" mode="out-in">
            <component :is="Component" :key="route.path" />
          </Transition>
        </router-view>
      </main>
    </div>

    <!-- AI Chat Panel -->
    <AiChatPanel />

    <!-- Mobile Navigation -->
    <MobileNav class="lg:hidden" />
  </div>
</template>

<style>
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}

.tab-enter-active {
  animation: bookOpen 0.7s cubic-bezier(0.22, 1, 0.36, 1) both;
  transform-origin: left center;
}
.tab-leave-active {
  animation: bookClose 0.25s ease both;
  transform-origin: right center;
}
</style>
