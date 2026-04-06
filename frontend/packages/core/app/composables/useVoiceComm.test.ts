import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('#app/nuxt', () => ({
  useRuntimeConfig: vi.fn(() => ({
    public: {
      wsUrl: 'ws://localhost:8000/ws/voice',
    },
  })),
}))

vi.mock('./useAuth', () => ({
  useAuth: vi.fn(() => ({
    accessToken: { value: 'test-token' },
    isAuthenticated: { value: true },
  })),
}))

class MockWebSocket {
  static current: MockWebSocket | null = null

  onopen: ((e?: Event) => void) | null = null
  onmessage: ((e?: MessageEvent) => void) | null = null
  onerror: ((e?: Event) => void) | null = null
  onclose: ((e?: CloseEvent) => void) | null = null
  send = vi.fn()
  close = vi.fn()
  readyState = 1 // WebSocket.OPEN

  constructor(_url: string) {
    MockWebSocket.current = this
  }
}

vi.stubGlobal('WebSocket', MockWebSocket)

describe('useVoiceComm', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.resetModules()
    MockWebSocket.current = null
  })

  it('initializes with disconnected status', async () => {
    const { useVoiceComm } = await import('./useVoiceComm')
    const { status } = useVoiceComm()
    expect(status.value.connected).toBe(false)
    expect(status.value.recording).toBe(false)
    expect(status.value.processing).toBe(false)
  })

  it('updates status to connected after WebSocket opens', async () => {
    const { useVoiceComm } = await import('./useVoiceComm')
    const { status, connect } = useVoiceComm()
    await connect()
    // Trigger the onopen handler that the composable registered on the ws instance
    MockWebSocket.current?.onopen?.()
    expect(status.value.connected).toBe(true)
  })
})
