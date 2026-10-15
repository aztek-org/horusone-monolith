import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockApi = {
  get: vi.fn(),
  post: vi.fn(),
}

vi.mock('./useApi', () => ({
  useApi: () => mockApi,
}))

async function setup() {
  const { useGamification } = await import('./useGamification')
  return useGamification()
}

describe('useGamification', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockApi.get.mockResolvedValue([])
    mockApi.post.mockResolvedValue([])
  })

  it('getAllBadges GETs the badges collection without a category filter', async () => {
    const game = await setup()
    await game.getAllBadges()
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/gamification/badges')
  })

  it('getAllBadges encodes the category filter', async () => {
    const game = await setup()
    await game.getAllBadges('flight')
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/gamification/badges?category=flight')
  })

  it('getMyBadges GETs the current user awards', async () => {
    const game = await setup()
    await game.getMyBadges()
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/gamification/me/badges')
  })

  it('getBadgeProgress GETs the current user progress', async () => {
    const game = await setup()
    await game.getBadgeProgress()
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/gamification/me/badges/progress')
  })

  it('checkBadges POSTs to the check endpoint', async () => {
    const game = await setup()
    await game.checkBadges()
    expect(mockApi.post).toHaveBeenCalledWith('/api/v1/gamification/check')
  })

  it('getLeaderboard GETs the leaderboard with no params', async () => {
    const game = await setup()
    await game.getLeaderboard()
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/gamification/leaderboard')
  })

  it('getLeaderboard serializes all provided filters in order', async () => {
    const game = await setup()
    await game.getLeaderboard('weekly', 'org-1', 'communication', 10, 20)
    expect(mockApi.get).toHaveBeenCalledWith(
      '/api/v1/gamification/leaderboard?period=weekly&org_id=org-1&category=communication&limit=10&offset=20',
    )
  })

  it('getLeaderboard omits undefined filters', async () => {
    const game = await setup()
    await game.getLeaderboard(undefined, undefined, undefined, 5)
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/gamification/leaderboard?limit=5')
  })
})
