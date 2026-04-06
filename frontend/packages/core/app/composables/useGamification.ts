/**
 * Gamification API composable — typed wrappers for badge and leaderboard endpoints.
 */

// ─── Types ───────────────────────────────────────────────────────────────────

export type BadgeTier = 'bronze' | 'silver' | 'gold' | 'platinum'
export type BadgeCategory = 'flight' | 'communication' | 'knowledge' | 'streak' | 'achievement'

export interface Badge {
  id: string
  name: string
  description: string
  icon: string
  tier: BadgeTier
  category: BadgeCategory
  criteria_description: string
  criteria_value: number
  sort_order: number
}

export interface UserBadge {
  id: string
  badge_id: string
  user_id: string
  earned_at: string
  badge: Badge
}

export interface LeaderboardEntry {
  rank: number
  user_id: string
  display_name: string
  email: string
  avatar_seed: string
  total_score: number
  flight_hours: number
  scenarios_completed: number
  badges_count: number
  category_scores: {
    communication: number
    decision_making: number
    procedures: number
  }
}

export interface BadgeProgress {
  badge_id: string
  badge: Badge
  current_value: number
  target_value: number
  progress_percent: number
}

export type LeaderboardPeriod = 'daily' | 'weekly' | 'monthly' | 'all_time'
export type LeaderboardCategory = 'overall' | 'communication' | 'decision_making' | 'procedures'

// ─── Composable ──────────────────────────────────────────────────────────────

export function useGamification() {
  const api = useApi()

  // ── Badges ─────────────────────────────────────────────────────────────

  function getAllBadges(category?: BadgeCategory): Promise<Badge[]> {
    const query = category ? `?category=${encodeURIComponent(category)}` : ''
    return api.get<Badge[]>(`/api/v1/gamification/badges${query}`)
  }

  function getMyBadges(): Promise<UserBadge[]> {
    return api.get<UserBadge[]>('/api/v1/gamification/badges/me')
  }

  function getBadgeProgress(): Promise<BadgeProgress[]> {
    return api.get<BadgeProgress[]>('/api/v1/gamification/badges/me/progress')
  }

  function checkBadges(): Promise<void> {
    return api.post<void>('/api/v1/gamification/badges/check')
  }

  // ── Leaderboard ────────────────────────────────────────────────────────

  function getLeaderboard(
    period?: LeaderboardPeriod,
    orgId?: string,
    category?: LeaderboardCategory,
    limit?: number,
    offset?: number,
  ): Promise<LeaderboardEntry[]> {
    const params = new URLSearchParams()
    if (period) params.set('period', period)
    if (orgId) params.set('org_id', orgId)
    if (category) params.set('category', category)
    if (limit !== undefined) params.set('limit', String(limit))
    if (offset !== undefined) params.set('offset', String(offset))
    const query = params.toString() ? `?${params.toString()}` : ''
    return api.get<LeaderboardEntry[]>(`/api/v1/gamification/leaderboard${query}`)
  }

  return {
    getAllBadges,
    getMyBadges,
    getBadgeProgress,
    checkBadges,
    getLeaderboard,
  }
}
