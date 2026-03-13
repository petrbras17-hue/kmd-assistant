<script setup>
import { computed } from "vue"

/**
 * ModuleHeader Component
 * Category badge, title, description, time estimate
 * Category options: docs, calc, ai, prod
 * Props: category, title, description, timeEstimate
 */

const props = defineProps({
  category: { type: String, default: "docs" },
  title: { type: String, required: true },
  description: { type: String, default: "" },
  timeEstimate: { type: String, default: "" },
})

const categoryColor = computed(() => {
  const colors = {
    docs: "bg-blue-100 text-blue-700",
    calc: "bg-purple-100 text-purple-700",
    ai: "bg-emerald-100 text-emerald-700",
    prod: "bg-orange-100 text-orange-700",
  }
  return colors[props.category] || colors.docs
})

const categoryLabel = computed(() => {
  const labels = {
    docs: "Documentation",
    calc: "Calculator",
    ai: "AI Tool",
    prod: "Production",
  }
  return labels[props.category] || props.category.toUpperCase()
})

const categoryIcon = computed(() => {
  const icons = {
    docs: "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z",
    calc: "M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z",
    ai: "M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z",
    prod: "M19.428 15.428a2 2 0 00-1.022-.547l-2.387-.477a6 6 0 00-3.86.517l-.318.158a6 6 0 01-3.86.517L6.05 15.21a2 2 0 00-1.806.547M8 4h8l-1 1v5.172a2 2 0 00.586 1.414l5 5c1.26 1.26.367 3.414-1.415 3.414H4.828c-1.782 0-2.674-2.154-1.414-3.414l5-5A2 2 0 009 10.172V5L8 4z",
  }
  return icons[props.category] || icons.docs
})
</script>

<template>
  <div class="space-y-4 mb-6 p-6 rounded-xl border border-carbon-200 bg-white">
    <!-- Category and Metadata -->
    <div class="flex items-center gap-3 flex-wrap">
      <span :class="[categoryColor, \"px-3 py-1.5 rounded-lg text-xs font-bold flex items-center gap-2 inline-flex\"]">
        <svg class="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
          <path stroke-linecap="round" stroke-linejoin="round" :d="categoryIcon" />
        </svg>
        {{ categoryLabel }}
      </span>

      <span v-if="timeEstimate" class="text-sm text-carbon-600 font-medium px-3 py-1.5 bg-canvas rounded-lg border border-carbon-200 flex items-center gap-2 inline-flex">
        <svg class="w-4 h-4 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4l3 2m6-3a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
        {{ timeEstimate }}
      </span>
    </div>

    <!-- Content -->
    <div>
      <h1 class="text-3xl font-bold text-carbon-900 mb-2 leading-tight">{{ title }}</h1>
      <p v-if="description" class="text-base text-carbon-700 leading-relaxed max-w-2xl">{{ description }}</p>
      <p v-if="!description" class="text-sm text-carbon-500">No description provided</p>
    </div>

    <!-- Divider -->
    <div class="pt-2 border-t border-carbon-200"></div>
  </div>
</template>
