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
  const { useWeatherData } = await import('./useWeatherData')
  return useWeatherData()
}

describe('useWeatherData', () => {
  beforeEach(() => {
    vi.resetModules()
    for (const key of Object.keys(nuxt.state)) Reflect.deleteProperty(nuxt.state, key)
  })

  it('starts with the default weather snapshot', async () => {
    const { weather } = await load()
    expect(weather.value.metar).toHaveLength(2)
    expect(weather.value.precipLevel).toBe('extreme')
    expect(weather.value.radarRange).toBe(120)
    expect(weather.value.lastUpdate).toBe('14:02:48 Z')
    expect(weather.value.analysis).toContain('convective activity')
  })

  it('exposes the precipitation level options', async () => {
    const { precipLevels } = await load()
    expect(precipLevels.map(p => p.value)).toEqual([
      'extreme',
      'heavy',
      'moderate',
      'light',
      'none',
    ])
  })

  it('updateMetar replaces an existing station report', async () => {
    const { weather, updateMetar } = await load()
    updateMetar('KJFK METAR', 'KJFK 130000Z 00000KT 10SM CLR 20/10 A3000')
    expect(weather.value.metar).toHaveLength(2)
    expect(weather.value.metar[0].raw).toContain('CLR')
    expect(weather.value.metar[0].time).toMatch(/^\d{2}\d{2}:\dZ$/)
  })

  it('updateMetar appends a new station report', async () => {
    const { weather, updateMetar } = await load()
    updateMetar('KLAX METAR', 'KLAX 130000Z 00000KT 10SM CLR 22/12 A2999')
    expect(weather.value.metar).toHaveLength(3)
    expect(weather.value.metar.at(-1)?.station).toBe('KLAX METAR')
  })

  it('updateMetar refreshes lastUpdate', async () => {
    const { weather, updateMetar } = await load()
    updateMetar('KJFK METAR', 'KJFK 130000Z 00000KT 10SM CLR 20/10 A3000')
    expect(weather.value.lastUpdate).toMatch(/^\d{2}:\d{2}:\d{2} Z$/)
  })

  it('setPrecipLevel, setRadarRange and setAnalysis mutate the snapshot', async () => {
    const { weather, setPrecipLevel, setRadarRange, setAnalysis } = await load()
    setPrecipLevel('light')
    setRadarRange(240)
    setAnalysis('Clear skies ahead')
    expect(weather.value.precipLevel).toBe('light')
    expect(weather.value.radarRange).toBe(240)
    expect(weather.value.analysis).toBe('Clear skies ahead')
  })

  it('resetWeather restores the defaults', async () => {
    const { weather, setPrecipLevel, setRadarRange, resetWeather } = await load()
    setPrecipLevel('none')
    setRadarRange(10)
    resetWeather()
    expect(weather.value.precipLevel).toBe('extreme')
    expect(weather.value.radarRange).toBe(120)
    expect(weather.value.metar).toHaveLength(2)
  })
})
