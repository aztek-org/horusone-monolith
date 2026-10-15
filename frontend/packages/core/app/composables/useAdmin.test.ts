import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockApi = {
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
}

vi.mock('./useApi', () => ({
  useApi: () => mockApi,
}))

async function setup() {
  const { useAdmin } = await import('./useAdmin')
  return useAdmin()
}

describe('useAdmin', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockApi.get.mockResolvedValue([])
    mockApi.post.mockResolvedValue({})
    mockApi.put.mockResolvedValue({})
    mockApi.del.mockResolvedValue(undefined)
  })

  // -- Stats ----------------------------------------------------------------
  it('fetchStats GETs the platform stats endpoint', async () => {
    const admin = await setup()
    await admin.fetchStats()
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/admin/stats')
  })

  // -- Organizations --------------------------------------------------------
  it('fetchOrganizations GETs the organizations collection', async () => {
    const admin = await setup()
    await admin.fetchOrganizations()
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/admin/organizations/')
  })

  it('fetchOrganization GETs a single organization by id', async () => {
    const admin = await setup()
    await admin.fetchOrganization('org-1')
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/admin/organizations/org-1')
  })

  it('createOrganization POSTs the payload', async () => {
    const admin = await setup()
    const payload = { name: 'Acme Flight', slug: 'acme', max_seats: 10 }
    await admin.createOrganization(payload)
    expect(mockApi.post).toHaveBeenCalledWith('/api/v1/admin/organizations/', payload)
  })

  it('updateOrganization PUTs the payload to the organization', async () => {
    const admin = await setup()
    const payload = { name: 'Renamed', is_active: false }
    await admin.updateOrganization('org-1', payload)
    expect(mockApi.put).toHaveBeenCalledWith('/api/v1/admin/organizations/org-1', payload)
  })

  it('deleteOrganization DELETEs the organization', async () => {
    const admin = await setup()
    await admin.deleteOrganization('org-1')
    expect(mockApi.del).toHaveBeenCalledWith('/api/v1/admin/organizations/org-1')
  })

  // -- Seats ----------------------------------------------------------------
  it('fetchSeats GETs the seats under an organization', async () => {
    const admin = await setup()
    await admin.fetchSeats('org-1')
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/admin/organizations/org-1/seats')
  })

  it('createSeat POSTs the payload under an organization', async () => {
    const admin = await setup()
    const payload = { email: 'pilot@horus.app', role: 'student' }
    await admin.createSeat('org-1', payload)
    expect(mockApi.post).toHaveBeenCalledWith('/api/v1/admin/organizations/org-1/seats', payload)
  })

  it('updateSeat PUTs the payload to a seat', async () => {
    const admin = await setup()
    const payload = { is_active: false }
    await admin.updateSeat('org-1', 'seat-9', payload)
    expect(mockApi.put).toHaveBeenCalledWith('/api/v1/admin/organizations/org-1/seats/seat-9', payload)
  })

  it('deleteSeat DELETEs a seat', async () => {
    const admin = await setup()
    await admin.deleteSeat('org-1', 'seat-9')
    expect(mockApi.del).toHaveBeenCalledWith('/api/v1/admin/organizations/org-1/seats/seat-9')
  })

  // -- Users ----------------------------------------------------------------
  it('fetchUsers GETs the users collection without a search query', async () => {
    const admin = await setup()
    await admin.fetchUsers()
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/admin/users/')
  })

  it('fetchUsers encodes the search query parameter', async () => {
    const admin = await setup()
    await admin.fetchUsers('john doe')
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/admin/users/?search=john%20doe')
  })

  it('fetchUser GETs a single user', async () => {
    const admin = await setup()
    await admin.fetchUser('user-3')
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/admin/users/user-3')
  })

  it('updateUser PUTs the active flag', async () => {
    const admin = await setup()
    await admin.updateUser('user-3', { is_active: true })
    expect(mockApi.put).toHaveBeenCalledWith('/api/v1/admin/users/user-3', { is_active: true })
  })

  // -- Analytics ------------------------------------------------------------
  it('fetchLeaderboard encodes the org_id query parameter', async () => {
    const admin = await setup()
    await admin.fetchLeaderboard('org 1')
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/analytics/leaderboard?org_id=org%201')
  })

  it('fetchAnalyticsOverview encodes the org_id query parameter', async () => {
    const admin = await setup()
    await admin.fetchAnalyticsOverview('org-1')
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/analytics/overview?org_id=org-1')
  })

  // -- Modules --------------------------------------------------------------
  it('fetchModules GETs the modules collection', async () => {
    const admin = await setup()
    await admin.fetchModules()
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/modules/')
  })

  it('fetchModule GETs a single module', async () => {
    const admin = await setup()
    await admin.fetchModule('mod-1')
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/modules/mod-1')
  })

  it('createModule POSTs the payload', async () => {
    const admin = await setup()
    const payload = {
      name: 'VFR Basics',
      description: 'Intro',
      difficulty_level: 'beginner',
      is_published: false,
      org_id: null,
      sort_order: 1,
    }
    await admin.createModule(payload)
    expect(mockApi.post).toHaveBeenCalledWith('/api/v1/modules/', payload)
  })

  it('updateModule PUTs the payload to a module', async () => {
    const admin = await setup()
    await admin.updateModule('mod-1', { is_published: true })
    expect(mockApi.put).toHaveBeenCalledWith('/api/v1/modules/mod-1', { is_published: true })
  })

  it('deleteModule DELETEs a module', async () => {
    const admin = await setup()
    await admin.deleteModule('mod-1')
    expect(mockApi.del).toHaveBeenCalledWith('/api/v1/modules/mod-1')
  })

  it('linkScenario POSTs the scenario id and sort order', async () => {
    const admin = await setup()
    await admin.linkScenario('mod-1', 'scen-2', 3)
    expect(mockApi.post).toHaveBeenCalledWith('/api/v1/modules/mod-1/scenarios', {
      scenario_id: 'scen-2',
      sort_order: 3,
    })
  })

  it('unlinkScenario DELETEs the scenario association', async () => {
    const admin = await setup()
    await admin.unlinkScenario('mod-1', 'scen-2')
    expect(mockApi.del).toHaveBeenCalledWith('/api/v1/modules/mod-1/scenarios/scen-2')
  })
})
