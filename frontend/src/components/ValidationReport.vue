<script setup>
import { ref, computed } from 'vue'

/**
 * @typedef {Object} ValidationItem
 * @property {string} label - Item description
 * @property {'ok'|'warn'|'fail'|'info'} severity - Severity level
 * @property {string} [details] - Optional expanded details
 */

/**
 * @typedef {Object} ValidationReportData
 * @property {string} title - Report title
 * @property {number} score - Score percentage (0-100)
 * @property {ValidationItem[]} items - Validation items
 */

const props = defineProps({
  /** @type {ValidationReportData} */
  report: {
    type: Object,
    required: true,
    validator: (v) => v && typeof v.title === 'string' && typeof v.score === 'number' && Array.isArray(v.items),
  },
})

/** Track expanded items by index */
const expandedItems = ref(new Set())

function toggleItem(idx) {
  if (expandedItems.value.has(idx)) {
    expandedItems.value.delete(idx)
  } else {
    expandedItems.value.add(idx)
  }
}

/** Score bar color based on value */
const scoreColor = computed(() => {
  const s = props.report.score
  if (s >= 80) return 'bg-status-ok'
  if (s >= 50) return 'bg-status-warn'
  return 'bg-status-fail'
})

const scoreTextColor = computed(() => {
  const s = props.report.score
  if (s >= 80) return 'text-status-ok'
  if (s >= 50) return 'text-status-warn'
  return 'text-status-fail'
})

/** Severity icon paths */
const severityIcons = {
  ok: 'M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  warn: 'M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z',
  fail: 'M9.75 9.75l4.5 4.5m0-4.5l-4.5 4.5M21 12a9 9 0 11-18 0 9 9 0 0118 0z',
  info: 'M11.25 11.25l.041-.02a.75.75 0 011.063.852l-.708 2.836a.75.75 0 001.063.853l.041-.021M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9-3.75h.008v.008H12V8.25z',
}

/** Severity labels */
const severityLabels = {
  ok: 'OK',
  warn: 'Внимание',
  fail: 'Ошибка',
  info: 'Инфо',
}

/** Count items by severity */
const summaryCounts = computed(() => {
  const counts = { ok: 0, warn: 0, fail: 0, info: 0 }
  for (const item of props.report.items) {
    if (counts[item.severity] !== undefined) counts[item.severity]++
  }
  return counts
})
</script>

<template>
  <div class="bg-white rounded-2xl border border-carbon-200 overflow-hidden">
    <!-- Header -->
    <div class="px-6 py-5 border-b border-carbon-100">
      <div class="flex items-center justify-between mb-3">
        <h3 class="font-display text-lg font-semibold text-carbon-800">
          {{ report.title }}
        </h3>
        <span
          class="text-2xl font-display font-bold"
          :class="scoreTextColor"
        >
          {{ report.score }}%
        </span>
      </div>

      <!-- Score bar -->
      <div class="w-full h-2 bg-carbon-100 rounded-full overflow-hidden">
        <div
          class="h-full rounded-full transition-all duration-700 ease-out"
          :class="scoreColor"
          :style="{ width: `${report.score}%` }"
        />
      </div>

      <!-- Summary badges -->
      <div class="flex items-center gap-3 mt-3">
        <span
          v-if="summaryCounts.ok"
          class="badge-ok text-xs font-medium px-2 py-0.5 rounded-full"
        >
          {{ summaryCounts.ok }} OK
        </span>
        <span
          v-if="summaryCounts.warn"
          class="badge-warn text-xs font-medium px-2 py-0.5 rounded-full"
        >
          {{ summaryCounts.warn }} {{ severityLabels.warn }}
        </span>
        <span
          v-if="summaryCounts.fail"
          class="badge-fail text-xs font-medium px-2 py-0.5 rounded-full"
        >
          {{ summaryCounts.fail }} {{ severityLabels.fail }}
        </span>
        <span
          v-if="summaryCounts.info"
          class="badge-info text-xs font-medium px-2 py-0.5 rounded-full"
        >
          {{ summaryCounts.info }} {{ severityLabels.info }}
        </span>
      </div>
    </div>

    <!-- Items list -->
    <div class="divide-y divide-carbon-100">
      <div
        v-for="(item, idx) in report.items"
        :key="idx"
        class="px-6 py-3 transition-colors"
        :class="{ 'bg-canvas-dark': expandedItems.has(idx) }"
      >
        <button
          class="w-full flex items-center gap-3 text-left"
          :class="{ 'cursor-pointer': item.details }"
          :disabled="!item.details"
          @click="item.details && toggleItem(idx)"
        >
          <!-- Severity icon -->
          <svg
            class="w-5 h-5 flex-shrink-0"
            :class="{
              'text-status-ok': item.severity === 'ok',
              'text-status-warn': item.severity === 'warn',
              'text-status-fail': item.severity === 'fail',
              'text-status-info': item.severity === 'info',
            }"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            stroke-width="1.5"
          >
            <path stroke-linecap="round" stroke-linejoin="round" :d="severityIcons[item.severity]" />
          </svg>

          <!-- Label -->
          <span class="flex-1 text-sm text-carbon-700">{{ item.label }}</span>

          <!-- Severity badge -->
          <span
            class="text-[0.625rem] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full"
            :class="`badge-${item.severity}`"
          >
            {{ severityLabels[item.severity] }}
          </span>

          <!-- Expand chevron -->
          <svg
            v-if="item.details"
            class="w-4 h-4 text-carbon-400 transition-transform duration-200"
            :class="{ 'rotate-180': expandedItems.has(idx) }"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
            stroke-width="2"
          >
            <path stroke-linecap="round" stroke-linejoin="round" d="M19 9l-7 7-7-7" />
          </svg>
        </button>

        <!-- Expanded details -->
        <Transition name="expand">
          <div
            v-if="item.details && expandedItems.has(idx)"
            class="mt-2 ml-8 text-xs text-carbon-500 bg-canvas rounded-lg p-3 border border-carbon-100 font-mono leading-relaxed whitespace-pre-wrap"
          >
            {{ item.details }}
          </div>
        </Transition>
      </div>
    </div>
  </div>
</template>

<style scoped>
.expand-enter-active {
  transition: max-height 0.25s ease, opacity 0.2s ease;
  max-height: 300px;
  overflow: hidden;
}
.expand-leave-active {
  transition: max-height 0.2s ease, opacity 0.15s ease;
  max-height: 300px;
  overflow: hidden;
}
.expand-enter-from,
.expand-leave-to {
  max-height: 0;
  opacity: 0;
}
</style>
