import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockApi = {
  get: vi.fn(),
  put: vi.fn(),
}

vi.mock('./useApi', () => ({
  useApi: () => mockApi,
}))

async function setup() {
  const { useInstructor } = await import('./useInstructor')
  return useInstructor()
}

describe('useInstructor', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockApi.get.mockResolvedValue([])
    mockApi.put.mockResolvedValue({})
  })

  it('getMyProfile GETs the current instructor profile', async () => {
    const instructor = await setup()
    await instructor.getMyProfile()
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/instructors/me/profile')
  })

  it('updateMyProfile PUTs the update payload', async () => {
    const instructor = await setup()
    const update = { bio: 'CFI since 2010' }
    await instructor.updateMyProfile(update)
    expect(mockApi.put).toHaveBeenCalledWith('/api/v1/instructors/me/profile', update)
  })

  it('getInstructorProfile GETs another instructor by user id', async () => {
    const instructor = await setup()
    await instructor.getInstructorProfile('user-9')
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/instructors/user-9/profile')
  })

  it('searchInstructors builds encoded search params', async () => {
    const instructor = await setup()
    await instructor.searchInstructors('org-1', 'IFR', 10, 20)
    expect(mockApi.get).toHaveBeenCalledWith(
      '/api/v1/instructors/?org_id=org-1&specialization=IFR&limit=10&offset=20',
    )
  })

  it('searchInstructors with no filters requests the bare collection', async () => {
    const instructor = await setup()
    await instructor.searchInstructors()
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/instructors/')
  })

  it('getMyStudents GETs the students collection', async () => {
    const instructor = await setup()
    await instructor.getMyStudents()
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/instructors/students')
  })

  it('getStudentDetail GETs a single student', async () => {
    const instructor = await setup()
    await instructor.getStudentDetail('student-4')
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/instructors/students/student-4')
  })

  it('getMyStats GETs the instructor stats endpoint', async () => {
    const instructor = await setup()
    await instructor.getMyStats()
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/instructors/stats')
  })

  it('getRecentSessions GETs recent sessions with no limit', async () => {
    const instructor = await setup()
    await instructor.getRecentSessions()
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/instructors/sessions/recent')
  })

  it('getRecentSessions appends the limit query parameter', async () => {
    const instructor = await setup()
    await instructor.getRecentSessions(5)
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/instructors/sessions/recent?limit=5')
  })
})
