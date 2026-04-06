export interface FlightData {
  airspeed: {
    value: number
    unit: string
    trend: 'up' | 'down' | 'stable'
    trendValue: string
  }
  altitude: {
    value: number
    unit: string
    verticalSpeed: number
  }
  fuel: {
    onBoard: number
    burnRate: number
    unit: string
  }
  position: {
    lat: number
    lon: number
    heading: number
  }
  systems: {
    propulsion: 'nominal' | 'warning' | 'critical' | 'offline'
    hydraulics: 'nominal' | 'warning' | 'critical' | 'offline'
    electrical: 'nominal' | 'warning' | 'critical' | 'offline'
    pitotStatic: 'nominal' | 'warning' | 'critical' | 'offline'
  }
}

const defaultFlightData: FlightData = {
  airspeed: {
    value: 245,
    unit: 'KIAS',
    trend: 'down',
    trendValue: '-2'
  },
  altitude: {
    value: 12500,
    unit: 'FT',
    verticalSpeed: 150
  },
  fuel: {
    onBoard: 8420,
    burnRate: 3400,
    unit: 'LBS'
  },
  position: {
    lat: 34.05,
    lon: -118.24,
    heading: 270
  },
  systems: {
    propulsion: 'nominal',
    hydraulics: 'nominal',
    electrical: 'warning',
    pitotStatic: 'critical'
  }
}

export const useFlightData = () => {
  const flightData = useState<FlightData>('flightData', () => ({ ...defaultFlightData }))

  function updateAirspeed(value: number, trend?: 'up' | 'down' | 'stable', trendValue?: string) {
    flightData.value.airspeed.value = value
    if (trend) flightData.value.airspeed.trend = trend
    if (trendValue) flightData.value.airspeed.trendValue = trendValue
  }

  function updateAltitude(value: number, verticalSpeed?: number) {
    flightData.value.altitude.value = value
    if (verticalSpeed !== undefined) flightData.value.altitude.verticalSpeed = verticalSpeed
  }

  function updateFuel(onBoard: number, burnRate?: number) {
    flightData.value.fuel.onBoard = onBoard
    if (burnRate !== undefined) flightData.value.fuel.burnRate = burnRate
  }

  function updatePosition(lat: number, lon: number, heading?: number) {
    flightData.value.position.lat = lat
    flightData.value.position.lon = lon
    if (heading !== undefined) flightData.value.position.heading = heading
  }

  function updateSystemStatus(
    system: keyof FlightData['systems'],
    status: 'nominal' | 'warning' | 'critical' | 'offline'
  ) {
    flightData.value.systems[system] = status
  }

  function resetFlightData() {
    flightData.value = { ...defaultFlightData }
  }

  // Computed helpers
  const hasSystemWarning = computed(() =>
    Object.values(flightData.value.systems).some(s => s === 'warning')
  )

  const hasSystemCritical = computed(() =>
    Object.values(flightData.value.systems).some(s => s === 'critical')
  )

  const formattedPosition = computed(() => ({
    lat: `${Math.abs(flightData.value.position.lat).toFixed(2)}°${flightData.value.position.lat >= 0 ? 'N' : 'S'}`,
    lon: `${Math.abs(flightData.value.position.lon).toFixed(2)}°${flightData.value.position.lon >= 0 ? 'E' : 'W'}`
  }))

  return {
    flightData: readonly(flightData),
    updateAirspeed,
    updateAltitude,
    updateFuel,
    updatePosition,
    updateSystemStatus,
    resetFlightData,
    hasSystemWarning,
    hasSystemCritical,
    formattedPosition
  }
}
