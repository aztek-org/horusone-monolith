/**
 * Typed API client composable for flight plan endpoints.
 * Handles CRUD, AI parsing (text/image), validation, and activation.
 */

export interface FlightPlanLeg {
  id: number
  sequence: number
  from_waypoint: string
  to_waypoint: string
  from_lat: number | null
  from_lon: number | null
  to_lat: number | null
  to_lon: number | null
  altitude_ft: number | null
  speed_kts: number | null
  heading_deg: number | null
  distance_nm: number | null
  leg_type: string
  notes: string | null
}

export interface FlightPlan {
  id: number
  user_id: string
  title: string
  aircraft_type: string
  departure_icao: string
  arrival_icao: string
  alternate_icao: string | null
  route_string: string | null
  cruise_altitude_ft: number | null
  estimated_time_enroute: string | null
  fuel_required_lbs: number | null
  fuel_reserve_lbs: number | null
  total_fuel_lbs: number | null
  total_weight_lbs: number | null
  max_weight_lbs: number | null
  cg_position: number | null
  cg_within_limits: boolean | null
  departure_lat: number | null
  departure_lon: number | null
  arrival_lat: number | null
  arrival_lon: number | null
  status: 'draft' | 'validated' | 'active' | 'completed'
  created_at: string
  updated_at: string
  legs: FlightPlanLeg[]
}

export interface FlightPlanCreateData {
  title: string
  aircraft_type: string
  departure_icao: string
  arrival_icao: string
  alternate_icao?: string
  route_string?: string
  cruise_altitude_ft?: number
  fuel_required_lbs?: number
  fuel_reserve_lbs?: number
  total_fuel_lbs?: number
  total_weight_lbs?: number
  max_weight_lbs?: number
  cg_position?: number
  legs?: Omit<FlightPlanLeg, 'id'>[]
}

export type FlightPlanUpdateData = Partial<FlightPlanCreateData>

export interface ValidationError {
  field: string
  severity: 'error' | 'warning' | 'info'
  message: string
  agent: string
}

export interface ValidationResult {
  check_name: string
  status: 'pass' | 'warning' | 'fail'
  message: string
  agent: string
  details: Record<string, unknown> | null
}

export interface ValidationResponse {
  is_valid: boolean
  results: ValidationResult[]
  errors: ValidationError[]
  validated_at: string
}

