/**
 * State and logic for session track replay.
 * Manages playback of recorded flight tracks with synced insights and transcripts.
 */

export interface TrackPoint {
  index: number
  timestamp: string
  lat: number
  lon: number
  altitude_ft: number
  speed_kts: number
  heading_deg: number
  vertical_speed_fpm: number
  phase: string
  bank_angle: number | null
  pitch_angle: number | null
}

export interface FlightInsight {
  id: string
  timestamp: string
  track_index: number
  category: 'communication' | 'decision' | 'procedure' | 'timing' | 'safety'
  severity: 'info' | 'positive' | 'warning' | 'critical'
  title: string
  message: string
  score_impact: number | null
}

export interface VoiceLog {
  id: string
  timestamp: string
  track_index: number
  speaker: 'pilot' | 'atc' | 'system'
  message: string
  frequency: string | null
  quality_score: number | null
}

export interface SessionScoring {
  overall_score: number
  letter_grade: string
  categories: {
    communication: number
    decisions: number
    procedures: number
    timing: number
  }
  badges: SessionBadge[]
}

export interface SessionBadge {
  id: string
  name: string
  icon: string
  description: string
}

export interface ProvenanceEvent {
  event_type: string
  created_at: string
  graph: string | null
  node: string | null
  scene_version: string | null
  prompt_version: string | null
  llm_provider: string | null
  llm_model: string | null
  llm_fallback_used: boolean | null
  retrieved_chunk_ids: string[]
  instructor_overridden: boolean | null
}

export interface SessionDetail {
  id: number
  scenario_id: number | null
  scenario_name: string
  status: string
  language: string
  started_at: string
  ended_at: string | null
  duration_seconds: number | null
  track_points: TrackPoint[]
  insights: FlightInsight[]
  voice_logs: VoiceLog[]
  scoring: SessionScoring | null
  provenance: ProvenanceEvent[]
}

export interface SessionAuditEvent {
  id: string
  session_id: number
  user_id: string | null
  org_id: string | null
  event_type: string
  event_payload: Record<string, unknown>
  created_at: string
}

type PlaybackSpeed = 1 | 2 | 4 | 8

