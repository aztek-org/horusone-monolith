export interface Waypoint {
  id: string
  name: string
  type: 'waypoint' | 'airport' | 'vor' | 'fix'
  lat: number
  lon: number
  altitude?: number
  status: 'pending' | 'active' | 'passed' | 'warning' | 'event'
  scenario?: string
  eta?: string
}

const defaultWaypoints: Waypoint[] = [
  {
    id: 'wp-1',
    name: 'DABOX',
    type: 'fix',
    lat: 34.12,
    lon: -118.45,
    altitude: 35000,
    status: 'warning',
    scenario: 'Altitude Constraint Change'
  },
  {
    id: 'wp-2',
    name: 'NEVEE',
    type: 'fix',
    lat: 33.95,
    lon: -117.89,
    altitude: 28000,
    status: 'event',
    scenario: 'Left Engine Bleed'
  },
  {
    id: 'wp-3',
    name: 'SEAL BEACH',
    type: 'vor',
    lat: 33.78,
    lon: -118.05,
    altitude: 18000,
    status: 'pending'
  }
]

export const useWaypoints = () => {
  const waypoints = useState<Waypoint[]>('waypoints', () => [...defaultWaypoints])
  const activeWaypointId = useState<string | null>('activeWaypoint', () => null)

  const activeWaypoint = computed(() =>
    waypoints.value.find(wp => wp.id === activeWaypointId.value)
  )

  const pendingWaypoints = computed(() =>
    waypoints.value.filter(wp => wp.status === 'pending')
  )

  const passedWaypoints = computed(() =>
    waypoints.value.filter(wp => wp.status === 'passed')
  )

  function addWaypoint(waypoint: Omit<Waypoint, 'id'>) {
    const id = `wp-${Date.now()}`
    waypoints.value.push({ ...waypoint, id })
    return id
  }

  function updateWaypoint(id: string, updates: Partial<Omit<Waypoint, 'id'>>) {
    const index = waypoints.value.findIndex(wp => wp.id === id)
    if (index !== -1) {
      Object.assign(waypoints.value[index], updates)
    }
  }

  function removeWaypoint(id: string) {
    const index = waypoints.value.findIndex(wp => wp.id === id)
    if (index !== -1) {
      waypoints.value.splice(index, 1)
    }
  }

  function setActiveWaypoint(id: string | null) {
    activeWaypointId.value = id
  }

  function markWaypointPassed(id: string) {
    updateWaypoint(id, { status: 'passed' })
    // Set next pending waypoint as active
    const nextPending = waypoints.value.find(wp => wp.status === 'pending')
    if (nextPending) {
      setActiveWaypoint(nextPending.id)
      updateWaypoint(nextPending.id, { status: 'active' })
    }
  }

  function resetWaypoints() {
    waypoints.value = [...defaultWaypoints]
    activeWaypointId.value = null
  }

  return {
    waypoints: readonly(waypoints),
    activeWaypoint,
    activeWaypointId: readonly(activeWaypointId),
    pendingWaypoints,
    passedWaypoints,
    addWaypoint,
    updateWaypoint,
    removeWaypoint,
    setActiveWaypoint,
    markWaypointPassed,
    resetWaypoints
  }
}
