<script setup lang="ts">
const { layers, toggleLayer } = useChartLayers()

function getBadgeVariant(status: string) {
  switch (status) {
    case 'active': return 'active'
    case 'mod': return 'mod'
    default: return 'idle'
  }
}
</script>

<template>
  <HCard variant="default" padding="md">
    <div class="space-y-4">
      <!-- Header -->
      <h3 class="text-xs font-semibold text-horus-text-secondary uppercase tracking-wider">
        CHART LAYERS
      </h3>
      
      <!-- Layer Toggles -->
      <div class="space-y-3">
        <label
          v-for="layer in layers"
          :key="layer.id"
          class="flex items-center justify-between gap-3 p-2 rounded-lg hover:bg-horus-bg-tertiary/50 cursor-pointer transition-colors"
        >
          <div class="flex items-center gap-3">
            <!-- Checkbox -->
            <div
              :class="[
                'w-5 h-5 rounded border-2 flex items-center justify-center transition-all',
                layer.enabled
                  ? 'bg-horus-accent-cyan border-horus-accent-cyan'
                  : 'bg-transparent border-horus-border-default'
              ]"
              @click.prevent="toggleLayer(layer.id)"
            >
              <svg
                v-if="layer.enabled"
                class="w-3 h-3 text-horus-bg-primary"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
                stroke-width="3"
              >
                <path stroke-linecap="round" stroke-linejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            </div>
            
            <span class="text-sm text-horus-text-primary">{{ layer.name }}</span>
          </div>
          
          <HBadge :variant="getBadgeVariant(layer.status)" size="sm">
            {{ layer.status.toUpperCase() }}
          </HBadge>
        </label>
      </div>
    </div>
  </HCard>
</template>
