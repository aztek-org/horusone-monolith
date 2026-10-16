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
    expect(status.value.pendingInstructor).toBe(false)
  })

  it('updates status to connected after WebSocket opens', async () => {
    const { useVoiceComm } = await import('./useVoiceComm')
    const { status, connect } = useVoiceComm()
    await connect()
    // Trigger the onopen handler that the composable registered on the ws instance
    MockWebSocket.current?.onopen?.()
    expect(status.value.connected).toBe(true)
  })

  it('flags a held exchange on awaiting_instructor and stops the spinner', async () => {
    const { useVoiceComm } = await import('./useVoiceComm')
    const { status, connect } = useVoiceComm()
    await connect()
    MockWebSocket.current?.onopen?.()
    status.value.processing = true

    MockWebSocket.current?.onmessage?.({
      data: JSON.stringify({ type: 'awaiting_instructor' }),
    } as MessageEvent)

    expect(status.value.pendingInstructor).toBe(true)
    expect(status.value.processing).toBe(false)
  })

  it('clears the held flag when a response completes', async () => {
    const { useVoiceComm } = await import('./useVoiceComm')
    const { status, connect } = useVoiceComm()
    await connect()
    MockWebSocket.current?.onopen?.()

    MockWebSocket.current?.onmessage?.({
      data: JSON.stringify({ type: 'awaiting_instructor' }),
    } as MessageEvent)
    MockWebSocket.current?.onmessage?.({
      data: JSON.stringify({ type: 'response_complete' }),
    } as MessageEvent)

    expect(status.value.pendingInstructor).toBe(false)
  })

  it('clears the held flag when the server confirms a new connection', async () => {
    const { useVoiceComm } = await import('./useVoiceComm')
    const { status, connect } = useVoiceComm()
    await connect()
    MockWebSocket.current?.onopen?.()

    status.value.pendingInstructor = true
    MockWebSocket.current?.onmessage?.({
      data: JSON.stringify({ type: 'connected', client_id: 'pilot-1' }),
    } as MessageEvent)

    expect(status.value.pendingInstructor).toBe(false)
  })

  it('refuses to record on an insecure origin instead of failing cryptically', async () => {
    // getUserMedia is unavailable outside a secure context (#73); simulate the
    // browser reporting that via isSecureContext.
    const win = window as unknown as Record<string, unknown>
    const hadOwn = Object.prototype.hasOwnProperty.call(win, 'isSecureContext')
    const previous = win.isSecureContext
    win.isSecureContext = false
    try {
      const { useVoiceComm } = await import('./useVoiceComm')
      const { status, startRecording } = useVoiceComm()
      await startRecording()

      expect(status.value.error).toMatch(/HTTPS/i)
      expect(status.value.recording).toBe(false)
    }
    finally {
      if (hadOwn) win.isSecureContext = previous
      else Reflect.deleteProperty(win, 'isSecureContext')
    }
  })
})
