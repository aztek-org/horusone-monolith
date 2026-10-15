<script setup lang="ts">
const { flightData } = useFlightData()

const systems = computed(() => [
  { key: 'propulsion', label: 'PROPULSION', status: flightData.value.systems.propulsion },
  { key: 'hydraulics', label: 'HYDRAULICS', status: flightData.value.systems.hydraulics },
  { key: 'electrical', label: 'ELECTRICAL', status: flightData.value.systems.electrical },
  { key: 'pitotStatic', label: 'PITOT STAT', status: flightData.value.systems.pitotStatic },
])

function getStatusValue(status: string) {
  switch (status) {
    case 'nominal': return 'NOMINAL'
    case 'warning': return 'LOAD HI'
    case 'critical': return 'ICING'
    case 'offline': return 'OFFLINE'
    default: return 'UNKNOWN'
  }
}

function getStatusVariant(status: string): 'nominal' | 'warning' | 'critical' | 'offline' {
  return status as 'nominal' | 'warning' | 'critical' | 'offline'
}
</script>

<template>
  <div class="space-y-3">
    <!-- Header -->
    <h3 class="text-xs font-semibold text-horus-text-secondary uppercase tracking-wider">
      SYSTEM STATUS INDICATORS
    </h3>

    <!-- Status Grid -->
    <div class="grid grid-cols-2 gap-2">
      <HStatusIndicator
        v-for="system in systems"
        :key="system.key"
        :label="system.label"
        :value="getStatusValue(system.status)"
        :status="getStatusVariant(system.status)"
      />
    </div>
  </div>
</template>
