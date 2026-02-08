<script setup lang="ts">
definePageMeta({
  layout: 'mission'
})

const route = useRoute()
const missionId = computed(() => route.params.id as string)
</script>

<template>
  <NuxtLayout name="mission">
    <template #sidebar>
      <div class="space-y-6">
        <MissionChecklist />
        <SystemStatusGrid />
      </div>
    </template>
    
    <template #default>
      <div class="space-y-4">
        <!-- Weather & Decision Matrix Row -->
        <div class="grid gap-4 lg:grid-cols-2">
          <WeatherEcosystem />
          <div class="space-y-4">
            <DecisionMatrix />
            <FlightDynamics />
          </div>
        </div>
      </div>
    </template>
    
    <template #panel>
      <TrainingInterface />
    </template>
  </NuxtLayout>
</template>
