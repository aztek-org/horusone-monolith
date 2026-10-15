<script setup lang="ts">
const { items, progressPercentage } = useChecklist()
const { waypoints } = useWaypoints()

const preflightItems = computed(() =>
  items.value.filter(item => item.category === 'PRE-FLIGHT OPERATIONS'),
)
</script>

<template>
  <div class="space-y-6">
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2">
        <Icon
          name="heroicons:clipboard-document-check"
          class="w-5 h-5 text-horus-accent-cyan"
        />
        <h2 class="text-sm font-semibold text-horus-text-primary">
          ROUTE CHECKLIST
        </h2>
      </div>
      <button class="text-xs text-horus-accent-cyan hover:text-horus-accent-cyan-glow flex items-center gap-1">
        <Icon
          name="heroicons:plus"
          class="w-4 h-4"
        />
        Add Task
      </button>
    </div>

    <!-- Pre-Flight Operations -->
    <HSection
      icon="heroicons:document-text"
      title="PRE-FLIGHT OPERATIONS"
      :collapsible="true"
      :default-expanded="true"
    >
      <div class="space-y-1">
        <HChecklistItem
          v-for="item in preflightItems"
          :key="item.id"
          :title="item.title"
          :subtitle="item.subtitle"
          :status="item.status"
        />
      </div>
    </HSection>

    <!-- En-Route Waypoints -->
    <HSection
      icon="heroicons:map-pin"
      title="EN-ROUTE WAYPOINTS"
      :collapsible="true"
      :default-expanded="true"
    >
      <div class="space-y-1">
        <div
          v-for="waypoint in waypoints"
          :key="waypoint.id"
          :class="[
            'flex items-center gap-3 p-3 rounded-lg transition-colors',
            'hover:bg-horus-bg-tertiary/50',
          ]"
        >
          <!-- Waypoint Marker -->
          <div
            :class="[
              'w-6 h-6 rounded flex items-center justify-center text-xs font-mono',
              waypoint.status === 'event' && 'bg-horus-status-danger/20 text-horus-status-danger',
              waypoint.status === 'warning' && 'bg-horus-status-warning/20 text-horus-status-warning',
              waypoint.status === 'pending' && 'bg-horus-bg-tertiary text-horus-text-muted',
            ]"
          >
            <Icon
              v-if="waypoint.status === 'event'"
              name="heroicons:exclamation-triangle-solid"
              class="w-4 h-4"
            />
            <span v-else>:</span>
          </div>

          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2">
              <span class="text-sm font-medium text-horus-text-primary">{{ waypoint.name }}</span>
              <HBadge
                v-if="waypoint.status === 'event'"
                variant="danger"
                size="sm"
              >
                EVENT
              </HBadge>
              <span
                v-if="waypoint.altitude"
                class="text-xs font-mono text-horus-accent-cyan ml-auto"
              >
                FL{{ Math.round(waypoint.altitude / 100) }}
              </span>
            </div>
            <p
              v-if="waypoint.scenario"
              class="text-xs text-horus-text-muted mt-0.5"
            >
              Scenario: {{ waypoint.scenario }}
            </p>
          </div>
        </div>
      </div>
    </HSection>

    <!-- Progress Bar -->
    <div class="pt-4 border-t border-horus-border-subtle">
      <HProgress
        :value="progressPercentage"
        label="PROGRESS"
        size="sm"
      />
    </div>
  </div>
</template>
