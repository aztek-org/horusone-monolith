<script setup lang="ts">
const { waypoints } = useWaypoints()
const { flightData, formattedPosition } = useFlightData()

// Simulated map position for demo
const cursorPosition = ref({
  lat: "34°03'N",
  lon: "118°14'W",
  elevation: '420 FT'
})

// Calculate positions for waypoints on the map (simplified)
const waypointPositions = computed(() => {
  return waypoints.value.map((wp, index) => ({
    ...wp,
    x: 20 + (index * 25) + '%',
    y: 70 - (index * 15) + '%'
  }))
})
</script>

<template>
  <HCard variant="glass" padding="none" class="relative overflow-hidden">
    <!-- Grid Overlay -->
    <div class="grid-overlay" />
    
    <!-- Map Container -->
    <div class="relative aspect-[16/10] min-h-[300px] lg:min-h-[400px]">
      <!-- Background gradient simulating terrain -->
      <div class="absolute inset-0 bg-gradient-to-b from-horus-bg-tertiary/30 to-horus-bg-primary/50" />
      
      <!-- Flight Path SVG -->
      <svg class="absolute inset-0 w-full h-full" preserveAspectRatio="none">
        <!-- Flight path line -->
        <path
          d="M 100,320 Q 200,280 300,240 Q 400,200 500,180 Q 600,160 700,140"
          fill="none"
          stroke="url(#pathGradient)"
          stroke-width="3"
          stroke-linecap="round"
          class="filter drop-shadow-lg"
        />
        
        <!-- Gradient definition -->
        <defs>
          <linearGradient id="pathGradient" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stop-color="#00d4ff" stop-opacity="0.3" />
            <stop offset="50%" stop-color="#00d4ff" stop-opacity="1" />
            <stop offset="100%" stop-color="#00d4ff" stop-opacity="0.5" />
          </linearGradient>
        </defs>
      </svg>
      
      <!-- Waypoint Markers -->
      <div
        v-for="(wp, index) in waypointPositions"
        :key="wp.id"
        :style="{ left: wp.x, top: wp.y }"
        class="absolute transform -translate-x-1/2 -translate-y-1/2"
      >
        <div
          :class="[
            'w-4 h-4 rounded-full border-2 border-horus-bg-primary',
            wp.status === 'event' && 'bg-horus-status-danger shadow-glow-danger',
            wp.status === 'warning' && 'bg-horus-status-warning shadow-glow-warning',
            wp.status === 'pending' && 'bg-horus-accent-cyan shadow-glow-cyan',
            wp.status === 'active' && 'bg-horus-status-success shadow-glow-success animate-pulse'
          ]"
        />
        <!-- Waypoint Label -->
        <div 
          :class="[
            'absolute left-6 top-0 whitespace-nowrap text-xs font-mono',
            wp.status === 'event' ? 'text-horus-status-danger' : 
            wp.status === 'warning' ? 'text-horus-status-warning' : 
            'text-horus-text-secondary'
          ]"
        >
          {{ wp.name }}
        </div>
      </div>
      
      <!-- Aircraft Position Indicator -->
      <div 
        class="absolute transform -translate-x-1/2 -translate-y-1/2"
        style="left: 40%; top: 55%;"
      >
        <div class="relative">
          <Icon 
            name="heroicons:paper-airplane-solid" 
            class="w-6 h-6 text-horus-accent-cyan rotate-45 drop-shadow-lg" 
          />
          <div class="absolute -inset-2 rounded-full bg-horus-accent-cyan/20 animate-ping" />
        </div>
      </div>
    </div>
    
    <!-- Map Controls & Info -->
    <div class="absolute bottom-4 left-4 right-4 flex items-end justify-between">
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
        <button class="w-10 h-10 rounded-lg bg-horus-bg-primary/90 backdrop-blur-sm border border-horus-border-subtle flex items-center justify-center text-horus-text-secondary hover:text-horus-text-primary hover:border-horus-accent-cyan/50 transition-colors">
          <Icon name="heroicons:plus" class="w-5 h-5" />
        </button>
        <button class="w-10 h-10 rounded-lg bg-horus-bg-primary/90 backdrop-blur-sm border border-horus-border-subtle flex items-center justify-center text-horus-text-secondary hover:text-horus-text-primary hover:border-horus-accent-cyan/50 transition-colors">
          <Icon name="heroicons:minus" class="w-5 h-5" />
        </button>
        <button class="w-10 h-10 rounded-lg bg-horus-accent-cyan/20 border border-horus-accent-cyan/30 flex items-center justify-center text-horus-accent-cyan hover:bg-horus-accent-cyan/30 transition-colors">
          <Icon name="heroicons:square-3-stack-3d" class="w-5 h-5" />
        </button>
      </div>
    </div>
  </HCard>
</template>
