import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockApi = {
  get: vi.fn(),
  post: vi.fn(),
}

vi.mock('./useApi', () => ({
  useApi: () => mockApi,
}))

async function setup() {
  const { useAssessments } = await import('./useAssessments')
  return useAssessments()
}

describe('useAssessments', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockApi.get.mockResolvedValue([])
    mockApi.post.mockResolvedValue({})
  })

  it('listAssessments GETs the assessments collection', async () => {
    const assessments = await setup()
    await assessments.listAssessments()
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/assessments')
  })

  it('listAssessments encodes the module query parameter', async () => {
    const assessments = await setup()
    await assessments.listAssessments('mod 42')
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/assessments?module=mod%2042')
  })

  it('getAssessment GETs a single assessment by id', async () => {
    const assessments = await setup()
    await assessments.getAssessment(7)
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/assessments/7')
  })

  it('submitAssessment POSTs the submission to the submit endpoint', async () => {
    const assessments = await setup()
    const submission = {
      assessmentId: 7,
      answers: [{ questionId: 1, selectedOptionId: 'b' }],
      timeTakenSeconds: 120,
    }
    await assessments.submitAssessment(7, submission)
    expect(mockApi.post).toHaveBeenCalledWith('/api/v1/assessments/7/submit', submission)
  })

  it('getMyResults GETs paginated results with default pagination', async () => {
    const assessments = await setup()
    await assessments.getMyResults()
    expect(mockApi.get).toHaveBeenCalledWith(
      '/api/v1/assessments/me/results?limit=10&offset=0',
    )
  })

  it('getMyResults passes through custom pagination', async () => {
    const assessments = await setup()
    await assessments.getMyResults(5, 20)
    expect(mockApi.get).toHaveBeenCalledWith(
      '/api/v1/assessments/me/results?limit=5&offset=20',
    )
  })

  it('returns the API response verbatim', async () => {
    const payload = [{ id: 1, title: 'Radio Comms' }]
    mockApi.get.mockResolvedValue(payload)
    const assessments = await setup()
    await expect(assessments.listAssessments()).resolves.toEqual(payload)
  })
})
