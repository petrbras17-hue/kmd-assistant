import { ref, computed } from 'vue'

export function usePagination(items, perPage = 20) {
  const currentPage = ref(1)

  const totalPages = computed(() => Math.ceil(items.value.length / perPage))
  const paginatedItems = computed(() => {
    const start = (currentPage.value - 1) * perPage
    return items.value.slice(start, start + perPage)
  })

  function goToPage(page) {
    if (page >= 1 && page <= totalPages.value) currentPage.value = page
  }
  function nextPage() { goToPage(currentPage.value + 1) }
  function prevPage() { goToPage(currentPage.value - 1) }

  return { currentPage, totalPages, paginatedItems, goToPage, nextPage, prevPage }
}
