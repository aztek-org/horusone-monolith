/**
 * Instructor API composable — typed wrappers for instructor profile and student management.
 */

// ─── Types ───────────────────────────────────────────────────────────────────

export interface AvailabilitySlot {
  day: 'monday' | 'tuesday' | 'wednesday' | 'thursday' | 'friday' | 'saturday' | 'sunday'
  period: 'am' | 'pm'
  available: boolean
}

export interface InstructorProfile {
  id: string
  user_id: string
  display_name: string
  email: string
  avatar_seed: string
  bio: string
  qualifications: string[]
  certifications: string[]
  specializations: string[]
  availability: AvailabilitySlot[]
  rating: number
  total_students: number
  total_sessions_conducted: number
  organization_id: string | null
  organization_name: string | null
  created_at: string
  updated_at: string
}

export interface InstructorProfileUpdate {
  bio?: string
  qualifications?: string[]
  certifications?: string[]
  specializations?: string[]
  availability?: AvailabilitySlot[]
}

export interface InstructorStudent {
  id: string
  user_id: string
  display_name: string
  email: string
  avatar_seed: string
  flight_hours: number
  scenarios_completed: number
  overall_score: number
  last_active: string | null
  strengths: string[]
  weaknesses: string[]
  recent_sessions: StudentSession[]
}

export interface StudentSession {
  id: string
  scenario_name: string
  score: number
  status: 'completed' | 'active' | 'abandoned'
  started_at: string
  ended_at: string | null
  duration_minutes: number
}

export interface InstructorStats {
  total_students: number
  active_sessions: number
  average_student_score: number
  assessments_created: number
}

export interface RecentSession {
  id: string
  student_name: string
  student_id: string
  scenario_name: string
  score: number
  status: 'completed' | 'active' | 'abandoned'
  started_at: string
  duration_minutes: number
}

export interface SessionEvent {
  id: string
  session_id: number
  user_id: string | null
  org_id: string | null
  event_type: string
  event_payload: Record<string, unknown>
  created_at: string
}

export interface InstructorExchangeResponse {
  session_id: number
  applied: boolean
  atc_response: string
  exchange_count: number
  pending_instructor: boolean
  instructor_overridden: boolean
}

// Live-graph lifecycle events that decide whether an exchange is held. The last
// of these to occur wins: a later response/override clears an earlier hold.
const EXCHANGE_LIFECYCLE_EVENTS = new Set([
  'awaiting_instructor',
  'instructor_override',
  'exchange_completed',
])

/**
 * Whether the session's most recent exchange is held for instructor review.
 *
 * Events are read oldest-first (the API orders them that way); an
 * `awaiting_instructor` is only held if nothing has resolved it since.
 */
export function heldExchangeFromEvents(events: SessionEvent[]): boolean {
  for (let i = events.length - 1; i >= 0; i--) {
    const eventType = events[i]!.event_type
    if (EXCHANGE_LIFECYCLE_EVENTS.has(eventType)) {
      return eventType === 'awaiting_instructor'
    }
  }
  return false
}

// ─── Composable ──────────────────────────────────────────────────────────────

export function useInstructor() {
  const api = useApi()

  // ── Profile ────────────────────────────────────────────────────────────

  function getMyProfile(): Promise<InstructorProfile> {
    return api.get<InstructorProfile>('/api/v1/instructors/me/profile')
  }

  function updateMyProfile(data: InstructorProfileUpdate): Promise<InstructorProfile> {
    return api.put<InstructorProfile>('/api/v1/instructors/me/profile', data)
  }

  function getInstructorProfile(userId: string): Promise<InstructorProfile> {
    return api.get<InstructorProfile>(`/api/v1/instructors/${userId}/profile`)
  }

  function searchInstructors(
    orgId?: string,
    specialization?: string,
    limit?: number,
    offset?: number,
  ): Promise<InstructorProfile[]> {
    const params = new URLSearchParams()
    if (orgId) params.set('org_id', orgId)
    if (specialization) params.set('specialization', specialization)
    if (limit !== undefined) params.set('limit', String(limit))
    if (offset !== undefined) params.set('offset', String(offset))
    const query = params.toString() ? `?${params.toString()}` : ''
    return api.get<InstructorProfile[]>(`/api/v1/instructors/${query}`)
  }

  // ── Students ───────────────────────────────────────────────────────────

  function getMyStudents(): Promise<InstructorStudent[]> {
    return api.get<InstructorStudent[]>('/api/v1/instructors/students')
  }

  function getStudentDetail(studentId: string): Promise<InstructorStudent> {
    return api.get<InstructorStudent>(`/api/v1/instructors/students/${studentId}`)
  }

  // ── Stats & Sessions ──────────────────────────────────────────────────

  function getMyStats(): Promise<InstructorStats> {
    return api.get<InstructorStats>('/api/v1/instructors/stats')
  }

  function getRecentSessions(limit?: number): Promise<RecentSession[]> {
    const query = limit ? `?limit=${limit}` : ''
    return api.get<RecentSession[]>(`/api/v1/instructors/sessions/recent${query}`)
  }

  // ── Held exchanges (HITL) ─────────────────────────────────────────────

  function getSessionEvents(sessionId: string | number): Promise<SessionEvent[]> {
    return api.get<SessionEvent[]>(`/api/v1/sessions/${sessionId}/events`)
  }

  /**
   * Release an exchange held for review.
   *
   * Omit ``instructorResponse`` to release the AI's own answer; pass text to
   * override it. Releasing with nothing pending is a no-op (``applied`` false).
   */
  function respondToHeldExchange(
    sessionId: string | number,
    instructorResponse?: string,
  ): Promise<InstructorExchangeResponse> {
    const body = instructorResponse ? { instructor_response: instructorResponse } : {}
    return api.post<InstructorExchangeResponse>(
      `/api/v1/sessions/${sessionId}/instructor-response`,
      body,
    )
  }

  return {
    // Profile
    getMyProfile,
    updateMyProfile,
    getInstructorProfile,
    searchInstructors,
    // Students
    getMyStudents,
    getStudentDetail,
    // Stats & Sessions
    getMyStats,
    getRecentSessions,
    // Held exchanges (HITL)
    getSessionEvents,
    respondToHeldExchange,
  }
}
