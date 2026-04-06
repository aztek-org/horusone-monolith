<script setup lang="ts">
import type { Map as LeafletMap, Layer } from 'leaflet'

const { waypoints } = useWaypoints()
const { flightData, formattedPosition } = useFlightData()

// Map refs
const mapContainer = ref<HTMLElement | null>(null)
const map = ref<LeafletMap | null>(null)
const L = ref<any>(null)

// Cursor position tracking
const cursorPosition = ref({
  lat: "20°31'N",
  lon: "103°18'W",
  elevation: '5016 FT'
})

// Mock flight path coordinates (Guadalajara area - Miguel Hidalgo Airport)
const flightPathCoords: [number, number][] = [
  [20.5218, -103.3111], // Miguel Hidalgo Airport (GDL)
  [20.7233, -103.3925], // Zapopan
  [20.6767, -103.3475], // Central Guadalajara
  [20.6401, -103.3125], // Tlaquepaque
  [20.5500, -103.2800], // Airport Approach
]

// Map waypoints to realistic coordinates
const waypointCoords = computed(() => {
  return waypoints.value.map((wp, index) => ({
    ...wp,
    coords: flightPathCoords[index] || flightPathCoords[flightPathCoords.length - 1]
  }))
})

// Current aircraft position (mock) - Near Guadalajara
const aircraftPosition: [number, number] = [20.6500, -103.3300]

// Initialize Leaflet map
onMounted(async () => {
  if (mapContainer.value) {
    // Dynamic import for SSR compatibility
    L.value = await import('leaflet')

    // Initialize map
    map.value = L.value.map(mapContainer.value, {
      center: aircraftPosition,
      zoom: 10,
      zoomControl: false, // We'll use custom controls
      attributionControl: false,
    })

    // Add OpenStreetMap tiles with dark theme
    L.value.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
      maxZoom: 19,
      className: 'map-tiles-dark'
    }).addTo(map.value)

    // Add flight path polyline
    const flightPath = L.value.polyline(flightPathCoords, {
      color: '#00d4ff',
      weight: 3,
      opacity: 0.8,
      smoothFactor: 1,
      className: 'flight-path-line'
    }).addTo(map.value)

    // Add waypoint markers
    waypointCoords.value.forEach((wp) => {
      const markerColor = getMarkerColor(wp.status)
      const markerIcon = L.value.divIcon({
        className: 'custom-waypoint-marker',
        html: `
          <div class="waypoint-marker-container">
            <div class="waypoint-marker waypoint-${wp.status}"></div>
            <div class="waypoint-label waypoint-label-${wp.status}">${wp.name}</div>
          </div>
        `,
        iconSize: [16, 16],
        iconAnchor: [8, 8]
      })

      L.value.marker(wp.coords, { icon: markerIcon }).addTo(map.value)
    })

    // Add aircraft position marker
    const aircraftIcon = L.value.divIcon({
      className: 'custom-aircraft-marker',
      html: `
        <div class="aircraft-marker-container">
          <div class="aircraft-pulse"></div>
          <svg class="aircraft-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">
            <path d="M3.478 2.404a.75.75 0 0 0-.926.941l2.432 7.905H13.5a.75.75 0 0 1 0 1.5H4.984l-2.432 7.905a.75.75 0 0 0 .926.94 60.519 60.519 0 0 0 18.445-8.986.75.75 0 0 0 0-1.218A60.517 60.517 0 0 0 3.478 2.404Z" />
          </svg>
        </div>
      `,
      iconSize: [24, 24],
      iconAnchor: [12, 12]
    })

    L.value.marker(aircraftPosition, { icon: aircraftIcon }).addTo(map.value)

    // Update cursor position on mouse move
    if (map.value) {
      map.value.on('mousemove', (e: any) => {
        const { lat, lng } = e.latlng
        cursorPosition.value = {
          lat: formatCoordinate(lat, 'lat'),
          lon: formatCoordinate(lng, 'lon'),
          elevation: '5016 FT' // Mock elevation (Guadalajara)
        }
      })
    }
  }
})

// Cleanup on unmount
onUnmounted(() => {
  if (map.value) {
    map.value.remove()
  }
})

