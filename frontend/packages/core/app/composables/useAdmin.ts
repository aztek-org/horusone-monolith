/**
 * Admin API composable — typed wrappers for all admin endpoints.
 */

// ─── Types ───────────────────────────────────────────────────────────────────

export interface AdminStats {
  total_organizations: number
  total_users: number
  total_sessions: number
  total_scenarios: number
  active_sessions: number
}

export interface OrganizationSummary {
  id: string
  name: string
  slug: string
  is_active: boolean
  max_seats: number
  created_at: string
  total_seats: number
  active_seats: number
  total_sessions: number
  total_scenarios: number
}

export interface OrganizationCreatePayload {
  name: string
  slug: string
  max_seats: number
}

export interface OrganizationUpdatePayload {
  name?: string
  slug?: string
  max_seats?: number
  is_active?: boolean
}

export interface SeatUser {
  id: string
  email: string
  display_name: string
}

export interface SeatWithUser {
  id: string
  user_id: string
  organization_id: string
  role: string
  is_active: boolean
  joined_at: string
  user: SeatUser
}

export interface SeatCreatePayload {
  email: string
  role: string
}

export interface SeatUpdatePayload {
  role?: string
  is_active?: boolean
}

export interface AdminUser {
  id: string
  email: string
  display_name: string
  is_active: boolean
  created_at: string
}

export interface AdminUserDetail extends AdminUser {
  seats: SeatWithUser[]
}

export interface LeaderboardEntry {
  user_id: string
  display_name: string
  email: string
  completed_sessions: number
  total_voice_logs: number
  total_duration_ms: number
}

export interface SessionsByDay {
  date: string
  count: number
}

export interface PopularScenario {
  scenario_id: string
  name: string
  session_count: number
}

export interface AnalyticsOverview {
  total_sessions: number
  completed_sessions: number
  active_sessions: number
  total_voice_logs: number
  sessions_by_day: SessionsByDay[]
  popular_scenarios: PopularScenario[]
}

export interface TrainingModule {
  id: string
  name: string
  description: string
  difficulty_level: string
  is_published: boolean
  org_id: string | null
  sort_order: number
  created_at: string
  scenario_count?: number
  scenarios?: ModuleScenario[]
}

export interface ModuleCreatePayload {
  name: string
  description: string
  difficulty_level: string
  is_published: boolean
  org_id: string | null
  sort_order: number
}

export interface ModuleUpdatePayload {
  name?: string
  description?: string
  difficulty_level?: string
  is_published?: boolean
  sort_order?: number
}

export interface ModuleScenario {
  scenario_id: string
  name: string
  sort_order: number
}

// ─── Composable ──────────────────────────────────────────────────────────────

