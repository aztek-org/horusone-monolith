import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockApi = {
  get: vi.fn(),
  post: vi.fn(),
  put: vi.fn(),
  del: vi.fn(),
}

const mockGetAccessToken = vi.fn().mockResolvedValue('test-token')

vi.mock('./useApi', () => ({
  useApi: () => mockApi,
}))

vi.mock('./useAuth', () => ({
  useAuth: () => ({ getAccessToken: mockGetAccessToken }),
}))

vi.mock('#app/nuxt', () => ({
  useRuntimeConfig: () => ({ public: { apiUrl: 'http://localhost:8000' } }),
}))

function makePlan(id: number, overrides: Record<string, unknown> = {}) {
  return {
    id,
    user_id: 'user-1',
    title: `Plan ${id}`,
    aircraft_type: 'C172',
    departure_icao: 'KJFK',
    arrival_icao: 'KBOS',
    alternate_icao: null,
    route_string: null,
    cruise_altitude_ft: 8000,
    estimated_time_enroute: null,
    fuel_required_lbs: null,
    fuel_reserve_lbs: null,
    total_fuel_lbs: null,
    total_weight_lbs: null,
    max_weight_lbs: null,
    cg_position: null,
    cg_within_limits: null,
    departure_lat: null,
    departure_lon: null,
    arrival_lat: null,
    arrival_lon: null,
    status: 'draft',
    created_at: '2026-01-01',
    updated_at: '2026-01-01',
    legs: [],
    ...overrides,
  }
}

async function setup() {
  const { useFlightPlans } = await import('./useFlightPlans')
  return useFlightPlans()
}

