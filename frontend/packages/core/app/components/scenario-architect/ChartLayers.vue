<script setup lang="ts">
const { layers, toggleLayer } = useChartLayers()

// Collapse state
const isCollapsed = ref(false)

function toggleCollapse() {
  isCollapsed.value = !isCollapsed.value
}

function getBadgeVariant(status: string) {
  switch (status) {
    case 'active': return 'active'
    case 'mod': return 'mod'
    default: return 'idle'
  }
}
</script>

<template>
  <HCard
    variant="default"
    padding="md"
    class="relative"
  >
    <div class="space-y-4">
      <!-- Header with Collapse/Expand Button -->
      <div class="flex items-center justify-between">
        <div class="flex items-center gap-3">
          <h3 class="text-xs font-semibold text-horus-text-secondary uppercase tracking-wider">
            CHART LAYERS
          </h3>
          <!-- Active layers indicator when collapsed -->
          <div
            v-if="isCollapsed && layers.filter(l => l.enabled).length > 0"
            class="flex items-center gap-1.5"
          >
            <div class="w-2 h-2 rounded-full bg-horus-accent-cyan animate-pulse" />
            <span class="text-xs font-mono text-horus-accent-cyan">
              {{ layers.filter(l => l.enabled).length }} active
            </span>
          </div>
        </div>
        <button
          class="w-8 h-8 rounded-lg flex items-center justify-center text-horus-text-muted hover:text-horus-text-primary hover:bg-horus-bg-tertiary/50 transition-all"
          :title="isCollapsed ? 'Expand' : 'Collapse'"
          @click="toggleCollapse"
        >
          <Icon
            :name="isCollapsed ? 'heroicons:chevron-down' : 'heroicons:chevron-up'"
            class="w-5 h-5"
          />
        </button>
      </div>

      <!-- Layer Toggles (collapsible) -->
      <Transition name="slide-down">
        <div
          v-if="!isCollapsed"
          class="space-y-3"
        >
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
                    : 'bg-transparent border-horus-border-default',
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
                  <path
                    stroke-linecap="round"
                    stroke-linejoin="round"
                    d="M5 13l4 4L19 7"
                  />
                </svg>
              </div>

              <span class="text-sm text-horus-text-primary">{{ layer.name }}</span>
            </div>

            <HBadge
              :variant="getBadgeVariant(layer.status)"
              size="sm"
            >
              {{ layer.status.toUpperCase() }}
            </HBadge>
          </label>
        </div>
      </Transition>
    </div>
  </HCard>
</template>

<style scoped>
/* Slide down animation */
.slide-down-enter-active,
.slide-down-leave-active {
  transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  max-height: 500px;
  overflow: hidden;
}

.slide-down-enter-from,
.slide-down-leave-to {
  opacity: 0;
  max-height: 0;
  transform: translateY(-10px);
}
</style>