// Helper functions
function getMarkerColor(status: string): string {
  const colors: Record<string, string> = {
    event: '#ef4444',
    warning: '#f59e0b',
    pending: '#00d4ff',
    active: '#10b981'
  }
  return colors[status] || '#00d4ff'
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

// Zoom controls
function zoomIn() {
  if (map.value) {
    map.value.zoomIn()
  }
}

function zoomOut() {
  if (map.value) {
    map.value.zoomOut()
  }
}

function toggleLayers() {
  // Placeholder for layer toggle functionality
  console.log('Toggle layers')
}
</script>

<template>
  <HCard variant="glass" padding="none" class="relative overflow-hidden">
    <!-- Grid Overlay -->
    <div class="grid-overlay" />

    <!-- Map Container -->
    <div
      ref="mapContainer"
      class="relative aspect-[16/10] min-h-[300px] lg:min-h-[400px] z-0"
    />

    <!-- Map Controls & Info -->
    <div class="absolute bottom-4 left-4 right-4 flex items-end justify-between z-10">
      <!-- Coordinates -->
      <div class="bg-horus-bg-primary/90 backdrop-blur-sm rounded-lg px-3 py-2 border border-horus-border-subtle">
        <div class="flex items-center gap-4 text-xs">
          <div>
            <span class="text-horus-text-muted">CURSOR COORDINATES:</span>
            <span class="font-mono text-horus-text-primary ml-2">
              {{ cursorPosition.lat }} / {{ cursorPosition.lon }}
            </span>
          </div>
          <div>
            <span class="text-horus-text-muted">ELEVATION:</span>
            <span class="font-mono text-horus-text-primary ml-2">{{ cursorPosition.elevation }}</span>
          </div>
        </div>
      </div>

      <!-- Zoom Controls -->
      <div class="flex items-center gap-2">
        <button
          @click="zoomIn"
          class="w-10 h-10 rounded-lg bg-horus-bg-primary/90 backdrop-blur-sm border border-horus-border-subtle flex items-center justify-center text-horus-text-secondary hover:text-horus-text-primary hover:border-horus-accent-cyan/50 transition-colors"
        >
          <Icon name="heroicons:plus" class="w-5 h-5" />
        </button>
        <button
          @click="zoomOut"
          class="w-10 h-10 rounded-lg bg-horus-bg-primary/90 backdrop-blur-sm border border-horus-border-subtle flex items-center justify-center text-horus-text-secondary hover:text-horus-text-primary hover:border-horus-accent-cyan/50 transition-colors"
        >
          <Icon name="heroicons:minus" class="w-5 h-5" />
        </button>
        <button
          @click="toggleLayers"
          class="w-10 h-10 rounded-lg bg-horus-accent-cyan/20 border border-horus-accent-cyan/30 flex items-center justify-center text-horus-accent-cyan hover:bg-horus-accent-cyan/30 transition-colors"
        >
          <Icon name="heroicons:square-3-stack-3d" class="w-5 h-5" />
        </button>
      </div>
    </div>
  </HCard>
</template>

<style scoped>
/* Dark theme for map tiles */
:deep(.map-tiles-dark) {
  filter: brightness(0.6) contrast(1.2) saturate(0.7) hue-rotate(10deg);
}

/* Flight path with cyan glow */
:deep(.flight-path-line) {
  filter: drop-shadow(0 0 4px rgba(0, 212, 255, 0.6));
}

/* Custom waypoint markers */
:deep(.custom-waypoint-marker) {
  background: transparent;
  border: none;
}

:deep(.waypoint-marker-container) {
  position: relative;
}

:deep(.waypoint-marker) {
  width: 16px;
  height: 16px;
  border-radius: 50%;
  border: 2px solid #0a0f1a;
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
}

:deep(.waypoint-marker.waypoint-event) {
  background: #ef4444;
  box-shadow: 0 0 8px rgba(239, 68, 68, 0.6);
}

:deep(.waypoint-marker.waypoint-warning) {
  background: #f59e0b;
  box-shadow: 0 0 8px rgba(245, 158, 11, 0.6);
}

:deep(.waypoint-marker.waypoint-pending) {
  background: #00d4ff;
  box-shadow: 0 0 8px rgba(0, 212, 255, 0.6);
}

:deep(.waypoint-marker.waypoint-active) {
  background: #10b981;
  box-shadow: 0 0 8px rgba(16, 185, 129, 0.6);
  animation: pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite;
}

:deep(.waypoint-label) {
  position: absolute;
  left: 24px;
  top: 0;
  white-space: nowrap;
  font-size: 12px;
  font-family: 'Courier New', monospace;
  color: #94a3b8;
}

:deep(.waypoint-label.waypoint-label-event) {
  color: #ef4444;
}

:deep(.waypoint-label.waypoint-label-warning) {
  color: #f59e0b;
}

/* Aircraft marker */
:deep(.custom-aircraft-marker) {
  background: transparent;
  border: none;
}

:deep(.aircraft-marker-container) {
  position: relative;
  width: 24px;
  height: 24px;
}

:deep(.aircraft-icon) {
  width: 24px;
  height: 24px;
  color: #00d4ff;
  filter: drop-shadow(0 0 4px rgba(0, 212, 255, 0.8));
  transform: rotate(45deg);
  position: relative;
  z-index: 2;
}

:deep(.aircraft-pulse) {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: rgba(0, 212, 255, 0.2);
  animation: ping 1.5s cubic-bezier(0, 0, 0.2, 1) infinite;
  z-index: 1;
}

@keyframes ping {
  0% {
    transform: translate(-50%, -50%) scale(1);
    opacity: 1;
  }
  75%, 100% {
    transform: translate(-50%, -50%) scale(1.5);
    opacity: 0;
  }
}
</style>