describe('useFlightPlans', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetAccessToken.mockResolvedValue('test-token')
    mockApi.get.mockResolvedValue([])
    mockApi.post.mockResolvedValue(makePlan(1))
    mockApi.put.mockResolvedValue(makePlan(1))
    mockApi.del.mockResolvedValue(undefined)
  })

  // -- listFlightPlans ------------------------------------------------------
  it('listFlightPlans GETs the collection with default pagination', async () => {
    mockApi.get.mockResolvedValue([makePlan(1)])
    const plans = await setup()

    const result = await plans.listFlightPlans()
    expect(mockApi.get).toHaveBeenCalledWith(
      '/api/v1/flight-plans?limit=50&offset=0',
    )
    expect(result).toHaveLength(1)
    expect(plans.flightPlans.value).toHaveLength(1)
    expect(plans.isLoading.value).toBe(false)
    expect(plans.errorMessage.value).toBeNull()
  })

  it('listFlightPlans includes the status filter and custom pagination', async () => {
    const plans = await setup()
    await plans.listFlightPlans('validated', 10, 20)
    expect(mockApi.get).toHaveBeenCalledWith(
      '/api/v1/flight-plans?status=validated&limit=10&offset=20',
    )
  })

  it('listFlightPlans returns [] and records the error on failure', async () => {
    mockApi.get.mockRejectedValue({ detail: 'Nope' })
    const plans = await setup()

    await expect(plans.listFlightPlans()).resolves.toEqual([])
    expect(plans.errorMessage.value).toBe('Nope')
    expect(plans.isLoading.value).toBe(false)
  })

  it('listFlightPlans uses a default error message when detail is missing', async () => {
    mockApi.get.mockRejectedValue(new Error('network'))
    const plans = await setup()
    await plans.listFlightPlans()
    expect(plans.errorMessage.value).toBe('Failed to load flight plans')
  })

  // -- getFlightPlan --------------------------------------------------------
  it('getFlightPlan GETs a single plan and stores it as current', async () => {
    const plan = makePlan(7)
    mockApi.get.mockResolvedValue(plan)
    const plans = await setup()

    await expect(plans.getFlightPlan(7)).resolves.toEqual(plan)
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/flight-plans/7')
    expect(plans.currentPlan.value).toEqual(plan)
  })

  it('getFlightPlan returns null and records the error on failure', async () => {
    mockApi.get.mockRejectedValue({ detail: 'missing' })
    const plans = await setup()
    await expect(plans.getFlightPlan(9)).resolves.toBeNull()
    expect(plans.errorMessage.value).toBe('missing')
  })

  // -- createFlightPlan -----------------------------------------------------
  it('createFlightPlan POSTs and prepends to the local list', async () => {
    const created = makePlan(3)
    mockApi.post.mockResolvedValue(created)
    const plans = await setup()

    const result = await plans.createFlightPlan({
      title: 'New',
      aircraft_type: 'C172',
      departure_icao: 'KJFK',
      arrival_icao: 'KBOS',
    })

    expect(mockApi.post).toHaveBeenCalledWith(
      '/api/v1/flight-plans',
      expect.objectContaining({ title: 'New' }),
    )
    expect(result).toEqual(created)
    expect(plans.flightPlans.value[0]).toEqual(created)
    expect(plans.isSaving.value).toBe(false)
  })

  it('createFlightPlan returns null on failure', async () => {
    mockApi.post.mockRejectedValue({ detail: 'bad payload' })
    const plans = await setup()
    await expect(plans.createFlightPlan({} as never)).resolves.toBeNull()
    expect(plans.errorMessage.value).toBe('bad payload')
  })

  // -- updateFlightPlan -----------------------------------------------------
  it('updateFlightPlan replaces the matching entry in the local list', async () => {
    const original = makePlan(4)
    const updated = makePlan(4, { title: 'Changed' })
    mockApi.get.mockResolvedValue([original])
    mockApi.put.mockResolvedValue(updated)

    const plans = await setup()
    await plans.listFlightPlans()
    await plans.updateFlightPlan(4, { title: 'Changed' })

    expect(mockApi.put).toHaveBeenCalledWith('/api/v1/flight-plans/4', { title: 'Changed' })
    expect(plans.flightPlans.value[0].title).toBe('Changed')
    expect(plans.currentPlan.value).toEqual(updated)
  })

  // -- AI parsing -----------------------------------------------------------
  it('createFromText POSTs the raw text', async () => {
    const parsed = makePlan(5)
    mockApi.post.mockResolvedValue(parsed)
    const plans = await setup()

    await plans.createFromText('KJFK to KBOS at 8000 feet')
    expect(mockApi.post).toHaveBeenCalledWith('/api/v1/flight-plans/from-text', {
      text: 'KJFK to KBOS at 8000 feet',
    })
    expect(plans.flightPlans.value[0]).toEqual(parsed)
  })

  it('createFromImage uploads FormData with an Authorization header', async () => {
    const extracted = makePlan(6)
    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(extracted),
    })
    vi.stubGlobal('fetch', fetchMock)

    const plans = await setup()
    const file = new File(['x'], 'plan.png', { type: 'image/png' })
    const result = await plans.createFromImage(file)

    expect(fetchMock).toHaveBeenCalledOnce()
    const [url, opts] = fetchMock.mock.calls[0] as [string, RequestInit]
    expect(url).toBe('http://localhost:8000/api/v1/flight-plans/from-image')
    expect(opts.method).toBe('POST')
    expect((opts.headers as Record<string, string>).Authorization).toBe('Bearer test-token')
    expect(opts.body).toBeInstanceOf(FormData)
    expect(result).toEqual(extracted)
    expect(plans.isSaving.value).toBe(false)
  })

  it('createFromImage surfaces an API error detail', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 422,
        json: () => Promise.resolve({ detail: 'Unreadable image' }),
      }),
    )
    const plans = await setup()
    await expect(plans.createFromImage(new File(['x'], 'plan.png'))).resolves.toBeNull()
    expect(plans.errorMessage.value).toBe('Unreadable image')
  })

  // -- validateFlightPlan ---------------------------------------------------
  it('validateFlightPlan POSTs, stores the result and refreshes a valid plan', async () => {
    const refreshed = makePlan(8, { status: 'validated' })
    const validation = {
      is_valid: true,
      results: [],
      errors: [],
      validated_at: '2026-01-01',
    }
    mockApi.post.mockResolvedValue(validation)
    mockApi.get.mockResolvedValue(refreshed)

    const plans = await setup()
    const result = await plans.validateFlightPlan(8)

    expect(mockApi.post).toHaveBeenCalledWith('/api/v1/flight-plans/8/validate')
    expect(result).toEqual(validation)
    expect(plans.validationResponse.value).toEqual(validation)
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/flight-plans/8')
    expect(plans.isValidating.value).toBe(false)
  })

  it('validateFlightPlan does not refresh when the plan is invalid', async () => {
    mockApi.post.mockResolvedValue({
      is_valid: false,
      results: [],
      errors: [],
      validated_at: '2026-01-01',
    })
    const plans = await setup()
    await plans.validateFlightPlan(8)
    expect(mockApi.get).not.toHaveBeenCalled()
  })

  // -- activateFlightPlan ---------------------------------------------------
  it('activateFlightPlan POSTs to activate and updates the local list', async () => {
    const original = makePlan(2)
    const activated = makePlan(2, { status: 'active' })
    mockApi.get.mockResolvedValue([original])
    mockApi.post.mockResolvedValue(activated)

    const plans = await setup()
    await plans.listFlightPlans()
    const result = await plans.activateFlightPlan(2)

    expect(mockApi.post).toHaveBeenCalledWith('/api/v1/flight-plans/2/activate')
    expect(result).toEqual(activated)
    expect(plans.flightPlans.value[0].status).toBe('active')
  })

  // -- deleteFlightPlan -----------------------------------------------------
  it('deleteFlightPlan DELETEs and removes the plan from local state', async () => {
    const plan = makePlan(11)
    mockApi.get.mockResolvedValue([plan])
    const plans = await setup()
    await plans.listFlightPlans()

    await expect(plans.deleteFlightPlan(11)).resolves.toBe(true)
    expect(mockApi.del).toHaveBeenCalledWith('/api/v1/flight-plans/11')
    expect(plans.flightPlans.value).toEqual([])
  })

  it('deleteFlightPlan returns false on failure', async () => {
    mockApi.del.mockRejectedValue({ detail: 'forbidden' })
    const plans = await setup()
    await expect(plans.deleteFlightPlan(11)).resolves.toBe(false)
    expect(plans.errorMessage.value).toBe('forbidden')
  })

  // -- clearValidation / resetState -----------------------------------------
  it('clearValidation resets only the validation response', async () => {
    mockApi.post.mockResolvedValue({ is_valid: false, results: [], errors: [], validated_at: '' })
    const plans = await setup()
    await plans.validateFlightPlan(1)
    expect(plans.validationResponse.value).not.toBeNull()

    plans.clearValidation()
    expect(plans.validationResponse.value).toBeNull()
  })

  it('resetState clears current plan, validation and error', async () => {
    mockApi.get.mockRejectedValue({ detail: 'boom' })
    const plans = await setup()
    await plans.listFlightPlans()
    await plans.resetState()
    expect(plans.currentPlan.value).toBeNull()
    expect(plans.validationResponse.value).toBeNull()
    expect(plans.errorMessage.value).toBeNull()
  })
})
