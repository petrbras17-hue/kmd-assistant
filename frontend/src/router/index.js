import { createRouter, createWebHistory } from 'vue-router'

const LandingPage = () => import('@/modules/LandingPage.vue')

// Docs
const CompareModule = () => import('@/modules/docs/CompareModule.vue')
const CheckPdfModule = () => import('@/modules/docs/CheckPdfModule.vue')
const ParseKmdModule = () => import('@/modules/docs/ParseKmdModule.vue')
const CrossValModule = () => import('@/modules/docs/CrossValModule.vue')
const ComparePdfModule = () => import('@/modules/docs/ComparePdfModule.vue')
const GenSpecModule = () => import('@/modules/docs/GenSpecModule.vue')
const BatchModule = () => import('@/modules/docs/BatchModule.vue')
const ChecklistModule = () => import('@/modules/docs/ChecklistModule.vue')

// Calc
const ThermalModule = () => import('@/modules/calc/ThermalModule.vue')
const WindModule = () => import('@/modules/calc/WindModule.vue')
const SashWeightModule = () => import('@/modules/calc/SashWeightModule.vue')
const GlassModule = () => import('@/modules/calc/GlassModule.vue')
const FastenersModule = () => import('@/modules/calc/FastenersModule.vue')

// Visual
const Preview3dModule = () => import('@/modules/visual/Preview3dModule.vue')
const CuttingModule = () => import('@/modules/visual/CuttingModule.vue')
const ProfileAiModule = () => import('@/modules/visual/ProfileAiModule.vue')

// AI
const AiReviewModule = () => import('@/modules/ai/AiReviewModule.vue')
const AiNoteModule = () => import('@/modules/ai/AiNoteModule.vue')
const AiGostModule = () => import('@/modules/ai/AiGostModule.vue')
const AiHardwareModule = () => import('@/modules/ai/AiHardwareModule.vue')
const AiCompareModule = () => import('@/modules/ai/AiCompareModule.vue')
const AiGenKmdModule = () => import('@/modules/ai/AiGenKmdModule.vue')
const AiTranslateModule = () => import('@/modules/ai/AiTranslateModule.vue')

// Prod
const VersioningModule = () => import('@/modules/prod/VersioningModule.vue')
const RequisitionModule = () => import('@/modules/prod/RequisitionModule.vue')
const ProjectsModule = () => import('@/modules/prod/ProjectsModule.vue')
const ActGenModule = () => import('@/modules/prod/ActGenModule.vue')
const CncModule = () => import('@/modules/prod/CncModule.vue')
const QrLabelsModule = () => import('@/modules/prod/QrLabelsModule.vue')
const PhotoReportModule = () => import('@/modules/prod/PhotoReportModule.vue')
const NodesLibraryModule = () => import('@/modules/prod/NodesLibraryModule.vue')

// Analytics
const DashboardModule = () => import('@/modules/analytics/DashboardModule.vue')

const routes = [
  { path: '/', name: 'landing', component: LandingPage },

  // Docs
  { path: '/module/compare', name: 'compare', component: CompareModule, meta: { category: 'docs' } },
  { path: '/module/check', name: 'check', component: CheckPdfModule, meta: { category: 'docs' } },
  { path: '/module/parse', name: 'parse', component: ParseKmdModule, meta: { category: 'docs' } },
  { path: '/module/crossval', name: 'crossval', component: CrossValModule, meta: { category: 'docs' } },
  { path: '/module/comparepdf', name: 'comparepdf', component: ComparePdfModule, meta: { category: 'docs' } },
  { path: '/module/genspec', name: 'genspec', component: GenSpecModule, meta: { category: 'docs' } },
  { path: '/module/batch', name: 'batch', component: BatchModule, meta: { category: 'docs' } },
  { path: '/module/checklist', name: 'checklist', component: ChecklistModule, meta: { category: 'docs' } },

  // Calc
  { path: '/module/thermal', name: 'thermal', component: ThermalModule, meta: { category: 'calc' } },
  { path: '/module/wind', name: 'wind', component: WindModule, meta: { category: 'calc' } },
  { path: '/module/sashweight', name: 'sashweight', component: SashWeightModule, meta: { category: 'calc' } },
  { path: '/module/glass', name: 'glass', component: GlassModule, meta: { category: 'calc' } },
  { path: '/module/fasteners', name: 'fasteners', component: FastenersModule, meta: { category: 'calc' } },

  // Visual
  { path: '/module/preview3d', name: 'preview3d', component: Preview3dModule, meta: { category: 'visual' } },
  { path: '/module/cutting', name: 'cutting', component: CuttingModule, meta: { category: 'visual' } },
  { path: '/module/profileai', name: 'profileai', component: ProfileAiModule, meta: { category: 'visual' } },

  // AI
  { path: '/module/aireview', name: 'aireview', component: AiReviewModule, meta: { category: 'ai' } },
  { path: '/module/ainote', name: 'ainote', component: AiNoteModule, meta: { category: 'ai' } },
  { path: '/module/aigost', name: 'aigost', component: AiGostModule, meta: { category: 'ai' } },
  { path: '/module/aihardware', name: 'aihardware', component: AiHardwareModule, meta: { category: 'ai' } },
  { path: '/module/aicompare', name: 'aicompare', component: AiCompareModule, meta: { category: 'ai' } },
  { path: '/module/aigenkmd', name: 'aigenkmd', component: AiGenKmdModule, meta: { category: 'ai' } },
  { path: '/module/aitranslate', name: 'aitranslate', component: AiTranslateModule, meta: { category: 'ai' } },

  // Prod
  { path: '/module/versioning', name: 'versioning', component: VersioningModule, meta: { category: 'prod' } },
  { path: '/module/requisition', name: 'requisition', component: RequisitionModule, meta: { category: 'prod' } },
  { path: '/module/projects', name: 'projects', component: ProjectsModule, meta: { category: 'prod' } },
  { path: '/module/actgen', name: 'actgen', component: ActGenModule, meta: { category: 'prod' } },
  { path: '/module/cnc', name: 'cnc', component: CncModule, meta: { category: 'prod' } },
  { path: '/module/qrlabels', name: 'qrlabels', component: QrLabelsModule, meta: { category: 'prod' } },
  { path: '/module/photoreport', name: 'photoreport', component: PhotoReportModule, meta: { category: 'prod' } },
  { path: '/module/nodeslibrary', name: 'nodeslibrary', component: NodesLibraryModule, meta: { category: 'prod' } },

  // Analytics
  { path: '/dashboard', name: 'dashboard', component: DashboardModule, meta: { category: 'analytics' } },

  // Catch-all
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior() {
    return { top: 0, behavior: 'smooth' }
  },
})

export default router
