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

// ─── Composable ──────────────────────────────────────────────────────────────

export function useInstructor() {
  const api = useApi()

  // ── Profile ────────────────────────────────────────────────────────────

  function getMyProfile(): Promise<InstructorProfile> {
    return api.get<InstructorProfile>('/api/v1/instructor/profile')
  }

  function updateMyProfile(data: InstructorProfileUpdate): Promise<InstructorProfile> {
    return api.put<InstructorProfile>('/api/v1/instructor/profile', data)
  }

  function getInstructorProfile(userId: string): Promise<InstructorProfile> {
    return api.get<InstructorProfile>(`/api/v1/instructor/profiles/${userId}`)
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
    return api.get<InstructorProfile[]>(`/api/v1/instructor/profiles${query}`)
  }

  // ── Students ───────────────────────────────────────────────────────────

  function getMyStudents(): Promise<InstructorStudent[]> {
    return api.get<InstructorStudent[]>('/api/v1/instructor/students')
  }

  function getStudentDetail(studentId: string): Promise<InstructorStudent> {
    return api.get<InstructorStudent>(`/api/v1/instructor/students/${studentId}`)
  }

  // ── Stats & Sessions ──────────────────────────────────────────────────

  function getMyStats(): Promise<InstructorStats> {
    return api.get<InstructorStats>('/api/v1/instructor/stats')
  }

  function getRecentSessions(limit?: number): Promise<RecentSession[]> {
    const query = limit ? `?limit=${limit}` : ''
    return api.get<RecentSession[]>(`/api/v1/instructor/sessions/recent${query}`)
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
  }
}
