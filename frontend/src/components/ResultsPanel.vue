<script setup>
import { ref, computed } from "vue"

const props = defineProps({
  data: { type: Object, required: true },
  tabNames: { type: Array, default: () => [] },
})

const activeTab = ref(0)
const expandedItems = ref(new Set())

const summary = computed(() => {
  if (!props.data || !props.data.results) return { total: 0, success: 0, errors: 0, warnings: 0 }
  const results = props.data.results
  return {
    total: results.length || 0,
    success: (results.filter(r => r.status === "ok") || []).length,
    errors: (results.filter(r => r.status === "error") || []).length,
    warnings: (results.filter(r => r.status === "warn") || []).length,
  }
})

const displayPercentage = computed(() => {
  if (summary.value.total === 0) return 0
  return Math.round((summary.value.success / summary.value.total) * 100)
})

function exportCSV() {
  if (!props.data || !props.data.results) return
  const headers = ["Label", "Status", "Value", "Details"]
  const rows = props.data.results.map(r => [r.label || "", r.status || "", r.value || "", r.details || ""])
  const csv = [headers.join(","), ...rows.map(row => row.map(cell => "\"" + cell + "\"").join(","))].join("\n")
  const blob = new Blob([csv], { type: "text/csv" })
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = "results.csv"
  link.click()
  URL.revokeObjectURL(url)
}

function getStatusColor(status) {
  const colors = { ok: "bg-emerald-100 text-emerald-700", error: "bg-red-100 text-red-700", warn: "bg-amber-100 text-amber-700" }
  return colors[status] || "bg-gray-100 text-gray-700"
}

function toggleExpanded(idx) {
  if (expandedItems.value.has(idx)) {
    expandedItems.value.delete(idx)
  } else {
    expandedItems.value.add(idx)
  }
}

function isExpanded(idx) {
  return expandedItems.value.has(idx)
}
</script>

<template>
  <div class="rounded-xl border border-carbon-200 bg-white overflow-hidden">
    <div class="border-b border-carbon-100 bg-canvas px-6 py-4">
      <div class="flex items-center justify-between mb-4">
        <h3 class="font-semibold text-carbon-900 text-lg">Results Analysis</h3>
        <button @click="exportCSV" class="px-4 py-2 rounded-lg text-sm font-medium bg-sage/10 text-sage hover:bg-sage/20">Export CSV</button>
      </div>

      <div class="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
        <div class="p-3 bg-white rounded-lg border border-carbon-100">
          <p class="text-xs text-carbon-500 mb-1">Total Results</p>
          <p class="text-2xl font-bold text-carbon-900">{{ summary.total }}</p>
        </div>
        <div class="p-3 bg-white rounded-lg border border-carbon-100">
          <p class="text-xs text-carbon-500 mb-1">Successful</p>
          <p class="text-2xl font-bold text-emerald-600">{{ summary.success }}</p>
        </div>
        <div class="p-3 bg-white rounded-lg border border-carbon-100">
          <p class="text-xs text-carbon-500 mb-1">Errors</p>
          <p class="text-2xl font-bold text-red-600">{{ summary.errors }}</p>
        </div>
        <div class="p-3 bg-white rounded-lg border border-carbon-100">
          <p class="text-xs text-carbon-500 mb-1">Warnings</p>
          <p class="text-2xl font-bold text-amber-600">{{ summary.warnings }}</p>
        </div>
      </div>

      <div v-if="summary.total > 0" class="space-y-2 mb-4">
        <div class="flex justify-between">
          <span class="text-xs text-carbon-600 font-medium">Success Rate</span>
          <span class="text-sm font-mono text-sage font-bold">{{ displayPercentage }}done</span>
        </div>
        <div class="w-full h-2.5 bg-carbon-100 rounded-full overflow-hidden">
          <div class="h-full bg-sage transition-all" :style="{ width: displayPercentage + done }"></div>
        </div>
      </div>

      <div v-if="tabNames.length > 1" class="flex border-t border-carbon-100 mt-4 overflow-x-auto">
        <button v-for="(tab, idx) in tabNames" :key="idx" @click="activeTab = idx" class="px-4 py-3 text-sm font-medium whitespace-nowrap transition-colors border-b-2" :class="[activeTab === idx ? \"border-sage text-sage\" : \"border-transparent text-carbon-500 hover:text-carbon-700\"]">
          {{ tab }}
        </button>
      </div>
    </div>

    <div class="px-6 py-4">
      <div v-if="data.results && data.results.length" class="space-y-2 max-h-96 overflow-y-auto">
        <div v-for="(item, idx) in data.results" :key="idx" class="p-3 rounded-lg border border-carbon-100 hover:bg-canvas transition-colors">
          <div class="flex items-start justify-between gap-3 cursor-pointer" @click="toggleExpanded(idx)">
            <div class="flex-1">
              <p class="text-sm font-medium text-carbon-700">{{ item.label }}</p>
              <p v-if="item.details && !isExpanded(idx)" class="text-xs text-carbon-500 truncate">{{ item.details }}</p>
              <p v-if="item.details && isExpanded(idx)" class="text-xs text-carbon-600 mt-2">{{ item.details }}</p>
            </div>
            <span :class="[getStatusColor(item.status), \"px-2 py-1 rounded text-xs font-bold\"]">{{ item.status }}</span>
          </div>
        </div>
      </div>
      <div v-else class="text-center py-8 text-carbon-400 text-sm">
        No results to display
      </div>
    </div>
  </div>
</template>
