export interface SimulationState {
  status: 'ready' | 'running' | 'paused' | 'completed'
  phase: string
  progress: number
  missionId: string
  routeId: string
  startTime: Date | null
  latency: number
  systemLoad: number
}

const defaultState: SimulationState = {
  status: 'ready',
  phase: 'PRE-FLIGHT',
  progress: 0,
  missionId: '',
  routeId: '',
  startTime: null,
  latency: 24,
  systemLoad: 1.2
}

export const useSimulationState = () => {
  const state = useState<SimulationState>('simulation', () => ({ ...defaultState }))

  const isRunning = computed(() => state.value.status === 'running')
  const isPaused = computed(() => state.value.status === 'paused')
  const isReady = computed(() => state.value.status === 'ready')

  function startSimulation(missionId: string, routeId: string) {
    state.value = {
      ...state.value,
      status: 'running',
      missionId,
      routeId,
      startTime: new Date(),
      progress: 0
    }
  }

  function pauseSimulation() {
    if (state.value.status === 'running') {
      state.value.status = 'paused'
    }
  }

  function resumeSimulation() {
    if (state.value.status === 'paused') {
      state.value.status = 'running'
    }
  }

  function stopSimulation() {
    state.value.status = 'completed'
  }

  function resetSimulation() {
    state.value = { ...defaultState }
  }

  function updateProgress(progress: number, phase?: string) {
    state.value.progress = Math.min(100, Math.max(0, progress))
    if (phase) {
      state.value.phase = phase
    }
  }

  function updateMetrics(latency: number, systemLoad: number) {
    state.value.latency = latency
    state.value.systemLoad = systemLoad
  }

  return {
    state: readonly(state),
    isRunning,
    isPaused,
    isReady,
    startSimulation,
    pauseSimulation,
    resumeSimulation,
    stopSimulation,
    resetSimulation,
    updateProgress,
    updateMetrics
  }
}