export function useFlightPlans() {
  const api = useApi()

  const flightPlans = ref<FlightPlan[]>([])
  const currentPlan = ref<FlightPlan | null>(null)
  const isLoading = ref(false)
  const isSaving = ref(false)
  const isValidating = ref(false)
  const errorMessage = ref<string | null>(null)
  const validationResponse = ref<ValidationResponse | null>(null)

  /**
   * List all flight plans for the current user.
   */
  async function listFlightPlans(
    status?: FlightPlan['status'],
    limit = 50,
    offset = 0,
  ): Promise<FlightPlan[]> {
    isLoading.value = true
    errorMessage.value = null
    try {
      const params = new URLSearchParams()
      if (status) params.set('status', status)
      params.set('limit', String(limit))
      params.set('offset', String(offset))

      const query = params.toString()
      const path = `/api/v1/flight-plans${query ? `?${query}` : ''}`
      const result = await api.get<FlightPlan[]>(path)
      flightPlans.value = result
      return result
    }
    catch (err) {
      const apiErr = err as { detail?: string }
      errorMessage.value = apiErr.detail ?? 'Failed to load flight plans'
      return []
    }
    finally {
      isLoading.value = false
    }
  }

  /**
   * Get a single flight plan by ID (with legs).
   */
  async function getFlightPlan(id: number): Promise<FlightPlan | null> {
    isLoading.value = true
    errorMessage.value = null
    try {
      const result = await api.get<FlightPlan>(`/api/v1/flight-plans/${id}`)
      currentPlan.value = result
      return result
    }
    catch (err) {
      const apiErr = err as { detail?: string }
      errorMessage.value = apiErr.detail ?? 'Failed to load flight plan'
      return null
    }
    finally {
      isLoading.value = false
    }
  }

  /**
   * Create a new flight plan.
   */
  async function createFlightPlan(data: FlightPlanCreateData): Promise<FlightPlan | null> {
    isSaving.value = true
    errorMessage.value = null
    try {
      const result = await api.post<FlightPlan>('/api/v1/flight-plans', data)
      currentPlan.value = result
      // Prepend to local list
      flightPlans.value.unshift(result)
      return result
    }
    catch (err) {
      const apiErr = err as { detail?: string }
      errorMessage.value = apiErr.detail ?? 'Failed to create flight plan'
      return null
    }
    finally {
      isSaving.value = false
    }
  }

  /**
   * Update an existing flight plan.
   */
  async function updateFlightPlan(
    id: number,
    data: FlightPlanUpdateData,
  ): Promise<FlightPlan | null> {
    isSaving.value = true
    errorMessage.value = null
    try {
      const result = await api.put<FlightPlan>(`/api/v1/flight-plans/${id}`, data)
      currentPlan.value = result
      // Update in local list
      const index = flightPlans.value.findIndex(fp => fp.id === id)
      if (index !== -1) {
        flightPlans.value[index] = result
      }
      return result
    }
    catch (err) {
      const apiErr = err as { detail?: string }
      errorMessage.value = apiErr.detail ?? 'Failed to update flight plan'
      return null
    }
    finally {
      isSaving.value = false
    }
  }

  /**
   * Parse a flight plan from natural text via AI.
   */
  async function createFromText(text: string): Promise<FlightPlan | null> {
    isSaving.value = true
    errorMessage.value = null
    try {
      const result = await api.post<FlightPlan>('/api/v1/flight-plans/from-text', { text })
      currentPlan.value = result
      flightPlans.value.unshift(result)
      return result
    }
    catch (err) {
      const apiErr = err as { detail?: string }
      errorMessage.value = apiErr.detail ?? 'Failed to parse flight plan from text'
      return null
    }
    finally {
      isSaving.value = false
    }
  }

  /**
   * Extract a flight plan from an image (OCR).
   */
  async function createFromImage(file: File): Promise<FlightPlan | null> {
    isSaving.value = true
    errorMessage.value = null
    try {
      const config = useRuntimeConfig()
      const baseUrl = config.public.apiUrl as string
      const { getAccessToken } = useAuth()

      const formData = new FormData()
      formData.append('file', file)

      const token = await getAccessToken()
      const headers: Record<string, string> = {}
      if (token) {
        headers.Authorization = `Bearer ${token}`
      }

      const response = await fetch(`${baseUrl}/api/v1/flight-plans/from-image`, {
        method: 'POST',
        headers,
        body: formData,
      })

      if (!response.ok) {
        let detail = `Request failed: ${response.status}`
        try {
          const body = await response.json()
          detail = body.detail || detail
        }
        catch { /* ignore parse errors */ }
        throw { detail }
      }

      const result: FlightPlan = await response.json()
      currentPlan.value = result
      flightPlans.value.unshift(result)
      return result
    }
    catch (err) {
      const apiErr = err as { detail?: string }
      errorMessage.value = apiErr.detail ?? 'Failed to extract flight plan from image'
      return null
    }
    finally {
      isSaving.value = false
    }
  }

  /**
   * Validate a flight plan using AI agents.
   */
  async function validateFlightPlan(id: number): Promise<ValidationResponse | null> {
    isValidating.value = true
    errorMessage.value = null
    try {
      const result = await api.post<ValidationResponse>(
        `/api/v1/flight-plans/${id}/validate`,
      )
      validationResponse.value = result
      // If validation succeeded, refresh the plan (status may have changed)
      if (result.is_valid) {
        await getFlightPlan(id)
      }
      return result
    }
    catch (err) {
      const apiErr = err as { detail?: string }
      errorMessage.value = apiErr.detail ?? 'Failed to validate flight plan'
      return null
    }
    finally {
      isValidating.value = false
    }
  }

  /**
   * Activate a validated flight plan for training.
   */
  async function activateFlightPlan(id: number): Promise<FlightPlan | null> {
    isSaving.value = true
    errorMessage.value = null
    try {
      const result = await api.post<FlightPlan>(
        `/api/v1/flight-plans/${id}/activate`,
      )
      currentPlan.value = result
      // Update in local list
      const index = flightPlans.value.findIndex(fp => fp.id === id)
      if (index !== -1) {
        flightPlans.value[index] = result
      }
      return result
    }
    catch (err) {
      const apiErr = err as { detail?: string }
      errorMessage.value = apiErr.detail ?? 'Failed to activate flight plan'
      return null
    }
    finally {
      isSaving.value = false
    }
  }

  /**
   * Delete a flight plan.
   */
  async function deleteFlightPlan(id: number): Promise<boolean> {
    errorMessage.value = null
    try {
      await api.del(`/api/v1/flight-plans/${id}`)
      flightPlans.value = flightPlans.value.filter(fp => fp.id !== id)
      if (currentPlan.value?.id === id) {
        currentPlan.value = null
      }
      return true
    }
    catch (err) {
      const apiErr = err as { detail?: string }
      errorMessage.value = apiErr.detail ?? 'Failed to delete flight plan'
      return false
    }
  }

  /**
   * Clear validation state.
   */
  function clearValidation() {
    validationResponse.value = null
  }

  /**
   * Reset all state.
   */
  function resetState() {
    currentPlan.value = null
    validationResponse.value = null
    errorMessage.value = null
  }

  return {
    flightPlans: readonly(flightPlans),
    currentPlan: readonly(currentPlan),
    isLoading: readonly(isLoading),
    isSaving: readonly(isSaving),
    isValidating: readonly(isValidating),
    errorMessage: readonly(errorMessage),
    validationResponse: readonly(validationResponse),
    listFlightPlans,
    getFlightPlan,
    createFlightPlan,
    updateFlightPlan,
    createFromText,
    createFromImage,
    validateFlightPlan,
    activateFlightPlan,
    deleteFlightPlan,
    clearValidation,
    resetState,
  }
}
