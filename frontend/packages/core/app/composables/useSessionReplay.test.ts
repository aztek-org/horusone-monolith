import { describe, expect, it, vi } from 'vitest'

const apiGet = vi.fn()

vi.mock('./useApi', () => ({
  useApi: () => ({ get: apiGet }),
}))

describe('useSessionReplay', () => {
  it('exposes provenance returned by the replay response', async () => {
    const provenance = [{
      event_type: 'exchange_completed',
      created_at: '2026-09-25T12:00:01Z',
      graph: 'live',
      node: 'generate_atc_response',
      scene_version: 'atc-2026.09',
      prompt_version: 'atc-2026.09',
      llm_provider: 'groq',
      llm_model: 'llama-3.3-70b-versatile',
      llm_fallback_used: false,
      retrieved_chunk_ids: ['chunk-a'],
      instructor_overridden: false,
    }]
    apiGet.mockImplementation((url: string) => {
      if (url.endsWith('/replay')) {
        return Promise.resolve({
          id: 42,
          scenario_id: 7,
          scenario_name: 'JFK Departure',
          status: 'completed',
          language: 'en',
          started_at: '2026-09-25T12:00:00Z',
          ended_at: '2026-09-25T12:20:00Z',
          duration_seconds: 1200,
          track_points: [],
          insights: [],
          voice_logs: [],
          scoring: null,
          provenance,
        })
      }
      return Promise.resolve([])
    })

    const { useSessionReplay } = await import('./useSessionReplay')
    const replay = useSessionReplay()

    expect(replay.provenance.value).toEqual([])
    expect(await replay.loadSession(42)).toBe(true)
    expect(replay.provenance.value).toEqual(provenance)
  })
})
