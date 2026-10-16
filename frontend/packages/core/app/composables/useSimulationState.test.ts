import { describe, it, expect, vi, beforeEach } from 'vitest'

const nuxt = vi.hoisted(() => ({
  state: {} as Record<string, unknown>,
  app: null as any,
}))

vi.mock('#app/nuxt', async () => {
  const { reactive } = await import('vue')
  nuxt.state = reactive<Record<string, unknown>>({})
  nuxt.app = { payload: { state: nuxt.state }, _state: {} }
  return {
    useNuxtApp: () => nuxt.app,
    tryUseNuxtApp: () => nuxt.app,
    useRuntimeConfig: () => ({ public: {} }),
  }
})

async function load() {
  const { useSimulationState } = await import('./useSimulationState')
  return useSimulationState()
}

describe('useSimulationState', () => {
  beforeEach(() => {
    vi.resetModules()
    for (const key of Object.keys(nuxt.state)) Reflect.deleteProperty(nuxt.state, key)
  })

  it('starts ready with the default state', async () => {
    const { state } = await load()
    expect(state.value).toMatchObject({
      status: 'ready',
      phase: 'PRE-FLIGHT',
      progress: 0,
      missionId: '',
      routeId: '',
      startTime: null,
      latency: 24,
      systemLoad: 1.2,
    })
  })

  it('derives the state flags', async () => {
    const { isReady, isRunning, isPaused } = await load()
    expect(isReady.value).toBe(true)
    expect(isRunning.value).toBe(false)
    expect(isPaused.value).toBe(false)
  })

  it('startSimulation resets progress and records the mission', async () => {
    const { state, startSimulation, isRunning } = await load()
    const before = Date.now()
    startSimulation('mission-7', 'route-2')

    expect(state.value.status).toBe('running')
    expect(state.value.missionId).toBe('mission-7')
    expect(state.value.routeId).toBe('route-2')
    expect(state.value.progress).toBe(0)
    expect(state.value.startTime).toBeInstanceOf(Date)
    expect(state.value.startTime!.getTime()).toBeGreaterThanOrEqual(before)
    expect(isRunning.value).toBe(true)
  })

  it('pauseSimulation pauses only a running simulation', async () => {
    const { state, startSimulation, pauseSimulation } = await load()
    pauseSimulation()
    expect(state.value.status).toBe('ready')

    startSimulation('m', 'r')
    pauseSimulation()
    expect(state.value.status).toBe('paused')
  })

  it('resumeSimulation resumes only a paused simulation', async () => {
    const { state, startSimulation, pauseSimulation, resumeSimulation } = await load()
    resumeSimulation()
    expect(state.value.status).toBe('ready')

    startSimulation('m', 'r')
    pauseSimulation()
    resumeSimulation()
    expect(state.value.status).toBe('running')
  })

  it('stopSimulation marks the simulation completed', async () => {
    const { state, startSimulation, stopSimulation } = await load()
    startSimulation('m', 'r')
    stopSimulation()
    expect(state.value.status).toBe('completed')
  })

  it('updateProgress clamps to 0..100 and optionally sets the phase', async () => {
    const { state, updateProgress } = await load()
    updateProgress(150, 'CRUISE')
    expect(state.value.progress).toBe(100)
    expect(state.value.phase).toBe('CRUISE')

    updateProgress(-10)
    expect(state.value.progress).toBe(0)
    expect(state.value.phase).toBe('CRUISE')
  })

  it('updateMetrics replaces latency and system load', async () => {
    const { state, updateMetrics } = await load()
    updateMetrics(80, 3.4)
    expect(state.value.latency).toBe(80)
    expect(state.value.systemLoad).toBe(3.4)
  })

  it('resetSimulation restores the defaults', async () => {
    const { state, startSimulation, updateMetrics, resetSimulation } = await load()
    startSimulation('m', 'r')
    updateMetrics(99, 9.9)
    resetSimulation()
    expect(state.value).toMatchObject({
      status: 'ready',
      phase: 'PRE-FLIGHT',
      progress: 0,
      missionId: '',
      routeId: '',
      startTime: null,
      latency: 24,
      systemLoad: 1.2,
    })
  })
})
