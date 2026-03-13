<script setup>
import { computed } from 'vue'
import { useAppStore } from '@/stores/app'

const store = useAppStore()

const progress = computed(() => store.aiProgress)

/** Stage dots: highlight completed and current stages */
const stageIndicators = computed(() => {
  if (!progress.value.stages.length) return []
  return progress.value.stages.map((stage, idx) => ({
    label: stage.label,
    completed: idx < progress.value.currentStage,
    current: idx === progress.value.currentStage,
  }))
})
</script>

<template>
  <Transition name="progress-slide">
    <div
      v-if="progress.active"
      class="w-full rounded-xl bg-white border border-carbon-200 p-4 overflow-hidden"
    >
      <!-- Stage label -->
      <div class="flex items-center justify-between mb-2">
        <span class="text-sm font-medium text-carbon-700">
          {{ progress.currentLabel }}
        </span>
        <span class="text-sm font-mono text-sage font-semibold tabular-nums">
          {{ progress.percent }}%
        </span>
      </div>

      <!-- Progress bar track -->
      <div class="relative w-full h-2.5 bg-carbon-100 rounded-full overflow-hidden">
        <!-- Fill -->
        <div
          class="absolute inset-y-0 left-0 bg-sage rounded-full transition-[width] duration-300 ease-out"
          :style="{ width: `${progress.percent}%` }"
        >
          <!-- Shimmer overlay -->
          <div class="absolute inset-0 progress-shimmer rounded-full" />
        </div>
      </div>

      <!-- Stage indicators -->
      <div
        v-if="stageIndicators.length > 1"
        class="flex items-center justify-between mt-3 gap-1"
      >
        <div
          v-for="(stage, idx) in stageIndicators"
          :key="idx"
          class="flex items-center gap-1.5 min-w-0"
        >
          <!-- Dot -->
          <span
            class="w-1.5 h-1.5 rounded-full flex-shrink-0 transition-colors duration-300"
            :class="{
              'bg-sage': stage.completed || stage.current,
              'bg-carbon-300': !stage.completed && !stage.current,
              'animate-pulse-glow': stage.current,
            }"
          />
          <!-- Label (shown only for current and adjacent stages on small screens) -->
          <span
            class="text-[0.625rem] truncate transition-colors duration-200"
            :class="stage.current ? 'text-sage font-medium' : 'text-carbon-400'"
          >
            {{ stage.label }}
          </span>
        </div>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
.progress-slide-enter-active {
  transition: all 0.4s cubic-bezier(0.22, 1, 0.36, 1);
}
.progress-slide-leave-active {
  transition: all 0.25s ease;
}
.progress-slide-enter-from {
  opacity: 0;
  transform: translateY(8px) scale(0.98);
}
.progress-slide-leave-to {
  opacity: 0;
  transform: translateY(-4px) scale(0.99);
}
</style>
