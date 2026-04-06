/**
 * Typed API client composable for student statistics endpoints.
 * Provides methods to fetch flight hours, maneuvers, assessment results, and transcripts.
 */

export interface StudentStats {
  totalFlightHours: number
  scenariosCompleted: number
  assessmentsTaken: number
  overallScore: number
  currentStreak: number
  longestStreak: number
  lastActiveAt: string | null
}

export interface FlightHourLog {
  id: string
  sessionId: number | null
  date: string
  hours: number
  phase: string
  maneuversCount: number
  scenarioName: string | null
}

export interface ManeuverLog {
  id: string
  sessionId: number | null
  name: string
  type: string
  score: number
  maxScore: number
  date: string
  feedback: string | null
}

export interface StatsAssessmentResult {
  id: string
  assessmentId: string
  assessmentTitle: string
  module: string
  score: number
  maxScore: number
  passingScore: number
  passed: boolean
  completedAt: string
  timeTakenSeconds: number
  questionsCorrect: number
  questionsTotal: number
  answers: Record<string, unknown>
}

export interface StatsVoiceLog {
  id: number
  sessionId: number
  speaker: 'pilot' | 'atc'
  message: string
  timestamp: string
  audioUrl: string | null
}

interface PaginatedResponse<T> {
  items: T[]
  total: number
  hasMore: boolean
}

interface ApiStudentStats {
  total_flight_hours: number
  total_scenarios_completed: number
  total_assessments: number
  overall_score: number
  current_streak: number
  best_streak: number
  updated_at: string
}

interface ApiFlightHourLog {
  id: string
  session_id: number | null
  hours_logged: number
  maneuvers_practiced: unknown[]
  phase: string
  created_at: string
}

interface ApiManeuverLog {
  id: string
  session_id: number | null
  maneuver_name: string
  maneuver_type: string
  score: number | null
  created_at: string
  extra_data: Record<string, unknown>
}

interface ApiAssessmentResult {
  id: string
  assessment_id: string
  score: number
  answers: Record<string, unknown>
  passed: boolean
  time_taken_seconds: number | null
  completed_at: string
}

interface ApiVoiceLog {
  id: number
  session_id: number
  role: 'pilot' | 'atc'
  transcript: string
  created_at: string
}

function toPaginatedResponse<T>(
  items: T[],
  limit: number,
  offset: number,
): PaginatedResponse<T> {
  return {
    items,
    total: offset + items.length,
    hasMore: items.length === limit,
  }
}

function toStudentStats(raw: ApiStudentStats): StudentStats {
  return {
    totalFlightHours: raw.total_flight_hours,
    scenariosCompleted: raw.total_scenarios_completed,
    assessmentsTaken: raw.total_assessments,
    overallScore: raw.overall_score,
    currentStreak: raw.current_streak,
    longestStreak: raw.best_streak,
    lastActiveAt: raw.updated_at,
  }
}

function toFlightHourLog(raw: ApiFlightHourLog): FlightHourLog {
  return {
    id: raw.id,
    sessionId: raw.session_id,
    date: raw.created_at,
    hours: raw.hours_logged,
    phase: raw.phase,
    maneuversCount: raw.maneuvers_practiced.length,
    scenarioName: null,
  }
}

function toManeuverLog(raw: ApiManeuverLog): ManeuverLog {
  const feedback = raw.extra_data.feedback
  return {
    id: raw.id,
    sessionId: raw.session_id,
    name: raw.maneuver_name,
    type: raw.maneuver_type,
    score: raw.score ?? 0,
    maxScore: 100,
    date: raw.created_at,
    feedback: typeof feedback === 'string' ? feedback : null,
  }
}

function toAssessmentResult(raw: ApiAssessmentResult): StatsAssessmentResult {
  const questionsTotal = Object.keys(raw.answers ?? {}).length
  const estimatedCorrect = questionsTotal > 0
    ? Math.round((raw.score / 100) * questionsTotal)
    : 0

  return {
    id: raw.id,
    assessmentId: raw.assessment_id,
    assessmentTitle: `Assessment ${raw.assessment_id.slice(0, 8)}`,
    module: 'Knowledge Check',
    score: raw.score,
    maxScore: 100,
    passingScore: 70,
    passed: raw.passed,
    completedAt: raw.completed_at,
    timeTakenSeconds: raw.time_taken_seconds ?? 0,
    questionsCorrect: Math.max(0, Math.min(questionsTotal, estimatedCorrect)),
    questionsTotal,
    answers: raw.answers,
  }
}

function toVoiceLog(raw: ApiVoiceLog): StatsVoiceLog {
  return {
    id: raw.id,
    sessionId: raw.session_id,
    speaker: raw.role,
    message: raw.transcript,
    timestamp: raw.created_at,
    audioUrl: null,
  }
}

export function useStats() {
  const api = useApi()

  async function getMyStats(): Promise<StudentStats> {
    const raw = await api.get<ApiStudentStats>('/api/v1/stats/me')
    return toStudentStats(raw)
  }

  async function getFlightHours(
    limit = 10,
    offset = 0,
  ): Promise<PaginatedResponse<FlightHourLog>> {
    const raw = await api.get<ApiFlightHourLog[]>(
      `/api/v1/stats/me/flight-hours?limit=${limit}&offset=${offset}`,
    )
    return toPaginatedResponse(raw.map(toFlightHourLog), limit, offset)
  }

  async function getManeuvers(
    limit = 12,
    offset = 0,
    type?: string,
  ): Promise<PaginatedResponse<ManeuverLog>> {
    const params = new URLSearchParams({
      limit: String(limit),
      offset: String(offset),
    })
    if (type) params.set('type', type)
    const raw = await api.get<ApiManeuverLog[]>(
      `/api/v1/stats/me/maneuvers?${params.toString()}`,
    )
    return toPaginatedResponse(raw.map(toManeuverLog), limit, offset)
  }

  async function getAssessmentResults(
    limit = 10,
    offset = 0,
  ): Promise<PaginatedResponse<StatsAssessmentResult>> {
    const raw = await api.get<ApiAssessmentResult[]>(
      `/api/v1/stats/me/assessments?limit=${limit}&offset=${offset}`,
    )
    return toPaginatedResponse(raw.map(toAssessmentResult), limit, offset)
  }

  async function getTranscript(sessionId: number): Promise<StatsVoiceLog[]> {
    const raw = await api.get<ApiVoiceLog[]>(`/api/v1/stats/me/transcript/${sessionId}`)
    return raw.map(toVoiceLog)
  }

  return {
    getMyStats,
    getFlightHours,
    getManeuvers,
    getAssessmentResults,
    getTranscript,
  }
}
