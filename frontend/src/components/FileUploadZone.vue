<script setup>
import { ref, computed } from "vue"

/**
 * FileUploadZone Component
 * Drag-drop file input with visual feedback and file list display
 * Props: accept (string), multiple (bool), maxSize (number)
 * Emits: files, error
 */

const props = defineProps({
  accept: { type: String, default: "" },
  multiple: { type: Boolean, default: true },
  maxSize: { type: Number, default: 100 },
})

const emit = defineEmits(["files", "error"])

const isDragging = ref(false)
const selectedFiles = ref([])
const fileInput = ref(null)
const errorMessage = ref("")

const totalSize = computed(() => {
  return selectedFiles.value.reduce((sum, file) => sum + file.size, 0)
})

const totalSizeFormatted = computed(() => formatSize(totalSize.value))

function handleFiles(fileList) {
  errorMessage.value = ""
  const files = Array.from(fileList)
  if (!files.length) return
  
  const validFiles = files.filter(file => {
    if (file.size > props.maxSize * 1024 * 1024) {
      errorMessage.value = `File ${file.name} exceeds max size of ${props.maxSize}MB`
      emit("error", errorMessage.value)
      return false
    }
    return true
  })
  
  if (validFiles.length > 0) {
    selectedFiles.value = props.multiple ? [...selectedFiles.value, ...validFiles] : validFiles
    emit("files", selectedFiles.value)
  }
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

function formatSize(bytes) {
  if (bytes < 1024) return bytes + " B"
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB"
  return (bytes / (1024 * 1024)).toFixed(1) + " MB"
}

function clearFiles() {
  selectedFiles.value = []
  errorMessage.value = ""
  if (fileInput.value) fileInput.value.value = ""
}

function removeFile(idx) {
  selectedFiles.value.splice(idx, 1)
  emit("files", selectedFiles.value)
}
</script>

<template>
  <div
    class="border-2 border-dashed border-carbon-300 rounded-xl p-6 transition-all duration-200 cursor-pointer"
    :class="[isDragging ? \"border-sage bg-sage/5 scale-[1.02]\" : \"hover:border-carbon-400 hover:bg-carbon-50\"]"
    @dragenter="onDragEnter" @dragover="onDragOver" @dragleave="onDragLeave" @drop="onDrop"
    @click="openFilePicker" role="button" tabindex="0" @keydown.enter.space.prevent="openFilePicker"
  >
    <input ref="fileInput" type="file" class="hidden" :accept="accept" :multiple="multiple" @change="onInputChange" />

    <div v-if="!selectedFiles.length" class="flex flex-col items-center gap-3">
      <div class="w-14 h-14 rounded-xl bg-carbon-100 flex items-center justify-center">
        <svg class="w-7 h-7 text-carbon-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
          <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
        </svg>
      </div>
      <div class="text-center">
        <p class="text-sm font-medium text-carbon-700">Drag files here or click to upload</p>
        <p v-if="accept" class="text-xs text-carbon-500 mt-1">Supported: {{ accept }}</p>
        <p class="text-xs text-carbon-400 mt-1">Max: {{ maxSize }}MB per file</p>
      </div>
    </div>

    <div v-else class="space-y-3">
      <div class="flex items-start justify-between gap-3">
        <div class="flex items-center gap-3 flex-1">
          <div class="w-12 h-12 rounded-xl bg-sage/10 flex items-center justify-center flex-shrink-0">
            <svg class="w-6 h-6 text-sage" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
              <path stroke-linecap="round" stroke-linejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <div class="flex-1 min-w-0">
            <p class="text-sm font-medium text-carbon-700">{{ selectedFiles.length }} file{{ selectedFiles.length !== 1 ? \"s\" : \"\" }} selected</p>
            <p class="text-xs text-carbon-500">Total: {{ totalSizeFormatted }}</p>
          </div>
        </div>
        <button @click.stop="clearFiles" class="text-xs text-sage hover:text-sage-dark transition-colors px-2 py-1">Clear All</button>
      </div>

      <div v-if="errorMessage" class="p-2 bg-red-50 border border-red-200 rounded-lg text-xs text-red-700">{{ errorMessage }}</div>

      <div class="bg-carbon-50 rounded-lg p-3 space-y-2 max-h-48 overflow-y-auto">
        <div v-for="(file, idx) in selectedFiles" :key="idx" class="flex items-center gap-2 text-xs">
          <svg class="w-3.5 h-3.5 text-carbon-400 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5">
            <path stroke-linecap="round" stroke-linejoin="round" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5" />
          </svg>
          <span class="text-carbon-700 font-medium truncate flex-1">{{ file.name }}</span>
          <span class="text-carbon-500">{{ formatSize(file.size) }}</span>
          <button @click.stop="removeFile(idx)" class="text-carbon-400 hover:text-red-600 transition-colors">x</button>
        </div>
      </div>
    </div>
  </div>
</template>
