<script setup lang="ts">
import type { Map as LeafletMap } from 'leaflet'
import type { FlightPlanLeg } from '~/composables/useFlightPlans'

interface WaypointMarker {
  id: string
  name: string
  lat: number
  lon: number
  type: 'departure' | 'arrival' | 'alternate' | 'waypoint'
}

interface Props {
  departureLat: number | null
  departureLon: number | null
  arrivalLat: number | null
  arrivalLon: number | null
  departureIcao: string
  arrivalIcao: string
  alternateIcao?: string
  waypoints?: WaypointMarker[]
  legs?: FlightPlanLeg[]
  interactive?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  alternateIcao: '',
  waypoints: () => [],
  legs: () => [],
  interactive: true,
})

const emit = defineEmits<{
  'waypoint-click': [waypoint: WaypointMarker]
  'map-click': [latlng: { lat: number, lon: number }]
}>()

const mapContainer = ref<HTMLElement | null>(null)
const map = ref<LeafletMap | null>(null)
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const L = ref<any>(null)
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const layerGroup = ref<any>(null)

const cursorPosition = ref({
  lat: '--',
  lon: '--',
})

// Build all markers from props
const allMarkers = computed<WaypointMarker[]>(() => {
  const markers: WaypointMarker[] = []

  if (props.departureLat !== null && props.departureLon !== null) {
    markers.push({
      id: 'dep',
      name: props.departureIcao || 'DEP',
      lat: props.departureLat,
      lon: props.departureLon,
      type: 'departure',
    })
  }

  if (props.arrivalLat !== null && props.arrivalLon !== null) {
    markers.push({
      id: 'arr',
      name: props.arrivalIcao || 'ARR',
      lat: props.arrivalLat,
      lon: props.arrivalLon,
      type: 'arrival',
    })
  }

  markers.push(...props.waypoints)
  return markers
})

// Route polyline coordinates from legs or from dep/arr
const routeCoords = computed<[number, number][]>(() => {
  if (props.legs.length > 0) {
    const coords: [number, number][] = []
    for (const leg of props.legs) {
      if (leg.from_lat !== null && leg.from_lon !== null) {
        coords.push([leg.from_lat, leg.from_lon])
      }
      if (leg.to_lat !== null && leg.to_lon !== null) {
        coords.push([leg.to_lat, leg.to_lon])
      }
    }
    return coords
  }

  // Fallback: just connect departure to arrival
  const coords: [number, number][] = []
  if (props.departureLat !== null && props.departureLon !== null) {
    coords.push([props.departureLat, props.departureLon])
  }
  for (const wp of props.waypoints) {
    coords.push([wp.lat, wp.lon])
  }
  if (props.arrivalLat !== null && props.arrivalLon !== null) {
    coords.push([props.arrivalLat, props.arrivalLon])
  }
  return coords
})

function getMarkerHtml(type: WaypointMarker['type'], name: string): string {
  const colorMap: Record<string, string> = {
    departure: '#10b981',
    arrival: '#ef4444',
    alternate: '#f59e0b',
    waypoint: '#00d4ff',
  }
  const color = colorMap[type] || '#00d4ff'
  const iconMap: Record<string, string> = {
    departure: '▲',
    arrival: '▼',
    alternate: '◆',
    waypoint: '●',
  }
  const icon = iconMap[type] || '●'

  return `
    <div style="position:relative;text-align:center;">
      <div style="width:20px;height:20px;border-radius:50%;background:${color};border:2px solid #0a0f1a;display:flex;align-items:center;justify-content:center;font-size:10px;color:#0a0f1a;box-shadow:0 0 8px ${color}80;">${icon}</div>
      <div style="position:absolute;left:24px;top:0;white-space:nowrap;font-size:11px;font-family:monospace;color:${color};text-shadow:0 0 4px ${color}60;">${name}</div>
    </div>
  `
}

function formatCoordinate(value: number, type: 'lat' | 'lon'): string {
  const absValue = Math.abs(value)
  const degrees = Math.floor(absValue)
  const minutes = Math.floor((absValue - degrees) * 60)
  const direction = type === 'lat'
    ? (value >= 0 ? 'N' : 'S')
    : (value >= 0 ? 'E' : 'W')
  return `${degrees}°${minutes.toString().padStart(2, '0')}'${direction}`
}

// Render markers and route on the map
function renderMap() {
  if (!map.value || !L.value) return

  // Clear existing layers
  if (layerGroup.value) {
    layerGroup.value.clearLayers()
  }
  else {
    layerGroup.value = L.value.layerGroup().addTo(map.value)
  }

  // Route polyline
  if (routeCoords.value.length >= 2) {
    const polyline = L.value.polyline(routeCoords.value, {
      color: '#00d4ff',
      weight: 3,
      opacity: 0.8,
      dashArray: '8 4',
      className: 'flight-plan-route',
    })
    layerGroup.value.addLayer(polyline)
  }

  // Markers
  for (const marker of allMarkers.value) {
    const icon = L.value.divIcon({
      className: 'flight-plan-marker',
      html: getMarkerHtml(marker.type, marker.name),
      iconSize: [20, 20],
      iconAnchor: [10, 10],
    })

    const leafletMarker = L.value.marker([marker.lat, marker.lon], { icon })
    leafletMarker.on('click', () => {
      emit('waypoint-click', marker)
    })
    layerGroup.value.addLayer(leafletMarker)
  }

  // Fit bounds
  const allCoords = allMarkers.value.map(m => [m.lat, m.lon] as [number, number])
  if (allCoords.length >= 2) {
    const bounds = L.value.latLngBounds(allCoords)
    map.value.fitBounds(bounds, { padding: [60, 60], maxZoom: 10 })
  }
  else if (allCoords.length === 1) {
    map.value.setView(allCoords[0], 8)
  }
}

