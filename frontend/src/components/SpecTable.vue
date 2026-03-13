<script setup>
import { ref, computed, toRef } from 'vue'
import { usePagination } from '@/composables/usePagination'

/**
 * @typedef {Object} TableColumn
 * @property {string} key - Column data key
 * @property {string} label - Column header label
 * @property {boolean} [sortable] - Whether column is sortable
 * @property {string} [align] - Text alignment: 'left' | 'center' | 'right'
 */

const props = defineProps({
  /** @type {TableColumn[]} */
  columns: { type: Array, required: true },
  /** @type {Record<string, any>[]} */
  rows: { type: Array, required: true },
  /** Enable sorting on sortable columns */
  sortable: { type: Boolean, default: true },
  /** Rows per page (0 = no pagination) */
  perPage: { type: Number, default: 20 },
})

const emit = defineEmits(['sort'])

/** Current sort state */
const sortKey = ref(null)
const sortDir = ref('asc')

/** Sort rows if sortable */
const sortedRows = computed(() => {
  if (!props.sortable || !sortKey.value) return props.rows

  return [...props.rows].sort((a, b) => {
    const va = a[sortKey.value]
    const vb = b[sortKey.value]

    // Numeric comparison
    if (typeof va === 'number' && typeof vb === 'number') {
      return sortDir.value === 'asc' ? va - vb : vb - va
    }

    // String comparison
    const sa = String(va ?? '').toLowerCase()
    const sb = String(vb ?? '').toLowerCase()
    const cmp = sa.localeCompare(sb, 'ru')
    return sortDir.value === 'asc' ? cmp : -cmp
  })
})

/** Pagination */
const sortedRowsRef = computed(() => sortedRows.value)
const { currentPage, totalPages, paginatedItems, goToPage, nextPage, prevPage } = usePagination(
  sortedRowsRef,
  props.perPage || 999999,
)

/** Displayed rows: paginated if perPage > 0, otherwise all */
const displayedRows = computed(() => {
  if (props.perPage > 0) return paginatedItems.value
  return sortedRows.value
})

/** Handle column header click */
function onSort(col) {
  if (!props.sortable || col.sortable === false) return

  if (sortKey.value === col.key) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortKey.value = col.key
    sortDir.value = 'asc'
  }
  emit('sort', sortKey.value, sortDir.value)
}

/** Column alignment class */
function alignClass(col) {
  if (col.align === 'center') return 'text-center'
  if (col.align === 'right') return 'text-right'
  return 'text-left'
}

/** Generate page numbers for pagination */
const pageNumbers = computed(() => {
  const total = totalPages.value
  const current = currentPage.value
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)

  const pages = []
  pages.push(1)
  if (current > 3) pages.push('...')
  for (let i = Math.max(2, current - 1); i <= Math.min(total - 1, current + 1); i++) {
    pages.push(i)
  }
  if (current < total - 2) pages.push('...')
  pages.push(total)
  return pages
})
</script>

<template>
  <div class="overflow-hidden rounded-xl border border-carbon-200 bg-white">
    <!-- Table -->
    <div class="overflow-x-auto">
      <table class="spec-table w-full">
        <thead>
          <tr class="bg-canvas-dark">
            <th
              v-for="col in columns"
              :key="col.key"
              :class="[
                alignClass(col),
                { 'cursor-pointer select-none hover:text-carbon-700': sortable && col.sortable !== false }
              ]"
              @click="onSort(col)"
            >
              <span class="inline-flex items-center gap-1.5">
                {{ col.label }}
                <!-- Sort indicator -->
                <template v-if="sortable && col.sortable !== false">
                  <svg
                    v-if="sortKey === col.key"
                    class="w-3 h-3 text-sage transition-transform"
                    :class="{ 'rotate-180': sortDir === 'desc' }"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    stroke-width="2.5"
                  >
                    <path stroke-linecap="round" stroke-linejoin="round" d="M4.5 15.75l7.5-7.5 7.5 7.5" />
                  </svg>
                  <svg
                    v-else
                    class="w-3 h-3 text-carbon-300"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    stroke-width="2"
                  >
                    <path stroke-linecap="round" stroke-linejoin="round" d="M8.25 15L12 18.75 15.75 15m-7.5-6L12 5.25 15.75 9" />
                  </svg>
                </template>
              </span>
            </th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="(row, idx) in displayedRows"
            :key="idx"
          >
            <td
              v-for="col in columns"
              :key="col.key"
              :class="alignClass(col)"
            >
              <!-- Slot for custom cell rendering -->
              <slot :name="`cell-${col.key}`" :row="row" :value="row[col.key]">
                {{ row[col.key] ?? '—' }}
              </slot>
            </td>
          </tr>

          <!-- Empty state -->
          <tr v-if="!displayedRows.length">
            <td :colspan="columns.length" class="text-center py-8 text-carbon-400 text-sm">
              Нет данных
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Pagination -->
    <div
      v-if="perPage > 0 && totalPages > 1"
      class="flex items-center justify-between px-4 py-3 border-t border-carbon-100 bg-canvas"
    >
      <p class="text-xs text-carbon-400">
        Стр. {{ currentPage }} из {{ totalPages }}
        <span class="ml-1">({{ sortedRows.length }} записей)</span>
      </p>
      <div class="flex items-center gap-1">
        <!-- Prev -->
        <button
          class="px-2 py-1 rounded text-xs font-medium transition-colors"
          :class="currentPage > 1 ? 'text-carbon-600 hover:bg-carbon-100' : 'text-carbon-300 cursor-not-allowed'"
          :disabled="currentPage <= 1"
          @click="prevPage"
        >
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M15.75 19.5L8.25 12l7.5-7.5" />
          </svg>
        </button>

        <!-- Page numbers -->
        <template v-for="(p, idx) in pageNumbers" :key="idx">
          <span v-if="p === '...'" class="px-1 text-xs text-carbon-400">...</span>
          <button
            v-else
            class="w-7 h-7 rounded text-xs font-medium transition-colors"
            :class="p === currentPage
              ? 'bg-sage text-white'
              : 'text-carbon-600 hover:bg-carbon-100'"
            @click="goToPage(p)"
          >
            {{ p }}
          </button>
        </template>

        <!-- Next -->
        <button
          class="px-2 py-1 rounded text-xs font-medium transition-colors"
          :class="currentPage < totalPages ? 'text-carbon-600 hover:bg-carbon-100' : 'text-carbon-300 cursor-not-allowed'"
          :disabled="currentPage >= totalPages"
          @click="nextPage"
        >
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
            <path stroke-linecap="round" stroke-linejoin="round" d="M8.25 4.5l7.5 7.5-7.5 7.5" />
          </svg>
        </button>
      </div>
    </div>
  </div>
</template>
