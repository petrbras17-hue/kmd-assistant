<script setup>
/**
 * LayoutShell Component
 * Simple wrapper with max-width, padding, responsive design
 * Provides consistent spacing and centering for page content
 * Usage: Wrap main page content with responsive layout constraints
 * Props: none - uses slots only
 * Slots: default (main content area)
 */

defineProps({
  maxWidth: { type: String, default: "7xl" },
})
</script>

<template>
  <div class="min-h-screen bg-canvas">
    <div :class="[\max-w-\` + maxWidth, \"mx-auto px-4 sm:px-6 lg:px-8 py-6 sm:py-8 lg:py-10\"]">
      <slot />
    </div>
  </div>
</template>

<style scoped>
.max-w-7xl {
  max-width: 80rem;
}

.max-w-6xl {
  max-width: 72rem;
}

.max-w-5xl {
  max-width: 64rem;
}

.max-w-4xl {
  max-width: 56rem;
}

@media (max-width: 640px) {
  div {
    padding: 1rem 0;
  }
}

@media (min-width: 641px) {
  div {
    padding: 2rem 0;
  }
}

@media (min-width: 1024px) {
  div {
    padding: 2.5rem 0;
  }
}
</style>