// Watch for prop changes and re-render
watch(
  [allMarkers, routeCoords],
  () => {
    renderMap()
  },
  { deep: true },
)

// Initialize map
onMounted(async () => {
  if (!mapContainer.value) return

  L.value = await import('leaflet')

  map.value = L.value.map(mapContainer.value, {
    center: [39.8283, -98.5795], // US center default
    zoom: 4,
    zoomControl: false,
    attributionControl: false,
  })

  L.value.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    className: 'map-tiles-dark',
  }).addTo(map.value)

  // Mouse tracking
  map.value.on('mousemove', (e: { latlng: { lat: number, lng: number } }) => {
    cursorPosition.value = {
      lat: formatCoordinate(e.latlng.lat, 'lat'),
      lon: formatCoordinate(e.latlng.lng, 'lon'),
    }
  })

  // Click to add waypoints
  if (props.interactive) {
    map.value.on('click', (e: { latlng: { lat: number, lng: number } }) => {
      emit('map-click', { lat: e.latlng.lat, lon: e.latlng.lng })
    })
  }

  renderMap()
})

onUnmounted(() => {
  if (map.value) {
    map.value.remove()
  }
})

function zoomIn() {
  map.value?.zoomIn()
}

function zoomOut() {
  map.value?.zoomOut()
}
</script>

<template>
  <HCard
    variant="glass"
    padding="none"
    class="relative overflow-hidden"
  >
    <!-- Map Container -->
    <div
      ref="mapContainer"
      class="relative w-full h-full min-h-[350px] lg:min-h-[450px] z-0"
    />

    <!-- Coordinates Overlay -->
    <div class="absolute bottom-3 left-3 right-3 flex items-end justify-between z-10">
      <div class="bg-horus-bg-primary/90 backdrop-blur-sm rounded-lg px-3 py-2 border border-horus-border-subtle">
        <div class="flex items-center gap-4 text-xs">
          <div>
            <span class="text-horus-text-muted">CURSOR:</span>
            <span class="font-mono text-horus-text-primary ml-2">
              {{ cursorPosition.lat }} / {{ cursorPosition.lon }}
            </span>
          </div>
        </div>
      </div>

      <!-- Zoom Controls -->
      <div class="flex items-center gap-2">
        <button
          class="w-9 h-9 rounded-lg bg-horus-bg-primary/90 backdrop-blur-sm border border-horus-border-subtle flex items-center justify-center text-horus-text-secondary hover:text-horus-text-primary hover:border-horus-accent-cyan/50 transition-colors"
          @click="zoomIn"
        >
          <Icon
            name="heroicons:plus"
            class="w-4 h-4"
          />
        </button>
        <button
          class="w-9 h-9 rounded-lg bg-horus-bg-primary/90 backdrop-blur-sm border border-horus-border-subtle flex items-center justify-center text-horus-text-secondary hover:text-horus-text-primary hover:border-horus-accent-cyan/50 transition-colors"
          @click="zoomOut"
        >
          <Icon
            name="heroicons:minus"
            class="w-4 h-4"
          />
        </button>
      </div>
    </div>

    <!-- Legend -->
    <div class="absolute top-3 right-3 z-10 bg-horus-bg-primary/90 backdrop-blur-sm rounded-lg px-3 py-2 border border-horus-border-subtle">
      <div class="space-y-1 text-xxs">
        <div class="flex items-center gap-2">
          <span class="w-2.5 h-2.5 rounded-full bg-horus-status-success" />
          <span class="text-horus-text-muted">Departure</span>
        </div>
        <div class="flex items-center gap-2">
          <span class="w-2.5 h-2.5 rounded-full bg-horus-status-danger" />
          <span class="text-horus-text-muted">Arrival</span>
        </div>
        <div class="flex items-center gap-2">
          <span class="w-2.5 h-2.5 rounded-full bg-horus-accent-cyan" />
          <span class="text-horus-text-muted">Waypoint</span>
        </div>
      </div>
    </div>
  </HCard>
</template>

<style scoped>
:deep(.map-tiles-dark) {
  filter: brightness(0.6) contrast(1.2) saturate(0.7) hue-rotate(10deg);
}

:deep(.flight-plan-route) {
  filter: drop-shadow(0 0 4px rgba(0, 212, 255, 0.6));
}

:deep(.flight-plan-marker) {
  background: transparent;
  border: none;
}
</style>
