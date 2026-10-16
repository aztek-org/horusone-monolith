import { describe, it, expect, vi, beforeEach } from 'vitest'

const nuxt = vi.hoisted(() => ({
  state: {} as Record<string, unknown>,
  app: null as any,
}))

vi.mock('#app/nuxt', async () => {
  const { reactive } = await import('vue')
  nuxt.state = reactive<Record<string, unknown>>({})
  nuxt.app = { payload: { state: nuxt.state }, _state: {} }
  return {
    useNuxtApp: () => nuxt.app,
    tryUseNuxtApp: () => nuxt.app,
    useRuntimeConfig: () => ({ public: {} }),
  }
})

async function load() {
  const { useCommsLog } = await import('./useCommsLog')
  return useCommsLog()
}

describe('useCommsLog', () => {
  beforeEach(() => {
    vi.resetModules()
    for (const key of Object.keys(nuxt.state)) Reflect.deleteProperty(nuxt.state, key)
  })

  it('starts with the four default entries', async () => {
    const { entries } = await load()
    expect(entries.value.map(e => e.id)).toEqual(['log-1', 'log-2', 'log-3', 'log-4'])
  })

  it('latestEntries returns the most recent ten entries', async () => {
    const { entries, addEntry, latestEntries } = await load()
    for (let i = 0; i < 12; i++) {
      addEntry({ type: 'system', message: `msg-${i}` })
    }
    expect(entries.value).toHaveLength(16)
    expect(latestEntries.value).toHaveLength(10)
    expect(latestEntries.value.at(-1)?.message).toBe('msg-11')
  })

  it('addEntry assigns an id and a formatted timestamp', async () => {
    const { entries, addEntry } = await load()
    addEntry({ type: 'user', message: 'Say again', variant: 'default' })
    const added = entries.value.at(-1)!
    expect(added.id).toMatch(/^log-\d+$/)
    expect(added.timestamp).toMatch(/^\d{2}:\d{2}:\d{2}$/)
    expect(added).toMatchObject({ type: 'user', message: 'Say again', variant: 'default' })
  })

  it('addAIMessage defaults to the info variant', async () => {
    const { entries, addAIMessage } = await load()
    addAIMessage('Analyzing')
    expect(entries.value.at(-1)).toMatchObject({ type: 'ai', message: 'Analyzing', variant: 'info' })
  })

  it('addSystemMessage defaults to the warning variant', async () => {
    const { entries, addSystemMessage } = await load()
    addSystemMessage('Icing detected')
    expect(entries.value.at(-1)).toMatchObject({
      type: 'system',
      message: 'Icing detected',
      variant: 'warning',
    })
  })

  it('addATCMessage records an atc entry', async () => {
    const { entries, addATCMessage } = await load()
    addATCMessage('Maintain 12,000')
    expect(entries.value.at(-1)).toMatchObject({ type: 'atc', message: 'Maintain 12,000' })
  })

  it('trims old entries once the 50-entry cap is exceeded', async () => {
    const { entries, addEntry } = await load()
    for (let i = 0; i < 50; i++) {
      addEntry({ type: 'system', message: `m-${i}` })
    }
    expect(entries.value).toHaveLength(50)
    expect(entries.value.at(-1)?.message).toBe('m-49')
    // The oldest defaults have been pushed out
    expect(entries.value.find(e => e.id === 'log-1')).toBeUndefined()
  })

  it('clearLog empties the log', async () => {
    const { entries, clearLog } = await load()
    clearLog()
    expect(entries.value).toEqual([])
  })

  it('resetLog restores the defaults', async () => {
    const { entries, clearLog, resetLog } = await load()
    clearLog()
    resetLog()
    expect(entries.value.map(e => e.id)).toEqual(['log-1', 'log-2', 'log-3', 'log-4'])
  })
})