export function useAdmin() {
  const api = useApi()

  // ── Platform stats ──────────────────────────────────────────────────────
  function fetchStats(): Promise<AdminStats> {
    return api.get<AdminStats>('/api/v1/admin/stats')
  }

  // ── Organizations ───────────────────────────────────────────────────────
  function fetchOrganizations(): Promise<OrganizationSummary[]> {
    return api.get<OrganizationSummary[]>('/api/v1/admin/organizations/')
  }

  function fetchOrganization(orgId: string): Promise<OrganizationSummary> {
    return api.get<OrganizationSummary>(`/api/v1/admin/organizations/${orgId}`)
  }

  function createOrganization(payload: OrganizationCreatePayload): Promise<OrganizationSummary> {
    return api.post<OrganizationSummary>('/api/v1/admin/organizations/', payload)
  }

  function updateOrganization(orgId: string, payload: OrganizationUpdatePayload): Promise<OrganizationSummary> {
    return api.put<OrganizationSummary>(`/api/v1/admin/organizations/${orgId}`, payload)
  }

  function deleteOrganization(orgId: string): Promise<void> {
    return api.del<void>(`/api/v1/admin/organizations/${orgId}`)
  }

  // ── Seats ───────────────────────────────────────────────────────────────
  function fetchSeats(orgId: string): Promise<SeatWithUser[]> {
    return api.get<SeatWithUser[]>(`/api/v1/admin/organizations/${orgId}/seats`)
  }

  function createSeat(orgId: string, payload: SeatCreatePayload): Promise<SeatWithUser> {
    return api.post<SeatWithUser>(`/api/v1/admin/organizations/${orgId}/seats`, payload)
  }

  function updateSeat(orgId: string, seatId: string, payload: SeatUpdatePayload): Promise<SeatWithUser> {
    return api.put<SeatWithUser>(`/api/v1/admin/organizations/${orgId}/seats/${seatId}`, payload)
  }

  function deleteSeat(orgId: string, seatId: string): Promise<void> {
    return api.del<void>(`/api/v1/admin/organizations/${orgId}/seats/${seatId}`)
  }

  // ── Users ───────────────────────────────────────────────────────────────
  function fetchUsers(search?: string): Promise<AdminUser[]> {
    const query = search ? `?search=${encodeURIComponent(search)}` : ''
    return api.get<AdminUser[]>(`/api/v1/admin/users/${query}`)
  }

  function fetchUser(userId: string): Promise<AdminUserDetail> {
    return api.get<AdminUserDetail>(`/api/v1/admin/users/${userId}`)
  }

  function updateUser(userId: string, payload: { is_active: boolean }): Promise<AdminUser> {
    return api.put<AdminUser>(`/api/v1/admin/users/${userId}`, payload)
  }

  // ── Analytics ───────────────────────────────────────────────────────────
  function fetchLeaderboard(orgId: string): Promise<LeaderboardEntry[]> {
    return api.get<LeaderboardEntry[]>(`/api/v1/analytics/leaderboard?org_id=${encodeURIComponent(orgId)}`)
  }

  function fetchAnalyticsOverview(orgId: string): Promise<AnalyticsOverview> {
    return api.get<AnalyticsOverview>(`/api/v1/analytics/overview?org_id=${encodeURIComponent(orgId)}`)
  }

  // ── Modules ─────────────────────────────────────────────────────────────
  function fetchModules(): Promise<TrainingModule[]> {
    return api.get<TrainingModule[]>('/api/v1/modules/')
  }

  function fetchModule(moduleId: string): Promise<TrainingModule> {
    return api.get<TrainingModule>(`/api/v1/modules/${moduleId}`)
  }

  function createModule(payload: ModuleCreatePayload): Promise<TrainingModule> {
    return api.post<TrainingModule>('/api/v1/modules/', payload)
  }

  function updateModule(moduleId: string, payload: ModuleUpdatePayload): Promise<TrainingModule> {
    return api.put<TrainingModule>(`/api/v1/modules/${moduleId}`, payload)
  }

  function deleteModule(moduleId: string): Promise<void> {
    return api.del<void>(`/api/v1/modules/${moduleId}`)
  }

  function linkScenario(moduleId: string, scenarioId: string, sortOrder: number): Promise<void> {
    return api.post<void>(`/api/v1/modules/${moduleId}/scenarios`, {
      scenario_id: scenarioId,
      sort_order: sortOrder,
    })
  }

  function unlinkScenario(moduleId: string, scenarioId: string): Promise<void> {
    return api.del<void>(`/api/v1/modules/${moduleId}/scenarios/${scenarioId}`)
  }

  return {
    // Stats
    fetchStats,
    // Organizations
    fetchOrganizations,
    fetchOrganization,
    createOrganization,
    updateOrganization,
    deleteOrganization,
    // Seats
    fetchSeats,
    createSeat,
    updateSeat,
    deleteSeat,
    // Users
    fetchUsers,
    fetchUser,
    updateUser,
    // Analytics
    fetchLeaderboard,
    fetchAnalyticsOverview,
    // Modules
    fetchModules,
    fetchModule,
    createModule,
    updateModule,
    deleteModule,
    linkScenario,
    unlinkScenario,
  }
}
