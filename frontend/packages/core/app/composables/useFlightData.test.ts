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
  const { useFlightData } = await import('./useFlightData')
  return useFlightData()
}

describe('useFlightData', () => {
  beforeEach(() => {
    vi.resetModules()
    for (const key of Object.keys(nuxt.state)) Reflect.deleteProperty(nuxt.state, key)
  })

  it('exposes the default flight data snapshot', async () => {
    const { flightData } = await load()
    expect(flightData.value).toMatchObject({
      airspeed: { value: 245, unit: 'KIAS', trend: 'down', trendValue: '-2' },
      altitude: { value: 12500, unit: 'FT', verticalSpeed: 150 },
      fuel: { onBoard: 8420, burnRate: 3400, unit: 'LBS' },
      position: { lat: 34.05, lon: -118.24, heading: 270 },
      systems: {
        propulsion: 'nominal',
        hydraulics: 'nominal',
        electrical: 'warning',
        pitotStatic: 'critical',
      },
    })
  })

  it('updateAirspeed replaces the value and optionally the trend', async () => {
    const { flightData, updateAirspeed } = await load()
    updateAirspeed(280, 'up', '+3')
    expect(flightData.value.airspeed).toMatchObject({ value: 280, trend: 'up', trendValue: '+3' })
    updateAirspeed(300)
    expect(flightData.value.airspeed).toMatchObject({ value: 300, trend: 'up', trendValue: '+3' })
  })

  it('updateAltitude replaces altitude and vertical speed', async () => {
    const { flightData, updateAltitude } = await load()
    updateAltitude(10000, -500)
    expect(flightData.value.altitude).toMatchObject({ value: 10000, verticalSpeed: -500 })
  })

  it('updateFuel replaces on-board fuel and burn rate', async () => {
    const { flightData, updateFuel } = await load()
    updateFuel(5000, 2200)
    expect(flightData.value.fuel).toMatchObject({ onBoard: 5000, burnRate: 2200 })
  })

  it('updatePosition replaces lat/lon and heading', async () => {
    const { flightData, updatePosition } = await load()
    updatePosition(40.7, -74.0, 90)
    expect(flightData.value.position).toEqual({ lat: 40.7, lon: -74.0, heading: 90 })
  })

  it('updateSystemStatus changes a single system', async () => {
    const { flightData, updateSystemStatus } = await load()
    updateSystemStatus('pitotStatic', 'nominal')
    expect(flightData.value.systems.pitotStatic).toBe('nominal')
  })

  it('computed warning/critical flags reflect the systems map', async () => {
    const { hasSystemWarning, hasSystemCritical } = await load()
    expect(hasSystemWarning.value).toBe(true)
    expect(hasSystemCritical.value).toBe(true)
  })

  it('clearing a warning updates hasSystemWarning', async () => {
    const { hasSystemWarning, updateSystemStatus } = await load()
    updateSystemStatus('electrical', 'nominal')
    expect(hasSystemWarning.value).toBe(false)
  })

  it('formattedPosition renders hemisphere-suffixed coordinates', async () => {
    const { formattedPosition } = await load()
    expect(formattedPosition.value).toEqual({ lat: '34.05°N', lon: '118.24°W' })

    const { formattedPosition: south, updatePosition } = await load()
    updatePosition(-33.87, 151.21, 180)
    expect(south.value).toEqual({ lat: '33.87°S', lon: '151.21°E' })
  })

  it('resetFlightData reassigns the state from the shared default snapshot', async () => {
    const { flightData, updateAirspeed, updateSystemStatus, resetFlightData } = await load()
    const before = flightData.value
    updateAirspeed(999)
    updateSystemStatus('electrical', 'offline')
    resetFlightData()
    // Top-level state object is replaced...
    expect(flightData.value).not.toBe(before)
    // ...but NOTE: `defaultFlightData` is shallow-copied, so nested objects are
    // shared and in-place updates (updateAirspeed/updateSystemStatus) persist.
    expect(flightData.value.airspeed.value).toBe(999)
    expect(flightData.value.systems.electrical).toBe('offline')
  })
})
