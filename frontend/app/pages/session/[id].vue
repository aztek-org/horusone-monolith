<script setup lang="ts">
import type { Map as LeafletMap } from 'leaflet'

definePageMeta({
  layout: false,
  middleware: 'auth',
})

const route = useRoute()
const sessionId = computed(() => route.params.id as string)

const {
  session,
  trackPoints,
  insights,
  voiceLogs,
  scoring,
  isPlaying,
  currentIndex,
  playbackSpeed,
  isLoading,
  errorMessage,
  currentPosition,
  totalPoints,
  currentTimestamp,
  progress,
  visibleInsights,
  visibleVoiceLogs,
  loadSession,
  play,
  pause,
  stop,
  seekTo,
  setSpeed,
  jumpToInsight,
  jumpToVoiceLog,
  formatDuration,
} = useSessionReplay()

// Map refs
const mapContainer = ref<HTMLElement | null>(null)
const map = ref<LeafletMap | null>(null)
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const L = ref<any>(null)
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const aircraftMarker = ref<any>(null)
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const trackLine = ref<any>(null)
// eslint-disable-next-line @typescript-eslint/no-explicit-any
const progressLine = ref<any>(null)

// Insight panel expanded
const showInsightsPanel = ref(true)

// Initialize map once session is loaded
async function initMap() {
  if (!mapContainer.value || trackPoints.value.length === 0) return

  L.value = await import('leaflet')

  const firstPoint = trackPoints.value[0]
  map.value = L.value.map(mapContainer.value, {
    center: [firstPoint.lat, firstPoint.lon],
    zoom: 10,
    zoomControl: false,
    attributionControl: false,
  })

  L.value.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    className: 'map-tiles-dark',
  }).addTo(map.value)

  // Full track line (dimmed)
  const allCoords = trackPoints.value.map(p => [p.lat, p.lon] as [number, number])
  trackLine.value = L.value.polyline(allCoords, {
    color: '#334155',
    weight: 2,
    opacity: 0.5,
  }).addTo(map.value)

  // Progress line (bright)
  progressLine.value = L.value.polyline([], {
    color: '#00d4ff',
    weight: 3,
    opacity: 0.9,
    className: 'track-progress-line',
  }).addTo(map.value)

  // Aircraft marker
  const aircraftIcon = L.value.divIcon({
    className: 'replay-aircraft-marker',
    html: `
      <div class="aircraft-replay-container">
        <div class="aircraft-replay-pulse"></div>
        <svg class="aircraft-replay-icon" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor">
          <path d="M3.478 2.404a.75.75 0 0 0-.926.941l2.432 7.905H13.5a.75.75 0 0 1 0 1.5H4.984l-2.432 7.905a.75.75 0 0 0 .926.94 60.519 60.519 0 0 0 18.445-8.986.75.75 0 0 0 0-1.218A60.517 60.517 0 0 0 3.478 2.404Z" />
        </svg>
      </div>
    `,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  })

  aircraftMarker.value = L.value.marker(
    [firstPoint.lat, firstPoint.lon],
    { icon: aircraftIcon, zIndexOffset: 1000 },
  ).addTo(map.value)

  // Fit map to track
  if (allCoords.length >= 2) {
    const bounds = L.value.latLngBounds(allCoords)
    map.value.fitBounds(bounds, { padding: [40, 40] })
  }
}

// Update aircraft position on playback
watch(currentPosition, (pos) => {
  if (!pos || !aircraftMarker.value || !progressLine.value || !L.value) return

  aircraftMarker.value.setLatLng([pos.lat, pos.lon])

  // Update progress line
  const progressCoords = trackPoints.value
    .slice(0, currentIndex.value + 1)
    .map(p => [p.lat, p.lon] as [number, number])
  progressLine.value.setLatLngs(progressCoords)

  // Pan map to follow aircraft if playing
  if (isPlaying.value && map.value) {
    map.value.panTo([pos.lat, pos.lon], { animate: true, duration: 0.3 })
  }
})

// Letter grade color
function gradeColor(grade: string): string {
  if (grade === 'A' || grade === 'A+') return 'text-horus-status-success'
  if (grade === 'B' || grade === 'B+') return 'text-horus-accent-cyan'
  if (grade === 'C' || grade === 'C+') return 'text-horus-status-warning'
  return 'text-horus-status-danger'
}

function insightSeverityColor(severity: string): string {
  switch (severity) {
    case 'positive': return 'text-horus-status-success'
    case 'info': return 'text-horus-accent-cyan'
    case 'warning': return 'text-horus-status-warning'
    case 'critical': return 'text-horus-status-danger'
    default: return 'text-horus-text-muted'
  }
}

