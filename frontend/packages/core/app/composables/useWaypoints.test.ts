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
  const { useWaypoints } = await import('./useWaypoints')
  return useWaypoints()
}

describe('useWaypoints', () => {
  beforeEach(() => {
    vi.resetModules()
    for (const key of Object.keys(nuxt.state)) Reflect.deleteProperty(nuxt.state, key)
  })

  it('starts with the three default waypoints', async () => {
    const { waypoints } = await load()
    expect(waypoints.value.map(w => w.id)).toEqual(['wp-1', 'wp-2', 'wp-3'])
    expect(waypoints.value.map(w => w.status)).toEqual(['warning', 'event', 'pending'])
  })

  it('activeWaypoint is undefined until one is selected', async () => {
    const { activeWaypoint } = await load()
    expect(activeWaypoint.value).toBeUndefined()
  })

  it('derives pending and passed lists', async () => {
    const { pendingWaypoints, passedWaypoints } = await load()
    expect(pendingWaypoints.value.map(w => w.id)).toEqual(['wp-3'])
    expect(passedWaypoints.value).toEqual([])
  })

  it('setActiveWaypoint selects and clears the active waypoint', async () => {
    const { activeWaypoint, activeWaypointId, setActiveWaypoint } = await load()
    setActiveWaypoint('wp-2')
    expect(activeWaypointId.value).toBe('wp-2')
    expect(activeWaypoint.value?.name).toBe('NEVEE')

    setActiveWaypoint(null)
    expect(activeWaypoint.value).toBeUndefined()
  })

  it('addWaypoint appends with a generated id and returns it', async () => {
    const { waypoints, addWaypoint } = await load()
    const id = addWaypoint({
      name: 'ROMEO',
      type: 'fix',
      lat: 1,
      lon: 2,
      status: 'pending',
    })
    expect(id).toMatch(/^wp-\d+$/)
    expect(waypoints.value).toHaveLength(4)
    expect(waypoints.value.at(-1)).toMatchObject({ id, name: 'ROMEO' })
  })

  it('updateWaypoint merges partial updates', async () => {
    const { waypoints, updateWaypoint } = await load()
    updateWaypoint('wp-1', { altitude: 12000, status: 'passed' })
    expect(waypoints.value.find(w => w.id === 'wp-1')).toMatchObject({
      name: 'DABOX',
      altitude: 12000,
      status: 'passed',
    })
  })

  it('removeWaypoint deletes the matching waypoint', async () => {
    const { waypoints, removeWaypoint } = await load()
    removeWaypoint('wp-2')
    expect(waypoints.value.map(w => w.id)).toEqual(['wp-1', 'wp-3'])
  })

  it('markWaypointPassed marks the waypoint and activates the next pending one', async () => {
    const { waypoints, activeWaypointId, markWaypointPassed } = await load()
    markWaypointPassed('wp-1')

    expect(waypoints.value.find(w => w.id === 'wp-1')?.status).toBe('passed')
    expect(activeWaypointId.value).toBe('wp-3')
    expect(waypoints.value.find(w => w.id === 'wp-3')?.status).toBe('active')
  })

  it('markWaypointPassed leaves the active waypoint unchanged when nothing is pending', async () => {
    const { activeWaypointId, markWaypointPassed, updateWaypoint, setActiveWaypoint } = await load()
    updateWaypoint('wp-3', { status: 'completed' })
    setActiveWaypoint(null)

    markWaypointPassed('wp-1')
    expect(activeWaypointId.value).toBeNull()
  })

  it('resetWaypoints restores the defaults and clears the active id', async () => {
    const { waypoints, activeWaypointId, removeWaypoint, setActiveWaypoint, resetWaypoints }
      = await load()
    removeWaypoint('wp-1')
    setActiveWaypoint('wp-2')

    resetWaypoints()

    expect(waypoints.value.map(w => w.id)).toEqual(['wp-1', 'wp-2', 'wp-3'])
    expect(activeWaypointId.value).toBeNull()
  })
})
