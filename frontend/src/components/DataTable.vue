<script setup>
import { ref, computed } from "vue"

/**
 * DataTable Component
 * Sortable columns, pagination, responsive horizontal scroll
 * Props: rows (array), columns (array), sortable (bool), perPage (number)
 * Features: Column sorting, pagination, CSV export
 */

const props = defineProps({
  rows: { type: Array, required: true },
  columns: { type: Array, required: true },
  sortable: { type: Boolean, default: true },
  perPage: { type: Number, default: 10 },
})

const emit = defineEmits(["sort", "row-click"])

const sortKey = ref(null)
const sortDir = ref("asc")
const currentPage = ref(1)

const sortedRows = computed(() => {
  if (!props.sortable || !sortKey.value) return props.rows
  return [...props.rows].sort((a, b) => {
    const va = a[sortKey.value]
    const vb = b[sortKey.value]
    if (typeof va === "number" && typeof vb === "number") {
      return sortDir.value === "asc" ? va - vb : vb - va
    }
    const cmp = String(va || "").localeCompare(String(vb || ""))
    return sortDir.value === "asc" ? cmp : -cmp
  })
})

const totalPages = computed(() => Math.ceil(sortedRows.value.length / props.perPage))

const displayedRows = computed(() => {
  const start = (currentPage.value - 1) * props.perPage
  return sortedRows.value.slice(start, start + props.perPage)
})

const hasData = computed(() => props.rows && props.rows.length > 0)

function onSort(col) {
  if (!props.sortable || col.sortable === false) return
  if (sortKey.value === col.key) {
    sortDir.value = sortDir.value === "asc" ? "desc" : "asc"
  } else {
    sortKey.value = col.key
    sortDir.value = "asc"
  }
  emit("sort", sortKey.value, sortDir.value)
}

function exportCSV() {
  const headers = props.columns.map(c => c.label).join(",")
  const rows = sortedRows.value.map(row =>
    props.columns.map(c => {
      const val = row[c.key] || ""
      return typeof val === "string" && val.includes(",") ? "\"" + val + "\"" : val
    }).join(",")
  )
  const csv = [headers, ...rows].join("\n")
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" })
  const url = URL.createObjectURL(blob)
  const link = document.createElement("a")
  link.href = url
  link.download = "data.csv"
  link.click()
  URL.revokeObjectURL(url)
}

function nextPage() {
  if (currentPage.value < totalPages.value) currentPage.value += 1
}

function prevPage() {
  if (currentPage.value > 1) currentPage.value -= 1
}

function goToPage(page) {
  if (page > 0 && page <= totalPages.value) currentPage.value = page
}

function onRowClick(row) {
  emit("row-click", row)
}
</script>

<template>
  <div class="rounded-xl border border-carbon-200 bg-white overflow-hidden">
    <!-- Header actions -->
    <div class="border-b border-carbon-100 px-6 py-4 flex justify-end gap-2 bg-canvas">
      <button
        @click="exportCSV"
        :disabled="!hasData"
        class="px-4 py-2 text-sm rounded-lg bg-sage/10 text-sage hover:bg-sage/20 disabled:opacity-50 disabled:cursor-not-allowed font-medium transition-colors"
      >
        Export CSV
      </button>
    </div>

    <!-- Table -->
    <div class="overflow-x-auto">
      <table class="w-full text-sm">
        <thead>
          <tr class="bg-canvas border-b border-carbon-100">
            <th v-for="col in columns" :key="col.key" class="px-6 py-4 text-left font-semibold text-carbon-700" :class="{ \"cursor-pointer select-none hover:text-carbon-900\": sortable && col.sortable !== false }" @click="onSort(col)">
              <span class="inline-flex items-center gap-2">
                {{ col.label }}
                <svg v-if="sortKey === col.key" class="w-4 h-4 text-sage transition-transform" :class="{ \"rotate-180\": sortDir === \"desc\" }" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2.5">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 15.75l7.5-7.5 7.5 7.5" />
                </svg>
              </span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in displayedRows" :key="row.id" class="border-b border-carbon-100 hover:bg-canvas transition-colors cursor-pointer" @click="onRowClick(row)">
            <td v-for="col in columns" :key="col.key" class="px-6 py-4 text-carbon-700">
              <slot :name="\"cell-\" + col.key" :row="row" :value="row[col.key]">
                {{ row[col.key] }}
              </slot>
            </td>
          </tr>
          <tr v-if="!displayedRows.length">
            <td :colspan="columns.length" class="px-6 py-12 text-center text-carbon-400 text-sm">
              No data available
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div v-if="totalPages > 1" class="flex items-center justify-between px-6 py-4 border-t border-carbon-100 bg-canvas text-sm">
      <p class="text-carbon-600">Page {{ currentPage }} of {{ totalPages }} ({{ sortedRows.length }} total)</p>
      <div class="flex gap-1">
        <button @click="prevPage" :disabled="currentPage === 1" class="px-3 py-2 rounded text-xs font-medium bg-carbon-100 text-carbon-600 hover:bg-carbon-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">Prev</button>
        <button @click="nextPage" :disabled="currentPage === totalPages" class="px-3 py-2 rounded text-xs font-medium bg-carbon-100 text-carbon-600 hover:bg-carbon-200 disabled:opacity-50 disabled:cursor-not-allowed transition-colors">Next</button>
      </div>
    </div>
  </div>
</template>
