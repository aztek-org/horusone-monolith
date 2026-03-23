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
  id: number
  sessionId: number
  date: string
  hours: number
  phase: string
  maneuversCount: number
  scenarioName: string | null
}

export interface ManeuverLog {
  id: number
  sessionId: number
  name: string
  type: string
  score: number
  maxScore: number
  date: string
  feedback: string | null
}

export interface StatsAssessmentResult {
  id: number
  assessmentId: number
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

export function useStats() {
  const api = useApi()

  async function getMyStats(): Promise<StudentStats> {
    return api.get<StudentStats>('/api/v1/stats/me')
  }

  async function getFlightHours(
    limit = 10,
    offset = 0,
  ): Promise<PaginatedResponse<FlightHourLog>> {
    return api.get<PaginatedResponse<FlightHourLog>>(
      `/api/v1/stats/flight-hours?limit=${limit}&offset=${offset}`,
    )
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
    return api.get<PaginatedResponse<ManeuverLog>>(
      `/api/v1/stats/maneuvers?${params.toString()}`,
    )
  }

  async function getAssessmentResults(
    limit = 10,
    offset = 0,
  ): Promise<PaginatedResponse<StatsAssessmentResult>> {
    return api.get<PaginatedResponse<StatsAssessmentResult>>(
      `/api/v1/stats/assessment-results?limit=${limit}&offset=${offset}`,
    )
  }

  async function getTranscript(sessionId: number): Promise<StatsVoiceLog[]> {
    return api.get<StatsVoiceLog[]>(`/api/v1/stats/transcripts/${sessionId}`)
  }

  return {
    getMyStats,
    getFlightHours,
    getManeuvers,
    getAssessmentResults,
    getTranscript,
  }
}
