<script setup>
import { reactive, ref } from 'vue'
import { useAppStore } from '@/stores/app'

const store = useAppStore()

const form = reactive({
  width: 1500,
  height: 2000,
  depth: 70,
  divisions_x: 2,
  divisions_y: 3,
  color: '#555555',
  glass_color: '#88BBDD',
})
const showPreview = ref(false)

function generate() {
  showPreview.value = true
}
</script>

<template>
  <div class="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
    <header class="mb-10 animate-fade-up">
      <span class="text-xs font-mono tracking-[0.2em] uppercase text-sage mb-2 block">3D и оптимизация</span>
      <h1 class="font-display text-3xl sm:text-4xl text-carbon-900 mb-3">3D Просмотр</h1>
      <p class="text-carbon-500 font-body">{{ store.cardDescriptions.preview3d }}</p>
    </header>

    <section class="bg-white rounded-2xl border border-carbon-200/60 p-8 mb-8 animate-fade-up" style="animation-delay:80ms">
      <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-5 mb-6">
        <div v-for="field in [
          { key: 'width', label: 'Ширина, мм' },
          { key: 'height', label: 'Высота, мм' },
          { key: 'depth', label: 'Глубина, мм' },
          { key: 'divisions_x', label: 'Делений X' },
          { key: 'divisions_y', label: 'Делений Y' },
        ]" :key="field.key">
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">{{ field.label }}</label>
          <input v-model.number="form[field.key]" type="number" min="1"
                 class="w-full px-3 py-2.5 bg-canvas border border-carbon-200/60 rounded-lg text-sm
                        text-carbon-700 font-mono focus:outline-none focus:border-sage/50 focus:ring-1
                        focus:ring-sage/20 transition-colors" />
        </div>
        <div>
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">Цвет профиля</label>
          <input v-model="form.color" type="color"
                 class="w-full h-[42px] bg-canvas border border-carbon-200/60 rounded-lg cursor-pointer" />
        </div>
        <div>
          <label class="block text-xs font-medium text-carbon-500 mb-1.5">Цвет стекла</label>
          <input v-model="form.glass_color" type="color"
                 class="w-full h-[42px] bg-canvas border border-carbon-200/60 rounded-lg cursor-pointer" />
        </div>
      </div>

      <button @click="generate"
              class="px-6 py-3 bg-sage text-white text-sm font-medium rounded-xl
                     hover:bg-sage-dark transition-colors">
        Сгенерировать превью
      </button>
    </section>

    <!-- Simple CSS 3D preview -->
    <section v-if="showPreview" class="bg-white rounded-2xl border border-carbon-200/60 p-8 animate-scale-in">
      <h2 class="font-display text-xl text-carbon-800 mb-6">Превью конструкции</h2>

      <div class="flex justify-center" style="perspective:800px">
        <div class="relative" style="transform:rotateY(-15deg) rotateX(5deg)"
             :style="{
               width: `${Math.min(form.width / 5, 400)}px`,
               height: `${Math.min(form.height / 5, 500)}px`,
             }">
          <!-- Frame -->
          <div class="absolute inset-0 rounded border-4"
               :style="{ borderColor: form.color }">
            <!-- Grid -->
            <div class="w-full h-full grid"
                 :style="{
                   gridTemplateColumns: `repeat(${form.divisions_x}, 1fr)`,
                   gridTemplateRows: `repeat(${form.divisions_y}, 1fr)`,
                   gap: '3px',
                   padding: '3px',
                 }">
              <div v-for="n in form.divisions_x * form.divisions_y" :key="n"
                   class="rounded-sm opacity-60"
                   :style="{ backgroundColor: form.glass_color }" />
            </div>
          </div>
        </div>
      </div>

      <div class="mt-6 text-center text-xs text-carbon-400 font-mono">
        {{ form.width }} x {{ form.height }} x {{ form.depth }} мм |
        {{ form.divisions_x }} x {{ form.divisions_y }} секций
      </div>

      <p class="mt-4 text-center text-xs text-carbon-300">
        Полноценная 3D визуализация будет доступна после интеграции Three.js
      </p>
    </section>
  </div>
</template>