function insightSeverityIcon(severity: string): string {
  switch (severity) {
    case 'positive': return 'heroicons:check-circle-solid'
    case 'info': return 'heroicons:information-circle-solid'
    case 'warning': return 'heroicons:exclamation-triangle-solid'
    case 'critical': return 'heroicons:x-circle-solid'
    default: return 'heroicons:question-mark-circle'
  }
}

function formatSessionDate(iso: string | null): string {
  if (!iso) return '--'
  return new Date(iso).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

function categoryScoreVariant(score: number): 'success' | 'warning' | 'danger' {
  if (score >= 80) return 'success'
  if (score >= 60) return 'warning'
  return 'danger'
}

// Load session data
onMounted(async () => {
  const success = await loadSession(sessionId.value)
  if (success) {
    await nextTick()
    await initMap()
  }
})

onUnmounted(() => {
  stop()
  if (map.value) {
    map.value.remove()
  }
})
</script>

<template>
  <NuxtLayout>
    <template #header>
      <AppHeader
        :title="session?.scenario_name ?? 'Session Replay'"
        subtitle="SESSION HISTORY · TRACK REPLAY"
      >
        <template #action>
          <HButton
            variant="secondary"
            size="sm"
            icon="heroicons:arrow-left"
            @click="$router.push('/performance')"
          >
            Back
          </HButton>
        </template>
      </AppHeader>
    </template>

    <template #sidebar>
      <div class="space-y-4">
        <!-- Session Info -->
        <div v-if="session" class="space-y-3">
          <div class="flex items-center gap-2">
            <Icon name="heroicons:information-circle" class="w-4 h-4 text-horus-accent-cyan" />
            <h2 class="text-xs font-semibold text-horus-text-primary uppercase tracking-wider">
              Session Info
            </h2>
          </div>

          <div class="p-3 rounded-lg bg-horus-bg-tertiary/50 border border-horus-border-subtle space-y-2">
            <div class="flex items-center justify-between">
              <span class="text-xxs text-horus-text-muted uppercase">Status</span>
              <HBadge
                :variant="session.status === 'completed' ? 'success' : session.status === 'active' ? 'active' : 'idle'"
                size="sm"
              >
                {{ session.status }}
              </HBadge>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-xxs text-horus-text-muted uppercase">Date</span>
              <span class="text-xs text-horus-text-primary">{{ formatSessionDate(session.started_at) }}</span>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-xxs text-horus-text-muted uppercase">Duration</span>
              <span class="text-xs font-mono text-horus-text-primary">{{ formatDuration(session.duration_seconds) }}</span>
            </div>
            <div class="flex items-center justify-between">
              <span class="text-xxs text-horus-text-muted uppercase">Track Points</span>
              <span class="text-xs font-mono text-horus-text-primary">{{ trackPoints.length }}</span>
            </div>
          </div>
        </div>

        <!-- Flight Data at Current Position -->
        <div v-if="currentPosition" class="space-y-3">
          <div class="flex items-center gap-2">
            <Icon name="heroicons:paper-airplane" class="w-4 h-4 text-horus-accent-cyan" />
            <h2 class="text-xs font-semibold text-horus-text-primary uppercase tracking-wider">
              Flight Data
            </h2>
          </div>

          <div class="grid grid-cols-2 gap-2">
            <HStatusIndicator
              status="nominal"
              label="Altitude"
              :value="`${currentPosition.altitude_ft.toLocaleString()} ft`"
              size="sm"
            />
            <HStatusIndicator
              status="nominal"
              label="Speed"
              :value="`${currentPosition.speed_kts} kts`"
              size="sm"
            />
            <HStatusIndicator
              status="nominal"
              label="Heading"
              :value="`${currentPosition.heading_deg}°`"
              size="sm"
            />
            <HStatusIndicator
              :status="Math.abs(currentPosition.vertical_speed_fpm) > 1000 ? 'warning' : 'nominal'"
              label="V/S"
              :value="`${currentPosition.vertical_speed_fpm > 0 ? '+' : ''}${currentPosition.vertical_speed_fpm} fpm`"
              size="sm"
            />
          </div>

          <!-- Phase -->
          <div class="p-2 rounded bg-horus-bg-tertiary/50 border border-horus-border-subtle">
            <span class="text-xxs text-horus-text-muted uppercase tracking-wider">Phase</span>
            <p class="text-sm font-semibold text-horus-accent-cyan uppercase">
              {{ currentPosition.phase }}
            </p>
          </div>
        </div>
      </div>
    </template>

    <template #default>
      <div class="p-4 lg:p-6 space-y-4">
        <!-- Loading -->
        <div v-if="isLoading" class="flex items-center justify-center py-16">
          <div class="text-center space-y-3">
            <Icon name="svg-spinners:ring-resize" class="w-8 h-8 text-horus-accent-cyan mx-auto" />
            <p class="text-sm text-horus-text-muted">Loading session replay...</p>
          </div>
        </div>

        <!-- Error -->
        <div
          v-else-if="errorMessage"
          class="flex flex-col items-center justify-center py-16 text-center"
        >
          <Icon name="heroicons:exclamation-triangle" class="w-12 h-12 text-horus-status-danger mb-4 opacity-60" />
          <p class="text-sm text-horus-status-danger mb-3">{{ errorMessage }}</p>
          <HButton variant="secondary" size="sm" @click="$router.push('/performance')">
            Back to Performance
          </HButton>
        </div>

        <template v-else>
          <!-- Map with Track Replay -->
          <HCard variant="glass" padding="none" class="relative overflow-hidden">
            <div
              ref="mapContainer"
              class="w-full aspect-[16/9] min-h-[300px] lg:min-h-[400px]"
            />

            <!-- Playback overlay on map -->
            <div class="absolute bottom-0 left-0 right-0 z-10 p-4 bg-gradient-to-t from-horus-bg-primary/90 to-transparent">
              <TrackReplayControls
                :is-playing="isPlaying"
                :current-index="currentIndex"
                :total-points="totalPoints"
                :speed="playbackSpeed"
                :current-timestamp="currentTimestamp"
                :progress="progress"
                @play="play"
                @pause="pause"
                @stop="stop"
                @seek="seekTo"
                @speed-change="setSpeed"
              />
            </div>
          </HCard>

          <!-- Insights Timeline -->
          <HCard variant="default" padding="md">
            <div class="space-y-3">
              <button
                class="flex items-center gap-2 w-full text-left"
                @click="showInsightsPanel = !showInsightsPanel"
              >
                <Icon name="heroicons:light-bulb" class="w-4 h-4 text-horus-accent-cyan" />
                <span class="text-xs font-semibold text-horus-text-primary uppercase tracking-wider flex-1">
                  Flight Insights
                </span>
                <HBadge variant="info" size="sm">{{ insights.length }}</HBadge>
                <Icon
                  name="heroicons:chevron-down-20-solid"
                  :class="['w-4 h-4 text-horus-text-muted transition-transform duration-200', !showInsightsPanel && '-rotate-90']"
                />
              </button>

              <div v-show="showInsightsPanel" class="space-y-2">
                <div v-if="insights.length === 0" class="text-center py-4">
                  <p class="text-xs text-horus-text-muted">No insights recorded</p>
                </div>

                <button
                  v-for="insight in insights"
                  :key="insight.id"
                  :class="[
                    'w-full text-left p-3 rounded-lg border transition-all',
                    insight.track_index <= currentIndex
                      ? 'bg-horus-bg-tertiary/50 border-horus-border-subtle'
                      : 'bg-horus-bg-primary/30 border-horus-border-subtle/50 opacity-50',
                  ]"
                  @click="jumpToInsight(insight)"
                >
                  <div class="flex items-center gap-2 mb-1">
                    <Icon
                      :name="insightSeverityIcon(insight.severity)"
                      :class="['w-4 h-4', insightSeverityColor(insight.severity)]"
                    />
                    <span class="text-xs font-semibold text-horus-text-primary">{{ insight.title }}</span>
                    <HBadge variant="default" size="sm">{{ insight.category }}</HBadge>
                  </div>
                  <p class="text-xs text-horus-text-secondary pl-6">{{ insight.message }}</p>
                </button>
              </div>
            </div>
          </HCard>

          <!-- Scoring Section -->
          <div v-if="scoring" class="space-y-4">
            <h2 class="text-sm font-semibold text-horus-text-primary uppercase tracking-wider flex items-center gap-2">
              <Icon name="heroicons:trophy" class="w-5 h-5 text-horus-status-warning" />
              Session Scoring
            </h2>

            <div class="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
              <!-- Overall Score -->
              <HCard variant="elevated" padding="lg" class="text-center md:col-span-2 lg:col-span-1">
                <div class="space-y-2">
                  <p class="text-xxs text-horus-text-muted uppercase tracking-wider">Overall Score</p>
                  <p class="text-5xl font-bold font-mono text-horus-accent-cyan">
                    {{ scoring.overall_score }}
                  </p>
                  <p :class="['text-2xl font-bold', gradeColor(scoring.letter_grade)]">
                    {{ scoring.letter_grade }}
                  </p>
                </div>
              </HCard>

              <!-- Category Scores -->
              <HCard variant="default" padding="md" class="md:col-span-2 lg:col-span-2">
                <div class="space-y-3">
                  <p class="text-xxs text-horus-text-muted uppercase tracking-wider">Categories</p>

                  <div class="space-y-2">
                    <div class="flex items-center gap-3">
                      <span class="text-xs text-horus-text-secondary w-28">Communication</span>
                      <div class="flex-1">
                        <HProgress
                          :value="scoring.categories.communication"
                          :variant="categoryScoreVariant(scoring.categories.communication)"
                          size="sm"
                        />
                      </div>
                    </div>
                    <div class="flex items-center gap-3">
                      <span class="text-xs text-horus-text-secondary w-28">Decisions</span>
                      <div class="flex-1">
                        <HProgress
                          :value="scoring.categories.decisions"
                          :variant="categoryScoreVariant(scoring.categories.decisions)"
                          size="sm"
                        />
                      </div>
                    </div>
                    <div class="flex items-center gap-3">
                      <span class="text-xs text-horus-text-secondary w-28">Procedures</span>
                      <div class="flex-1">
                        <HProgress
                          :value="scoring.categories.procedures"
                          :variant="categoryScoreVariant(scoring.categories.procedures)"
                          size="sm"
                        />
                      </div>
                    </div>
                    <div class="flex items-center gap-3">
                      <span class="text-xs text-horus-text-secondary w-28">Timing</span>
                      <div class="flex-1">
                        <HProgress
                          :value="scoring.categories.timing"
                          :variant="categoryScoreVariant(scoring.categories.timing)"
                          size="sm"
                        />
                      </div>
                    </div>
                  </div>
                </div>
              </HCard>

              <!-- Badges -->
              <HCard variant="default" padding="md">
                <div class="space-y-3">
                  <p class="text-xxs text-horus-text-muted uppercase tracking-wider">Badges Earned</p>

                  <div v-if="scoring.badges.length === 0" class="text-center py-4">
                    <Icon name="heroicons:star" class="w-6 h-6 text-horus-text-muted mx-auto mb-1 opacity-50" />
                    <p class="text-xxs text-horus-text-muted">No badges this session</p>
                  </div>

                  <div v-else class="space-y-2">
                    <div
                      v-for="badge in scoring.badges"
                      :key="badge.id"
                      class="flex items-center gap-2 p-2 rounded bg-horus-status-warning/10 border border-horus-status-warning/20"
                    >
                      <span class="text-lg">{{ badge.icon }}</span>
                      <div>
                        <p class="text-xs font-semibold text-horus-status-warning">{{ badge.name }}</p>
                        <p class="text-xxs text-horus-text-muted">{{ badge.description }}</p>
                      </div>
                    </div>
                  </div>
                </div>
              </HCard>
            </div>

            <!-- Export -->
            <div class="flex justify-end">
              <HButton
                variant="secondary"
                size="sm"
                icon="heroicons:document-arrow-down"
              >
                Export Report (PDF)
              </HButton>
            </div>
          </div>
        </template>
      </div>
    </template>

    <template #panel>
      <!-- Voice Transcript -->
      <div class="h-full flex flex-col">
        <TranscriptTimeline
          :voice-logs="voiceLogs"
          :current-timestamp="currentTimestamp"
          :current-index="currentIndex"
          @jump-to="jumpToVoiceLog"
        />
      </div>
    </template>
  </NuxtLayout>
</template>

<style scoped>
:deep(.map-tiles-dark) {
  filter: brightness(0.6) contrast(1.2) saturate(0.7) hue-rotate(10deg);
}

:deep(.track-progress-line) {
  filter: drop-shadow(0 0 4px rgba(0, 212, 255, 0.6));
}

:deep(.replay-aircraft-marker) {
  background: transparent;
  border: none;
}

:deep(.aircraft-replay-container) {
  position: relative;
  width: 28px;
  height: 28px;
}

:deep(.aircraft-replay-icon) {
  width: 28px;
  height: 28px;
  color: #00d4ff;
  filter: drop-shadow(0 0 6px rgba(0, 212, 255, 0.8));
  transform: rotate(45deg);
  position: relative;
  z-index: 2;
}

:deep(.aircraft-replay-pulse) {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: rgba(0, 212, 255, 0.2);
  animation: replayPing 1.5s cubic-bezier(0, 0, 0.2, 1) infinite;
  z-index: 1;
}

@keyframes replayPing {
  0% {
    transform: translate(-50%, -50%) scale(1);
    opacity: 1;
  }
  75%, 100% {
    transform: translate(-50%, -50%) scale(1.8);
    opacity: 0;
  }
}
</style>
