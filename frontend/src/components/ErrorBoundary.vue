<script setup>
import { ref } from "vue"

/**
 * ErrorBoundary Component
 * Wraps modules for error catching with graceful error display and retry
 * Integration with Sentry if available
 */

const props = defineProps({
  name: { type: String, default: "Component" },
})

const emit = defineEmits(["error", "retry"])

const hasError = ref(false)
const error = ref(null)
const errorCount = ref(0)
const lastErrorTime = ref(null)

function handleError(err) {
  hasError.value = true
  error.value = err.message || "An unexpected error occurred"
  errorCount.value += 1
  lastErrorTime.value = new Date().toLocaleString()
  
  console.error("Error in " + props.name + ":", err)
  
  if (window.Sentry && window.Sentry.captureException) {
    window.Sentry.captureException(err, {
      tags: {
        component: props.name,
        errorCount: errorCount.value,
      }
    })
  }
  
  emit("error", {
    message: error.value,
    component: props.name,
    count: errorCount.value,
    timestamp: lastErrorTime.value,
  })
}

function retry() {
  hasError.value = false
  error.value = null
  emit("retry")
}

function clearError() {
  hasError.value = false
  error.value = null
}

function reportError() {
  if (window.Sentry && window.Sentry.showReportDialog) {
    window.Sentry.showReportDialog({
      title: "Report Error",
      subtitle: "Help us improve by reporting this issue",
    })
  }
}
</script>

<template>
  <div>
    <Transition name="error-slide">
      <div v-if="hasError" class="rounded-lg border-2 border-red-200 bg-red-50 p-6 mb-4">
        <div class="flex items-start gap-4">
          <div class="w-10 h-10 rounded-lg bg-red-100 flex items-center justify-center flex-shrink-0">
            <svg class="w-6 h-6 text-red-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4m0 4v.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div class="flex-1">
            <h4 class="font-bold text-red-900 mb-1">Error in {{ name }}</h4>
            <p class="text-sm text-red-800 mb-3">{{ error }}</p>
            <p class="text-xs text-red-700 mb-3">Occurrences: {{ errorCount }} at {{ lastErrorTime }}</p>
            
            <div class="flex flex-wrap gap-2">
              <button
                @click="retry"
                class="px-4 py-2 text-sm rounded-lg bg-red-200 text-red-900 hover:bg-red-300 transition-colors font-semibold"
              >
                Retry
              </button>
              <button
                @click="clearError"
                class="px-4 py-2 text-sm rounded-lg bg-red-100 text-red-800 hover:bg-red-200 transition-colors font-medium"
              >
                Dismiss
              </button>
              <button
                v-if="window.Sentry"
                @click="reportError"
                class="px-4 py-2 text-sm rounded-lg bg-red-100 text-red-800 hover:bg-red-200 transition-colors font-medium"
              >
                Report
              </button>
            </div>
          </div>
          <button @click="clearError" class="text-red-400 hover:text-red-600 transition-colors">
            <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
              <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>
    </Transition>

    <div v-if="!hasError">
      <ErrorBoundary :name="name" @error="handleError">
        <slot />
      </ErrorBoundary>
    </div>
  </div>
</template>

<style scoped>
.error-slide-enter-active, .error-slide-leave-active {
  transition: all 0.3s ease;
}
.error-slide-enter-from, .error-slide-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
