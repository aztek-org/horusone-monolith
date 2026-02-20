<script setup lang="ts">
interface Props {
  routeId?: string
  validated?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  routeId: 'LAX-TYO-992',
  validated: true
})

const { state: simulation } = useSimulationState()
</script>

<template>
  <footer class="sticky bottom-0 z-40 bg-horus-bg-primary/95 backdrop-blur-md border-t border-horus-border-subtle">
    <div class="flex items-center justify-between h-8 px-4 lg:px-6 text-xxs">
      <!-- Route Info -->
      <div class="flex items-center gap-4">
        <span class="text-horus-text-muted">
          ROUTE ID: <span class="text-horus-text-secondary font-mono">{{ routeId }}</span>
        </span>
        <span class="hidden sm:inline-flex items-center gap-1.5">
          STATUS:
          <span 
            :class="[
              'flex items-center gap-1 font-semibold',
              validated ? 'text-horus-status-success' : 'text-horus-status-warning'
            ]"
          >
            <span class="w-1.5 h-1.5 rounded-full bg-current" />
            {{ validated ? 'VALIDATED' : 'PENDING' }}
          </span>
        </span>
      </div>
      
      <!-- System Metrics -->
      <div class="flex items-center gap-4 text-horus-text-muted">
        <span class="hidden md:inline">
          LATENCY: <span class="text-horus-text-secondary font-mono">{{ simulation.latency }}ms</span>
        </span>
        <span>
          SYSTEMLOAD: <span class="text-horus-text-secondary font-mono">{{ simulation.systemLoad.toFixed(1) }} TFLOPS</span>
        </span>
      </div>
    </div>
  </footer>
</template>
