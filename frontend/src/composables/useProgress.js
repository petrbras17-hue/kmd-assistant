import { useAppStore } from '@/stores/app'

export function useProgress() {
  const store = useAppStore()

  function start(stages, estimatedMs = 15000) {
    store.startProgress(stages, estimatedMs)
  }

  function complete() {
    store.completeProgress()
  }

  return { progress: store.aiProgress, start, complete }
}
