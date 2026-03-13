import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'

const STORAGE_KEY = 'kmd_app_state'
const STORAGE_VERSION = 2

export const useAppStore = defineStore('app', () => {
  // Navigation
  const sidebarOpen = ref(false)
  const navSearch = ref('')
  const openCategories = ref(['docs', 'calc', 'visual', 'ai', 'prod', 'analytics'])

  // AI Chat
  const showAiChat = ref(false)
  const aiChatMessages = ref([
    { role: 'bot', text: 'Привет! Я AI-помощник KMD Assistant. Спрашивайте про любой модуль, расчёт или ГОСТ — помогу разобраться.' },
  ])
  const aiChatInput = ref('')
  const aiChatLoading = ref(false)

  // Progress
  const aiProgress = ref({
    active: false,
    percent: 0,
    currentStage: 0,
    currentLabel: '',
    stages: [],
    timers: [],
  })

  // Global state
  const loading = ref(false)
  const error = ref(null)

  // Navigation categories
  const navCategories = [
    { key: 'docs', label: 'Документация', items: [
      { id: 'compare', label: 'Сравнение спецификаций', ai: false },
      { id: 'check', label: 'Проверка PDF', ai: false },
      { id: 'parse', label: 'Парсинг КМД', ai: false },
      { id: 'crossval', label: 'Кросс-валидация', ai: false },
      { id: 'comparepdf', label: 'Сравнение PDF', ai: false },
      { id: 'genspec', label: 'Генерация спецификации', ai: false },
      { id: 'batch', label: 'Пакетная обработка', ai: false },
      { id: 'checklist', label: 'Чек-лист КМД', ai: false },
    ]},
    { key: 'calc', label: 'Калькуляторы', items: [
      { id: 'thermal', label: 'Теплотехника', ai: false },
      { id: 'wind', label: 'Ветровая нагрузка', ai: false },
      { id: 'sashweight', label: 'Вес створки', ai: false },
      { id: 'glass', label: 'Стеклопакет', ai: false },
      { id: 'fasteners', label: 'Крепёж', ai: false },
    ]},
    { key: 'visual', label: '3D и оптимизация', items: [
      { id: 'preview3d', label: '3D Просмотр', ai: false },
      { id: 'cutting', label: 'Раскрой профиля', ai: false },
      { id: 'profileai', label: 'Подбор системы', ai: false },
    ]},
    { key: 'ai', label: 'AI инструменты', items: [
      { id: 'aireview', label: 'Ревью чертежа', ai: true },
      { id: 'ainote', label: 'Пояснительная записка', ai: true },
      { id: 'aigost', label: 'Консультант ГОСТ', ai: true },
      { id: 'aihardware', label: 'Подбор фурнитуры', ai: true },
      { id: 'aicompare', label: 'Сравнение чертежей', ai: true },
      { id: 'aigenkmd', label: 'Генерация КМД', ai: true },
      { id: 'aitranslate', label: 'Перевод ГОСТ/EN', ai: true },
    ]},
    { key: 'prod', label: 'Производство', items: [
      { id: 'versioning', label: 'Версионирование', ai: false },
      { id: 'requisition', label: 'Заявка на материалы', ai: false },
      { id: 'projects', label: 'Проекты', ai: false },
      { id: 'actgen', label: 'Акты', ai: false },
      { id: 'cnc', label: 'Программы ЧПУ', ai: false },
      { id: 'qrlabels', label: 'Маркировка', ai: false },
      { id: 'photoreport', label: 'Фотоотчёт', ai: false },
      { id: 'nodeslibrary', label: 'Библиотека узлов', ai: false },
    ]},
    { key: 'analytics', label: 'Аналитика', items: [
      { id: 'dashboard', label: 'Дашборд', ai: false },
    ]},
  ]

  // Category descriptions
  const catalogDescriptions = {
    docs: 'Полный инструментарий для работы с проектной документацией алюминиевых конструкций.',
    calc: 'Инженерные калькуляторы по действующим ГОСТ и СП.',
    visual: 'Трёхмерная визуализация и производственная оптимизация.',
    ai: 'Нейросетевые инструменты для анализа и генерации документации.',
    prod: 'Управление производственным процессом от заявки до сдачи.',
    analytics: 'Аналитический дашборд продуктивности.',
  }

  // Module descriptions
  const cardDescriptions = {
    compare: 'Интеллектуальное сопоставление двух спецификаций XLSX.',
    check: 'Комплексная валидация PDF-чертежа по критериям полноты.',
    parse: 'Автоматическое извлечение данных из чертежа КМД.',
    crossval: 'Перекрёстная верификация PDF и XLSX.',
    comparepdf: 'Посимвольное сравнение двух редакций PDF.',
    genspec: 'Формирование ведомости элементов из PDF/DXF.',
    batch: 'Массовая обработка проектного архива ZIP.',
    checklist: 'Аудит КМД по семи категориям качества.',
    thermal: 'Расчёт Uw по ГОСТ 26602.1-99.',
    wind: 'Ветровая нагрузка по СП 20.13330.2016.',
    sashweight: 'Калькуляция массы створки с контролем нагрузки.',
    glass: 'Конфигуратор формулы стеклопакета.',
    fasteners: 'Подбор крепёжных элементов по типу основания.',
    preview3d: '3D визуализация оконной/фасадной конструкции.',
    cutting: 'Оптимизация карт раскроя по FFD.',
    profileai: 'Подбор профильной серии из каталогов.',
    aireview: 'Нейросетевой анализ чертежа.',
    ainote: 'Автогенерация пояснительной записки.',
    aigost: 'Консультация по ГОСТ, СП, ТУ и СНиП.',
    aihardware: 'Подбор фурнитуры по параметрам конструкции.',
    aicompare: 'Визуальное сопоставление чертежей.',
    aigenkmd: 'Создание черновой версии КМД.',
    aitranslate: 'Перевод ГОСТ ↔ EN/ISO.',
    versioning: 'Контроль версий проектной документации.',
    requisition: 'Формирование заявки на закупку материалов.',
    projects: 'Управление жизненным циклом проекта.',
    actgen: 'Акты выполненных работ и приёмки.',
    cnc: 'Генерация программ для станков ЧПУ.',
    qrlabels: 'QR-маркировка изделий.',
    photoreport: 'Структурированный фотоотчёт по этапам.',
    nodeslibrary: 'Каталог типовых конструктивных узлов.',
    dashboard: 'Аналитическая панель использования платформы.',
  }

  // Filtered items
  function filteredItems(cat) {
    if (!navSearch.value) return cat.items
    const q = navSearch.value.toLowerCase()
    return cat.items.filter(i => i.label.toLowerCase().includes(q) || i.id.toLowerCase().includes(q))
  }

  // Toggle category
  function toggleCategory(key) {
    const idx = openCategories.value.indexOf(key)
    if (idx >= 0) openCategories.value.splice(idx, 1)
    else openCategories.value.push(key)
  }

  // Progress methods
  function startProgress(stages, estimatedMs = 15000) {
    aiProgress.value.active = true
    aiProgress.value.percent = 0
    aiProgress.value.currentStage = 0
    aiProgress.value.stages = stages
    aiProgress.value.currentLabel = stages[0]?.label || ''
    aiProgress.value.timers = []
    const perStage = estimatedMs / stages.length
    stages.forEach((stage, i) => {
      const timer = setTimeout(() => {
        aiProgress.value.currentStage = i
        aiProgress.value.currentLabel = stage.label
        const target = i < stages.length - 1 ? stages[i + 1].at : 92
        animateProgressTo(target, perStage * 0.8)
      }, i * perStage)
      aiProgress.value.timers.push(timer)
    })
  }

  function animateProgressTo(target, duration) {
    const start = aiProgress.value.percent
    const diff = target - start
    const startTime = performance.now()
    const step = (now) => {
      if (!aiProgress.value.active) return
      const elapsed = now - startTime
      const t = Math.min(elapsed / duration, 1)
      const eased = 1 - Math.pow(1 - t, 3)
      aiProgress.value.percent = Math.round(start + diff * eased)
      if (t < 1) requestAnimationFrame(step)
    }
    requestAnimationFrame(step)
  }

  function completeProgress() {
    aiProgress.value.timers.forEach(t => clearTimeout(t))
    aiProgress.value.timers = []
    aiProgress.value.currentStage = aiProgress.value.stages.length - 1
    aiProgress.value.currentLabel = 'Готово'
    animateProgressTo(100, 300)
    setTimeout(() => {
      aiProgress.value.active = false
      aiProgress.value.percent = 0
      aiProgress.value.currentStage = 0
      aiProgress.value.stages = []
    }, 600)
  }

  // LocalStorage persistence
  function saveState() {
    try {
      const state = {
        _version: STORAGE_VERSION,
        _savedAt: Date.now(),
        sidebarOpen: sidebarOpen.value,
        openCategories: openCategories.value,
        aiChatMessages: aiChatMessages.value,
      }
      const json = JSON.stringify(state)
      if (json.length > 4 * 1024 * 1024) return
      localStorage.setItem(STORAGE_KEY, json)
    } catch (e) {
      console.warn('[KMD] Save failed:', e.message)
    }
  }

  function loadState() {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      if (!raw) return
      const saved = JSON.parse(raw)
      if (!saved._version || saved._version < STORAGE_VERSION) {
        localStorage.removeItem(STORAGE_KEY)
        return
      }
      if (saved._savedAt && (Date.now() - saved._savedAt > 30 * 24 * 60 * 60 * 1000)) {
        localStorage.removeItem(STORAGE_KEY)
        return
      }
      if (typeof saved.sidebarOpen === 'boolean') sidebarOpen.value = saved.sidebarOpen
      if (Array.isArray(saved.openCategories)) openCategories.value = saved.openCategories
      if (Array.isArray(saved.aiChatMessages) && saved.aiChatMessages.length) {
        if (saved.aiChatMessages.every(m => m && typeof m.role === 'string' && typeof m.text === 'string')) {
          aiChatMessages.value = saved.aiChatMessages
        }
      }
    } catch {
      localStorage.removeItem(STORAGE_KEY)
    }
  }

  // Auto-save on changes
  watch([sidebarOpen, openCategories, aiChatMessages], () => saveState(), { deep: true })

  return {
    sidebarOpen, navSearch, openCategories, showAiChat,
    aiChatMessages, aiChatInput, aiChatLoading,
    aiProgress, loading, error,
    navCategories, catalogDescriptions, cardDescriptions,
    filteredItems, toggleCategory,
    startProgress, completeProgress,
    saveState, loadState,
  }
})
