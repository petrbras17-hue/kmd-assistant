<script setup>
import { ref, computed } from "vue"

/**
 * FormInputGroup Component
 * Input with label, optional unit selector, and inline validation feedback
 * Props: label, type, modelValue, unit, units, placeholder, error, hint
 * Emits: update:modelValue, update:unit
 */

const props = defineProps({
  label: { type: String, required: true },
  type: { type: String, default: "text" },
  modelValue: { type: [String, Number], default: "" },
  unit: { type: String, default: "" },
  units: { type: Array, default: () => [] },
  placeholder: { type: String, default: "" },
  error: { type: String, default: "" },
  hint: { type: String, default: "" },
  disabled: { type: Boolean, default: false },
})

const emit = defineEmits(["update:modelValue", "update:unit"])

const selectedUnit = ref(props.unit)
const isFocused = ref(false)

const hasError = computed(() => Boolean(props.error))

const allUnits = computed(() => {
  if (props.units.length > 0) return props.units
  if (props.unit) return [props.unit]
  return []
})

function updateValue(e) {
  emit("update:modelValue", e.target.value)
}

function updateUnit(e) {
  selectedUnit.value = e.target.value
  emit("update:unit", selectedUnit.value)
}

function onFocus() {
  isFocused.value = true
}

function onBlur() {
  isFocused.value = false
}
</script>

<template>
  <div class="space-y-2">
    <div class="flex items-center justify-between">
      <label class="block text-sm font-semibold text-carbon-900">
        {{ label }}
      </label>
      <span v-if="error" class="text-xs text-red-600 font-medium">Error</span>
    </div>

    <div class="flex gap-2 items-stretch">
      <div class="flex-1 relative">
        <input
          :type="type"
          :value="modelValue"
          :placeholder="placeholder"
          :disabled="disabled"
          :class="[
            \"w-full px-3 py-2.5 rounded-lg border-2 transition-all focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed\",
            hasError
              ? \"border-red-300 bg-red-50 text-red-900 placeholder-red-300\"
              : isFocused
              ? \"border-sage bg-white text-carbon-900 shadow-sm\"
              : \"border-carbon-300 bg-white text-carbon-900 hover:border-carbon-400\"
          ]\"
          @input="updateValue"
          @focus="onFocus"
          @blur="onBlur"
        />
      </div>

      <select
        v-if="allUnits.length > 0"
        :value="selectedUnit"
        :disabled="disabled"
        :class="[
          \"px-3 py-2.5 rounded-lg border-2 border-carbon-300 bg-white text-carbon-700 text-sm font-semibold hover:border-carbon-400 transition-colors focus:outline-none focus:border-sage focus:ring-2 focus:ring-sage/20 disabled:opacity-50 disabled:cursor-not-allowed\",
        ]\"
        @change="updateUnit"
      >
        <option v-for="u in allUnits" :key="u" :value="u">{{ u }}</option>
      </select>
    </div>

    <div v-if="error || hint" class="flex gap-2">
      <p v-if="error" class="text-xs text-red-600 font-medium">{{ error }}</p>
      <p v-else-if="hint" class="text-xs text-carbon-500 italic">{{ hint }}</p>
    </div>
  </div>
</template>
