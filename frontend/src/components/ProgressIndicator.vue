<script setup>
import { ref, computed } from "vue"

/**
 * ProgressIndicator Component
 * Circular and linear progress modes with stage tracking
 * Props: progress (0-100), stages (array), mode (circular/linear)
 */

const props = defineProps({
  progress: { type: Number, default: 0 },
  stages: { type: Array, default: () => [] },
  mode: { type: String, default: "linear" },
})

const emit = defineEmits(["cancel"])

const displayProgress = computed(() => Math.min(100, Math.max(0, props.progress)))

const currentStageIndex = computed(() => {
  if (!props.stages.length) return 0
  return Math.floor((props.progress / 100) * props.stages.length)
})

const currentStage = computed(() => {
  if (!props.stages.length) return "Processing"
  const idx = Math.min(currentStageIndex.value, props.stages.length - 1)
  return props.stages[idx] || "Processing"
})

const completedCount = computed(() => {
  return currentStageIndex.value
})

function handleCancel() {
  emit("cancel")
}

function getStageStatus(idx) {
  return idx < currentStageIndex.value ? "completed" : idx === currentStageIndex.value ? "active" : "pending"
}

function getCircleDashOffset() {
  const radius = 50
  const circumference = 2 * Math.PI * radius
  return circumference * (1 - displayProgress.value / 100)
}
</script>

<template>
  <div v-if="mode === "circular"" class="flex flex-col items-center justify-center gap-6 p-6 rounded-xl border border-carbon-200 bg-white">
    <div class="relative w-32 h-32">
      <svg class="w-full h-full -rotate-90" viewBox="0 0 120 120">
        <circle cx="60" cy="60" r="50" fill="none" stroke="currentColor" stroke-width="4" class="text-carbon-200" />
        <circle cx="60" cy="60" r="50" fill="none" stroke="currentColor" stroke-width="4" class="text-sage transition-all duration-300" :style="{ strokeDasharray: 314, strokeDashoffset: getCircleDashOffset() }" stroke-linecap="round" />
      </svg>
      <div class="absolute inset-0 flex flex-col items-center justify-center">
        <span class="text-3xl font-bold text-carbon-900">{{ displayProgress }}</span>
        <span class="text-sm text-carbon-500">done</span>
      </div>
    </div>

    <div class="text-center">
      <p class="text-lg font-semibold text-carbon-900">{{ currentStage }}</p>
      <p class="text-sm text-carbon-600 mt-1">{{ completedCount }} of {{ stages.length }} stages</p>
    </div>

    <button @click="handleCancel" class="w-32 px-4 py-2 text-sm rounded-lg bg-carbon-100 text-carbon-700 hover:bg-carbon-200 font-medium transition-colors">
      Cancel
    </button>
  </div>

  <div v-else class="space-y-4 p-6 rounded-xl border border-carbon-200 bg-white">
    <div class="space-y-3">
      <div class="flex items-center justify-between">
        <p class="text-sm font-semibold text-carbon-900">{{ currentStage }}</p>
        <span class="text-lg font-mono text-sage font-bold">{{ displayProgress }}x</span>
      </div>
      <div class="relative w-full h-3 bg-carbon-100 rounded-full overflow-hidden">
        <div class="absolute inset-y-0 left-0 bg-sage rounded-full transition-all duration-500" :style="{ width: displayProgress + perc }"></div>
        <div class="absolute inset-0 bg-gradient-to-r from-transparent via-white to-transparent opacity-20"></div>
      </div>
    </div>

    <div v-if="stages.length > 1" class="space-y-2 mt-4 border-t border-carbon-100 pt-4">
      <p class="text-xs font-medium text-carbon-600 uppercase tracking-wide">Stages</p>
      <div class="grid grid-cols-1 gap-2">
        <div v-for="(stage, idx) in stages" :key="idx" class="flex items-center gap-3 p-2 rounded-lg transition-colors" :class="[getStageStatus(idx) === \"completed\" ? \"bg-emerald-50\" : getStageStatus(idx) === \"active\" ? \"bg-sage/10\" : \"bg-canvas\"]">
          <span :class="[\"w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold transition-colors\", getStageStatus(idx) === \"completed\" ? \"bg-sage text-white\" : getStageStatus(idx) === \"active\" ? \"bg-sage text-white\" : \"bg-carbon-200 text-carbon-600\"]">
            {{ idx + 1 }}
          </span>
          <span class="text-sm" :class="[getStageStatus(idx) === \"completed\" || getStageStatus(idx) === \"active\" ? \"text-carbon-900 font-medium\" : \"text-carbon-500\"]">{{ stage }}</span>
        </div>
      </div>
    </div>

    <button @click="handleCancel" class="w-full px-4 py-2 text-sm rounded-lg bg-carbon-100 text-carbon-700 hover:bg-carbon-200 font-medium transition-colors mt-6">
      Cancel Operation
    </button>
  </div>
</template>
