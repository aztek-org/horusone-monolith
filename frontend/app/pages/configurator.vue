<script setup lang="ts">
definePageMeta({
  layout: 'default'
})

const { startSimulation } = useSimulationState()
const router = useRouter()

function handleExecuteSimulation() {
  const missionId = `X-RAY-${String(Math.floor(Math.random() * 1000)).padStart(3, '0')}-ALPHA`
  startSimulation(missionId, 'LAX-TYO-992')
  router.push(`/mission/${missionId}`)
}
</script>

<template>
  <NuxtLayout>
    <template #header>
      <AppHeader title="Route & Scenario Architect" subtitle="TRAINING SYSTEM - HORUS V.0.2-TOKYO">
        <template #action>
          <HButton
            variant="primary"
            size="sm"
            icon="heroicons:play-solid"
            @click="handleExecuteSimulation"
          >
            EXECUTE SIMULATION
          </HButton>
        </template>
      </AppHeader>
    </template>

    <template #sidebar>
      <RouteChecklist />
    </template>

    <template #default>
      <div class="p-4 lg:p-6 space-y-4">
        <!-- Chart Layers -->
        <ChartLayers />

        <!-- Map Visualization -->
        <MapVisualization />
      </div>
    </template>

    <template #panel>
      <AICopilotParams />
    </template>
  </NuxtLayout>
</template>
