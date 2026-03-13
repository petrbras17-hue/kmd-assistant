<script setup>
import { ref, computed, onMounted } from 'vue'
import { useApi } from '@/composables/useApi'
import { useAppStore } from '@/stores/app'

const store = useAppStore()
const { loading, error, get } = useApi()

const stats = ref(null)

async function loadStats() {
  try {
    stats.value = await get('/api/stats')
  } catch { /* handled */ }
}

onMounted(loadStats)

const moduleUsage = computed(() => {
  if (!stats.value?.module_usage) return []
  const entries = Object.entries(stats.value.module_usage)
  const max = Math.max(...entries.map(([, v]) => v), 1)
  return entries
    .sort(([, a], [, b]) => b - a)
    .map(([name, count]) => ({
      name: store.cardDescriptions[name] ? name : name,
      label: store.navCategories
        .flatMap(c => c.items)
        .find(i => i.id === name)?.label || name,
      count,
      pct: Math.round((count / max) * 100),
    }))
})

const activityLog = computed(() => {
  return stats.value?.activity || stats.value?.recent_activity || []
})
</script>

<template>
  <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-10">
    <header class="mb-10 animate-fade-up">
      <span class="text-xs font-mono tracking-[0.2em] uppercase text-sage mb-2 block">Аналитика</span>
      <h1 class="font-display text-3xl sm:text-4xl text-carbon-900 mb-3">Дашборд</h1>
      <p class="text-carbon-500 font-body">{{ store.cardDescriptions.dashboard }}</p>
    </header>

    <!-- Loading -->
    <div v-if="loading" class="text-center py-16">
      <div class="inline-flex items-center gap-2 text-sm text-carbon-400">
        <svg class="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
          <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"/>
          <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
        </svg>
        Загрузка статистики...
      </div>
    </div>

    <div v-if="error" class="bg-status-fail/10 border border-status-fail/20 rounded-xl p-4 mb-8 text-sm text-status-fail">
      {{ error }}
    </div>

    <template v-if="stats">
      <!-- Summary cards -->
      <section class="grid grid-cols-2 sm:grid-cols-4 gap-4 mb-10 animate-fade-up" style="animation-delay:80ms">
        <div v-for="(item, i) in [
          { label: 'Всего запросов', value: stats.total_requests || stats.total || 0, color: 'text-carbon-800' },
          { label: 'Сегодня', value: stats.today || stats.requests_today || 0, color: 'text-sage' },
          { label: 'Проектов', value: stats.projects_count || stats.projects || 0, color: 'text-terra' },
          { label: 'Ошибок', value: stats.errors_count || stats.errors || 0, color: 'text-status-fail' },
        ]" :key="i"
             class="bg-white rounded-2xl border border-carbon-200/60 p-6 text-center">
          <p class="text-3xl font-display" :class="item.color">{{ item.value }}</p>
          <p class="text-xs text-carbon-400 mt-2 font-mono">{{ item.label }}</p>
        </div>
      </section>

      <!-- Module usage chart -->
      <section class="bg-white rounded-2xl border border-carbon-200/60 p-8 mb-8 animate-fade-up" style="animation-delay:160ms">
        <h2 class="font-display text-xl text-carbon-800 mb-6">Использование модулей</h2>

        <div v-if="moduleUsage.length" class="space-y-3">
          <div v-for="mod in moduleUsage" :key="mod.name" class="flex items-center gap-4">
            <span class="text-xs text-carbon-500 w-40 truncate">{{ mod.label }}</span>
            <div class="flex-1 h-6 bg-canvas rounded-full overflow-hidden">
              <div class="h-full bg-sage/70 rounded-full transition-all duration-700"
                   :style="{ width: `${mod.pct}%` }" />
            </div>
            <span class="text-xs font-mono text-carbon-400 w-12 text-right">{{ mod.count }}</span>
          </div>
        </div>

        <p v-else class="text-sm text-carbon-400">Нет данных об использовании.</p>
      </section>

      <!-- Activity log -->
      <section class="bg-white rounded-2xl border border-carbon-200/60 p-8 animate-fade-up" style="animation-delay:240ms">
        <h2 class="font-display text-xl text-carbon-800 mb-6">Журнал активности</h2>

        <div v-if="activityLog.length" class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="border-b border-carbon-200/60">
                <th class="text-left py-3 px-4 text-xs font-mono text-carbon-400 uppercase">Время</th>
                <th class="text-left py-3 px-4 text-xs font-mono text-carbon-400 uppercase">Модуль</th>
                <th class="text-left py-3 px-4 text-xs font-mono text-carbon-400 uppercase">Действие</th>
                <th class="text-left py-3 px-4 text-xs font-mono text-carbon-400 uppercase">Статус</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(log, i) in activityLog" :key="i"
                  class="border-b border-carbon-100 hover:bg-canvas transition-colors">
                <td class="py-3 px-4 font-mono text-xs text-carbon-400">
                  {{ log.timestamp || log.time || log.date || '' }}
                </td>
                <td class="py-3 px-4 text-carbon-600">{{ log.module || log.endpoint || '' }}</td>
                <td class="py-3 px-4 text-carbon-500 text-xs">{{ log.action || log.type || '' }}</td>
                <td class="py-3 px-4">
                  <span class="text-xs font-mono px-2 py-0.5 rounded"
                        :class="(log.status === 'ok' || log.status === 'success')
                          ? 'bg-status-ok/10 text-status-ok'
                          : (log.status === 'error' || log.status === 'fail')
                            ? 'bg-status-fail/10 text-status-fail'
                            : 'bg-canvas text-carbon-400'">
                    {{ log.status || '-' }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>

        <p v-else class="text-sm text-carbon-400">Нет записей активности.</p>
      </section>
    </template>
  </div>
</template>
