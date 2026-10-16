import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockApi = {
  get: vi.fn(),
}

vi.mock('./useApi', () => ({
  useApi: () => mockApi,
}))

async function setup() {
  const { useStats } = await import('./useStats')
  return useStats()
}

describe('useStats', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  // -- getMyStats -----------------------------------------------------------
  it('getMyStats maps snake_case API fields to camelCase student stats', async () => {
    mockApi.get.mockResolvedValue({
      total_flight_hours: 12.5,
      total_scenarios_completed: 7,
      total_assessments: 3,
      overall_score: 88,
      current_streak: 4,
      best_streak: 9,
      updated_at: '2026-01-02T03:04:05Z',
    })
    const stats = await setup()

    await expect(stats.getMyStats()).resolves.toEqual({
      totalFlightHours: 12.5,
      scenariosCompleted: 7,
      assessmentsTaken: 3,
      overallScore: 88,
      currentStreak: 4,
      longestStreak: 9,
      lastActiveAt: '2026-01-02T03:04:05Z',
    })
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/stats/me')
  })

  // -- getFlightHours -------------------------------------------------------
  it('getFlightHours maps rows and counts practiced maneuvers', async () => {
    mockApi.get.mockResolvedValue([
      {
        id: 'fh-1',
        session_id: 11,
        hours_logged: 1.4,
        maneuvers_practiced: [{ id: 'm1' }, { id: 'm2' }],
        phase: 'DIVERGENCE',
        created_at: '2026-01-01',
      },
    ])
    const stats = await setup()

    const result = await stats.getFlightHours()
    expect(result.items[0]).toEqual({
      id: 'fh-1',
      sessionId: 11,
      date: '2026-01-01',
      hours: 1.4,
      phase: 'DIVERGENCE',
      maneuversCount: 2,
      scenarioName: null,
    })
    expect(mockApi.get).toHaveBeenCalledWith(
      '/api/v1/stats/me/flight-hours?limit=10&offset=0',
    )
  })

  it('getFlightHours reports hasMore when a full page is returned', async () => {
    mockApi.get.mockResolvedValue(
      Array.from({ length: 2 }, (_, i) => ({
        id: `fh-${i}`,
        session_id: null,
        hours_logged: 1,
        maneuvers_practiced: [],
        phase: 'X',
        created_at: '2026-01-01',
      })),
    )
    const stats = await setup()

    const result = await stats.getFlightHours(2, 0)
    expect(result.hasMore).toBe(true)
    expect(result.total).toBe(2)
  })

  // -- getManeuvers ---------------------------------------------------------
  it('getManeuvers normalizes scores and extracts feedback', async () => {
    mockApi.get.mockResolvedValue([
      {
        id: 'man-1',
        session_id: null,
        maneuver_name: 'Power-off stall',
        maneuver_type: 'STALL',
        score: 92,
        created_at: '2026-01-01',
        extra_data: { feedback: 'Nice recovery' },
      },
      {
        id: 'man-2',
        session_id: 3,
        maneuver_name: 'Steep turn',
        maneuver_type: 'TURN',
        score: null,
        created_at: '2026-01-02',
        extra_data: {},
      },
    ])
    const stats = await setup()

    const result = await stats.getManeuvers()
    expect(result.items[0]).toEqual({
      id: 'man-1',
      sessionId: null,
      name: 'Power-off stall',
      type: 'STALL',
      score: 92,
      maxScore: 100,
      date: '2026-01-01',
      feedback: 'Nice recovery',
    })
    expect(result.items[1].score).toBe(0)
    expect(result.items[1].feedback).toBeNull()
    expect(mockApi.get).toHaveBeenCalledWith(
      '/api/v1/stats/me/maneuvers?limit=12&offset=0',
    )
  })

  it('getManeuvers appends the type filter when provided', async () => {
    mockApi.get.mockResolvedValue([])
    const stats = await setup()
    await stats.getManeuvers(5, 10, 'STALL')
    expect(mockApi.get).toHaveBeenCalledWith(
      '/api/v1/stats/me/maneuvers?limit=5&offset=10&type=STALL',
    )
  })

  // -- getAssessmentResults -------------------------------------------------
  it('getAssessmentResults estimates correct answers from the score', async () => {
    mockApi.get.mockResolvedValue([
      {
        id: 'res-1',
        assessment_id: 'abcdef123456',
        score: 80,
        answers: { q1: 'a', q2: 'b', q3: 'c', q4: 'd', q5: 'e' },
        passed: true,
        time_taken_seconds: 300,
        completed_at: '2026-01-03',
      },
    ])
    const stats = await setup()

    const result = await stats.getAssessmentResults()
    expect(result.items[0]).toEqual({
      id: 'res-1',
      assessmentId: 'abcdef123456',
      assessmentTitle: 'Assessment abcdef12',
      module: 'Knowledge Check',
      score: 80,
      maxScore: 100,
      passingScore: 70,
      passed: true,
      completedAt: '2026-01-03',
      timeTakenSeconds: 300,
      questionsCorrect: 4,
      questionsTotal: 5,
      answers: { q1: 'a', q2: 'b', q3: 'c', q4: 'd', q5: 'e' },
    })
    expect(mockApi.get).toHaveBeenCalledWith(
      '/api/v1/stats/me/assessments?limit=10&offset=0',
    )
  })

  it('getAssessmentResults handles an empty answer set', async () => {
    mockApi.get.mockResolvedValue([
      {
        id: 'res-2',
        assessment_id: 'deadbeef',
        score: 55,
        answers: {},
        passed: false,
        time_taken_seconds: null,
        completed_at: '2026-01-04',
      },
    ])
    const stats = await setup()

    const result = await stats.getAssessmentResults()
    expect(result.items[0].questionsTotal).toBe(0)
    expect(result.items[0].questionsCorrect).toBe(0)
    expect(result.items[0].timeTakenSeconds).toBe(0)
  })

  // -- getTranscript --------------------------------------------------------
  it('getTranscript maps voice logs to speaker/message shape', async () => {
    mockApi.get.mockResolvedValue([
      {
        id: 1,
        session_id: 42,
        role: 'pilot',
        transcript: 'Tower, request taxi',
        created_at: '2026-01-05T10:00:00Z',
      },
      {
        id: 2,
        session_id: 42,
        role: 'atc',
        transcript: 'Taxi to runway 22',
        created_at: '2026-01-05T10:00:05Z',
      },
    ])
    const stats = await setup()

    const result = await stats.getTranscript(42)
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/stats/me/transcript/42')
    expect(result).toEqual([
      {
        id: 1,
        sessionId: 42,
        speaker: 'pilot',
        message: 'Tower, request taxi',
        timestamp: '2026-01-05T10:00:00Z',
        audioUrl: null,
      },
      {
        id: 2,
        sessionId: 42,
        speaker: 'atc',
        message: 'Taxi to runway 22',
        timestamp: '2026-01-05T10:00:05Z',
        audioUrl: null,
      },
    ])
  })

  // -- Error propagation ----------------------------------------------------
  it('propagates API errors', async () => {
    mockApi.get.mockRejectedValue({ status: 500, detail: 'boom' })
    const stats = await setup()
    await expect(stats.getMyStats()).rejects.toEqual({ status: 500, detail: 'boom' })
  })
})
