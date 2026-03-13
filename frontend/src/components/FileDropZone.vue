<script setup>
import { ref } from 'vue'

/** @type {{ accept?: string, multiple?: boolean, label?: string }} */
const props = defineProps({
  /** MIME types or extensions to accept (e.g. ".pdf,.xlsx") */
  accept: { type: String, default: '' },
  /** Allow multiple file selection */
  multiple: { type: Boolean, default: false },
  /** Label text for the drop zone */
  label: { type: String, default: 'Перетащите файл сюда или нажмите для выбора' },
})

const emit = defineEmits(['files'])

const isDragging = ref(false)
const selectedFiles = ref([])
const fileInput = ref(null)

/** Handle file selection from input or drop */
function handleFiles(fileList) {
  const files = Array.from(fileList)
  if (!files.length) return
  selectedFiles.value = files
  emit('files', files)
}

function onDragEnter(e) {
  e.preventDefault()
  isDragging.value = true
}

function onDragOver(e) {
  e.preventDefault()
  isDragging.value = true
}

function onDragLeave(e) {
  e.preventDefault()
  // Only deactivate if leaving the drop zone (not entering a child)
  if (!e.currentTarget.contains(e.relatedTarget)) {
    isDragging.value = false
  }
}

function onDrop(e) {
  e.preventDefault()
  isDragging.value = false
  if (e.dataTransfer?.files) {
    handleFiles(e.dataTransfer.files)
  }
}

function onInputChange(e) {
  if (e.target.files) {
    handleFiles(e.target.files)
  }
}

function openFilePicker() {
  fileInput.value?.click()
}

/** Format file size for display */
function formatSize(bytes) {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}
</script>

<template>
  <div
    class="drop-zone cursor-pointer"
    :class="{ active: isDragging }"
    @dragenter="onDragEnter"
    @dragover="onDragOver"
    @dragleave="onDragLeave"
    @drop="onDrop"
    @click="openFilePicker"
    role="button"
    tabindex="0"
    @keydown.enter.space.prevent="openFilePicker"
  >
    <input
      ref="fileInput"
      type="file"
      class="hidden"
      :accept="accept"
      :multiple="multiple"
      @change="onInputChange"
    />

    <!-- Empty state -->
    <div v-if="!selectedFiles.length" class="flex flex-col items-center gap-3 py-4">
      <div class="w-12 h-12 rounded-xl bg-carbon-100 flex items-center justify-center">
        <svg class="w-6 h-6 text-carbon-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
        </svg>
      </div>
      <div class="text-center">
        <p class="text-sm text-carbon-600 font-medium">{{ label }}</p>
        <p v-if="accept" class="text-xs text-carbon-400 mt-1">
          Форматы: {{ accept }}
        </p>
      </div>
    </div>

    <!-- Files selected -->
    <div v-else class="flex flex-col items-center gap-3 py-2">
      <div class="w-10 h-10 rounded-xl bg-sage/10 flex items-center justify-center">
        <svg class="w-5 h-5 text-sage" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </div>
      <div class="text-center space-y-1">
        <p
          v-for="(file, idx) in selectedFiles"
          :key="idx"
          class="text-sm text-carbon-700 font-medium"
        >
          {{ file.name }}
          <span class="text-carbon-400 font-normal text-xs ml-1">
            ({{ formatSize(file.size) }})
          </span>
        </p>
      </div>
      <p class="text-xs text-carbon-400">Нажмите, чтобы заменить</p>
    </div>
  </div>
</template>