export function useSessionReplay() {
  const api = useApi()

  // Session data
  const session = ref<SessionDetail | null>(null)
  const trackPoints = ref<TrackPoint[]>([])
  const insights = ref<FlightInsight[]>([])
  const voiceLogs = ref<VoiceLog[]>([])
  const scoring = ref<SessionScoring | null>(null)
  const provenance = ref<ProvenanceEvent[]>([])
  const sessionEvents = ref<SessionAuditEvent[]>([])

  // Playback state
  const isPlaying = ref(false)
  const currentIndex = ref(0)
  const playbackSpeed = ref<PlaybackSpeed>(1)
  const isLoading = ref(false)
  const errorMessage = ref<string | null>(null)

  // Internal timer
  let playbackTimer: ReturnType<typeof setInterval> | null = null

  // Computed: current track point at playback position
  const currentPosition = computed<TrackPoint | null>(() => {
    if (trackPoints.value.length === 0) return null
    const idx = Math.min(currentIndex.value, trackPoints.value.length - 1)
    return trackPoints.value[idx] ?? null
  })

  // Computed: total number of track points
  const totalPoints = computed(() => trackPoints.value.length)

  // Computed: current timestamp
  const currentTimestamp = computed(() => {
    return currentPosition.value?.timestamp ?? ''
  })

  // Computed: progress percentage
  const progress = computed(() => {
    if (totalPoints.value <= 1) return 0
    return (currentIndex.value / (totalPoints.value - 1)) * 100
  })

  // Computed: insights at or before current position
  const visibleInsights = computed(() => {
    return insights.value.filter(i => i.track_index <= currentIndex.value)
  })

  // Computed: voice logs at or before current position
  const visibleVoiceLogs = computed(() => {
    return voiceLogs.value.filter(v => v.track_index <= currentIndex.value)
  })

  // Computed: current voice log (most recent at current position)
  const activeVoiceLog = computed(() => {
    const visible = visibleVoiceLogs.value
    return visible.length > 0 ? visible[visible.length - 1] : null
  })

  /**
   * Load session data including track, insights, and transcripts.
   */
  async function loadSession(sessionId: string | number): Promise<boolean> {
    isLoading.value = true
    errorMessage.value = null
    stop()

    try {
      const [result, events] = await Promise.all([
        api.get<SessionDetail>(`/api/v1/sessions/${sessionId}/replay`),
        api.get<SessionAuditEvent[]>(`/api/v1/sessions/${sessionId}/events`),
      ])

      session.value = result
      trackPoints.value = result.track_points ?? []
      insights.value = result.insights ?? []
      voiceLogs.value = result.voice_logs ?? []
      scoring.value = result.scoring ?? null
      provenance.value = result.provenance ?? []
      sessionEvents.value = events ?? []
      currentIndex.value = 0

      return true
    }
    catch (err) {
      const apiErr = err as { detail?: string }
      errorMessage.value = apiErr.detail ?? 'Failed to load session replay data'
      return false
    }
    finally {
      isLoading.value = false
    }
  }

  /**
   * Start or resume playback.
   */
  function play() {
    if (trackPoints.value.length === 0) return
    if (currentIndex.value >= trackPoints.value.length - 1) {
      // If at end, restart
      currentIndex.value = 0
    }

    isPlaying.value = true
    _startTimer()
  }

  /**
   * Pause playback.
   */
  function pause() {
    isPlaying.value = false
    _stopTimer()
  }

  /**
   * Stop playback and reset to beginning.
   */
  function stop() {
    isPlaying.value = false
    currentIndex.value = 0
    _stopTimer()
  }

  /**
   * Seek to a specific index.
   */
  function seekTo(index: number) {
    currentIndex.value = Math.max(0, Math.min(index, trackPoints.value.length - 1))
  }

  /**
   * Set playback speed multiplier.
   */
  function setSpeed(speed: PlaybackSpeed) {
    playbackSpeed.value = speed
    // Restart timer with new speed if currently playing
    if (isPlaying.value) {
      _stopTimer()
      _startTimer()
    }
  }

  /**
   * Jump to a specific insight by its track index.
   */
  function jumpToInsight(insight: FlightInsight) {
    seekTo(insight.track_index)
  }

  /**
   * Jump to a specific voice log by its track index.
   */
  function jumpToVoiceLog(log: VoiceLog) {
    seekTo(log.track_index)
  }

  /**
   * Internal: start the playback interval.
   * Base rate ~100ms per point, divided by speed.
   */
  function _startTimer() {
    _stopTimer()
    const intervalMs = Math.max(25, 100 / playbackSpeed.value)

    playbackTimer = setInterval(() => {
      if (currentIndex.value >= trackPoints.value.length - 1) {
        pause()
        return
      }
      currentIndex.value++
    }, intervalMs)
  }

  /**
   * Internal: stop the playback interval.
   */
  function _stopTimer() {
    if (playbackTimer !== null) {
      clearInterval(playbackTimer)
      playbackTimer = null
    }
  }

  /**
   * Format duration in seconds to MM:SS.
   */
  function formatDuration(seconds: number | null): string {
    if (seconds === null || seconds === undefined) return '--:--'
    const mins = Math.floor(seconds / 60)
    const secs = Math.floor(seconds % 60)
    return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
  }

  // Cleanup on unmount
  onUnmounted(() => {
    _stopTimer()
  })

  return {
    // Session data
    session: readonly(session),
    trackPoints: readonly(trackPoints),
    insights: readonly(insights),
    voiceLogs: readonly(voiceLogs),
    scoring: readonly(scoring),
    provenance: readonly(provenance),
    sessionEvents: readonly(sessionEvents),

    // Playback state
    isPlaying: readonly(isPlaying),
    currentIndex: readonly(currentIndex),
    playbackSpeed: readonly(playbackSpeed),
    isLoading: readonly(isLoading),
    errorMessage: readonly(errorMessage),

    // Computed
    currentPosition,
    totalPoints,
    currentTimestamp,
    progress,
    visibleInsights,
    visibleVoiceLogs,
    activeVoiceLog,

    // Methods
    loadSession,
    play,
    pause,
    stop,
    seekTo,
    setSpeed,
    jumpToInsight,
    jumpToVoiceLog,
    formatDuration,
  }
}
