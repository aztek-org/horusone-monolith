export interface ChartLayer {
  id: string
  name: string
  enabled: boolean
  status: 'active' | 'idle' | 'mod'
}

const defaultLayers: ChartLayer[] = [
  { id: 'turbulence', name: 'Simulated Turbulence', enabled: true, status: 'mod' },
  { id: 'atc', name: 'ATC Constraints', enabled: true, status: 'active' },
  { id: 'failures', name: 'Mechanical Failures', enabled: false, status: 'idle' },
]

export const useChartLayers = () => {
  const layers = useState<ChartLayer[]>('chartLayers', () => [...defaultLayers])

  function toggleLayer(id: string) {
    const layer = layers.value.find(l => l.id === id)
    if (layer) {
      layer.enabled = !layer.enabled
      layer.status = layer.enabled ? 'active' : 'idle'
    }
  }

  function setLayerStatus(id: string, status: ChartLayer['status']) {
    const layer = layers.value.find(l => l.id === id)
    if (layer) {
      layer.status = status
    }
  }

  function enableAllLayers() {
    layers.value.forEach((layer) => {
      layer.enabled = true
      layer.status = 'active'
    })
  }

  function disableAllLayers() {
    layers.value.forEach((layer) => {
      layer.enabled = false
      layer.status = 'idle'
    })
  }

  function resetLayers() {
    layers.value = [...defaultLayers]
  }

  return {
    layers: readonly(layers),
    toggleLayer,
    setLayerStatus,
    enableAllLayers,
    disableAllLayers,
    resetLayers,
  }
}
