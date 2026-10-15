<script setup lang="ts">
const { weather, precipLevels } = useWeatherData()
</script>

<template>
  <HCard
    variant="default"
    padding="md"
    class="space-y-4"
  >
    <!-- Header -->
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-2">
        <Icon
          name="heroicons:cloud"
          class="w-5 h-5 text-horus-accent-cyan"
        />
        <h3 class="text-sm font-semibold text-horus-text-primary">
          WEATHER ECOSYSTEM
        </h3>
      </div>
      <div class="flex items-center gap-2">
        <HBadge
          variant="active"
          size="sm"
          :pulse="true"
        >
          LIVE FEED
        </HBadge>
        <span class="text-xxs text-horus-text-muted">LAST UPDATE: {{ weather.lastUpdate }}</span>
      </div>
    </div>

    <!-- METAR Data -->
    <div class="space-y-3">
      <div
        v-for="metar in weather.metar"
        :key="metar.station"
        class="p-3 rounded-lg bg-horus-bg-secondary/50 border border-horus-border-subtle"
      >
        <div class="flex items-center justify-between mb-2">
          <span class="text-xxs font-semibold text-horus-text-muted">{{ metar.station }}</span>
        </div>
        <p class="text-xs font-mono text-horus-text-secondary leading-relaxed break-all">
          {{ metar.raw }}
        </p>
      </div>
    </div>

    <!-- Radar Display (Simulated) -->
    <div class="relative aspect-video bg-horus-bg-secondary/50 rounded-lg overflow-hidden border border-horus-border-subtle">
      <!-- Radar Grid -->
      <div class="absolute inset-0 grid-overlay opacity-50" />

      <!-- Simulated Weather Cells -->
      <div class="absolute inset-0 flex items-center justify-center">
        <div class="relative w-32 h-32">
          <!-- Weather cell gradient -->
          <div class="absolute inset-0 rounded-full bg-gradient-radial from-horus-status-danger/60 via-horus-status-warning/40 to-transparent animate-pulse" />
          <div class="absolute inset-4 rounded-full bg-gradient-radial from-horus-status-danger/80 via-horus-status-danger/40 to-transparent" />
        </div>
      </div>

      <!-- Range Indicator -->
      <div class="absolute bottom-2 left-2 text-xxs font-mono text-horus-accent-cyan">
        RADAR RANGE: <span class="text-horus-text-primary">{{ weather.radarRange }} NM</span>
      </div>
    </div>

    <!-- Precipitation Legend -->
    <div class="flex items-center justify-between">
      <span class="text-xxs text-horus-text-muted uppercase">PRECIP DBZ</span>
      <div class="flex items-center gap-3">
        <div
          v-for="level in precipLevels"
          :key="level.value"
          class="flex items-center gap-1.5"
        >
          <span :class="['w-3 h-3 rounded-sm', level.color]" />
          <span class="text-xxs text-horus-text-muted">{{ level.label }}</span>
        </div>
      </div>
    </div>
  </HCard>
</template>
