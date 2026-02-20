export interface WeatherData {
  metar: {
    station: string
    raw: string
    time: string
  }[]
  precipLevel: 'extreme' | 'heavy' | 'moderate' | 'light' | 'none'
  radarRange: number
  lastUpdate: string
  analysis?: string
}

const defaultWeatherData: WeatherData = {
  metar: [
    {
      station: 'KJFK METAR',
      raw: 'KJFK 121851Z 19015G25KT 1/2SM +TSRA BKN008 OVC015CB 24/22 A2992',
      time: '121851Z'
    },
    {
      station: 'KTEB (ALT) METAR',
      raw: 'KTEB 121851Z 18012KT 10SM SCT025 OVC050 25/20 A2995',
      time: '121851Z'
    }
  ],
  precipLevel: 'extreme',
  radarRange: 120,
  lastUpdate: '14:02:48 Z',
  analysis: 'Significant convective activity detected on current flight path. KJFK ceiling dropping below CAT II minimums.'
}

export const useWeatherData = () => {
  const weather = useState<WeatherData>('weather', () => ({ ...defaultWeatherData }))

  const precipLevels = [
    { value: 'extreme', label: 'EXTREME', color: 'bg-horus-status-danger' },
    { value: 'heavy', label: 'HEAVY', color: 'bg-horus-status-warning' },
    { value: 'moderate', label: 'MOD', color: 'bg-horus-status-success' },
    { value: 'light', label: 'LIGHT', color: 'bg-horus-accent-cyan' },
    { value: 'none', label: 'NONE', color: 'bg-horus-text-muted' }
  ]

  function updateMetar(station: string, raw: string) {
    const index = weather.value.metar.findIndex(m => m.station === station)
    const time = new Date().toISOString().slice(8, 10) + new Date().toISOString().slice(11, 15) + 'Z'
    if (index !== -1) {
      weather.value.metar[index] = { station, raw, time }
    } else {
      weather.value.metar.push({ station, raw, time })
    }
    weather.value.lastUpdate = new Date().toISOString().slice(11, 19) + ' Z'
  }

  function setPrecipLevel(level: WeatherData['precipLevel']) {
    weather.value.precipLevel = level
  }

  function setRadarRange(range: number) {
    weather.value.radarRange = range
  }

  function setAnalysis(analysis: string) {
    weather.value.analysis = analysis
  }

  function resetWeather() {
    weather.value = { ...defaultWeatherData }
  }

  return {
    weather: readonly(weather),
    precipLevels,
    updateMetar,
    setPrecipLevel,
    setRadarRange,
    setAnalysis,
    resetWeather
  }
}
