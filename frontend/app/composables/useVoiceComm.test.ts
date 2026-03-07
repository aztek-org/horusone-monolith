import { describe, it, expect, vi, beforeEach } from 'vitest'

// Track the most recently constructed WebSocket instance so we can trigger handlers
let currentWs: any = null

class MockWebSocket {
  onopen: ((e?: Event) => void) | null = null
  onmessage: ((e?: MessageEvent) => void) | null = null
  onerror: ((e?: Event) => void) | null = null
  onclose: ((e?: CloseEvent) => void) | null = null
  send = vi.fn()
  close = vi.fn()
  readyState = 1 // WebSocket.OPEN

  constructor(_url: string) {
    currentWs = this
  }
}

vi.stubGlobal('WebSocket', MockWebSocket)

describe('useVoiceComm', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.resetModules()
    currentWs = null
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
    currentWs?.onopen?.()
    expect(status.value.connected).toBe(true)
  })
})
