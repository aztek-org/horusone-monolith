<script setup lang="ts">
const { flightData } = useFlightData()

const fuelPercentage = computed(() => {
  const maxFuel = 20000 // Approximate max fuel capacity
  return Math.round((flightData.value.fuel.onBoard / maxFuel) * 100)
})
</script>

<template>
  <HCard
    variant="default"
    padding="md"
    class="space-y-4"
  >
    <!-- Header -->
    <div class="flex items-center gap-2">
      <Icon
        name="heroicons:chart-bar"
        class="w-5 h-5 text-horus-accent-cyan"
      />
      <h3 class="text-sm font-semibold text-horus-text-primary">
        FLIGHT DYNAMICS
      </h3>
    </div>

    <!-- Metrics Grid -->
    <div class="grid grid-cols-2 gap-4">
      <!-- Airspeed -->
      <div class="space-y-1">
        <HDataPanel
          :value="flightData.airspeed.value"
          :unit="flightData.airspeed.unit"
          label="AIRSPEED"
          :trend="flightData.airspeed.trend"
          :trend-value="flightData.airspeed.trendValue"
          variant="default"
        />
      </div>

      <!-- Trend -->
      <div class="flex items-end justify-end">
        <div class="text-right">
          <span class="text-xxs text-horus-text-muted uppercase">TREND</span>
          <div class="flex items-center gap-1 mt-1">
            <Icon
              :name="flightData.airspeed.trend === 'down' ? 'heroicons:arrow-trending-down' : 'heroicons:arrow-trending-up'"
              :class="[
                'w-5 h-5',
                flightData.airspeed.trend === 'down' ? 'text-horus-status-danger' : 'text-horus-status-success',
              ]"
            />
            <span
              :class="[
                'text-sm font-mono',
                flightData.airspeed.trend === 'down' ? 'text-horus-status-danger' : 'text-horus-status-success',
              ]"
            >
              {{ flightData.airspeed.trendValue }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Altitude -->
    <div class="pt-3 border-t border-horus-border-subtle">
      <div class="flex items-end justify-between">
        <HDataPanel
          :value="flightData.altitude.value.toLocaleString()"
          :unit="flightData.altitude.unit"
          label="ALTITUDE"
          variant="large"
        />
        <div class="text-right">
          <span class="text-xxs text-horus-text-muted uppercase">VERTICAL SPD</span>
          <div class="flex items-center gap-1 mt-1">
            <Icon
              name="heroicons:arrow-up-right"
              class="w-4 h-4 text-horus-status-success"
            />
            <span class="text-sm font-mono text-horus-status-success">
              +{{ flightData.altitude.verticalSpeed }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Fuel -->
    <div class="pt-3 border-t border-horus-border-subtle space-y-2">
      <div class="flex items-end justify-between">
        <HDataPanel
          :value="flightData.fuel.onBoard.toLocaleString()"
          :unit="flightData.fuel.unit"
          label="FUEL ON BOARD"
          variant="default"
          highlight
        />
        <div class="text-right">
          <span class="text-xxs text-horus-text-muted">BURN RATE</span>
          <p class="text-sm font-mono text-horus-text-secondary">
            {{ flightData.fuel.burnRate }}/H
          </p>
        </div>
      </div>

      <!-- Fuel Bar -->
      <div class="h-2 bg-horus-bg-secondary rounded-full overflow-hidden">
        <div
          class="h-full bg-gradient-to-r from-horus-accent-cyan to-horus-status-info rounded-full transition-all"
          :style="{ width: `${fuelPercentage}%` }"
        />
      </div>
    </div>
  </HCard>
</template>
