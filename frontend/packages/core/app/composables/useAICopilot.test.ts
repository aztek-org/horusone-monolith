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
  const { useAICopilot } = await import('./useAICopilot')
  return useAICopilot()
}

describe('useAICopilot', () => {
  beforeEach(() => {
    vi.resetModules()
    for (const key of Object.keys(nuxt.state)) Reflect.deleteProperty(nuxt.state, key)
  })

  it('exposes sensible default parameters', async () => {
    const { params } = await load()
    expect(params.value).toEqual({
      assertiveness: 65,
      simulatedErrorRate: 12.5,
      proceduralKnowledge: 'expert',
      commsStyle: 'brevity-military',
      interventionMode: 'assistance',
      confidence: 92,
      isOnline: true,
    })
  })

  it('exposes the selectable option lists', async () => {
    const { commsStyleOptions, knowledgeLevels, interventionModes } = await load()
    expect(commsStyleOptions.map(o => o.value)).toEqual([
      'brevity-military',
      'standard-icao',
      'verbose',
      'minimal',
    ])
    expect(knowledgeLevels.map(o => o.value)).toEqual(['novice', 'proficient', 'expert'])
    expect(interventionModes.map(o => o.value)).toEqual(['monitor', 'assistance', 'override'])
  })

  it('setAssertiveness clamps to the 0..100 range', async () => {
    const { params, setAssertiveness } = await load()
    setAssertiveness(150)
    expect(params.value.assertiveness).toBe(100)
    setAssertiveness(-20)
    expect(params.value.assertiveness).toBe(0)
    setAssertiveness(42)
    expect(params.value.assertiveness).toBe(42)
  })

  it('setErrorRate clamps to the 0..100 range', async () => {
    const { params, setErrorRate } = await load()
    setErrorRate(200)
    expect(params.value.simulatedErrorRate).toBe(100)
    setErrorRate(-1)
    expect(params.value.simulatedErrorRate).toBe(0)
  })

  it('updateConfidence clamps to the 0..100 range', async () => {
    const { params, updateConfidence } = await load()
    updateConfidence(101)
    expect(params.value.confidence).toBe(100)
    updateConfidence(-5)
    expect(params.value.confidence).toBe(0)
  })

  it('setters update knowledge level, comms style, intervention mode and online status', async () => {
    const { params, setKnowledgeLevel, setCommsStyle, setInterventionMode, setOnlineStatus }
      = await load()

    setKnowledgeLevel('proficient')
    setCommsStyle('standard-icao')
    setInterventionMode('override')
    setOnlineStatus(false)

    expect(params.value.proceduralKnowledge).toBe('proficient')
    expect(params.value.commsStyle).toBe('standard-icao')
    expect(params.value.interventionMode).toBe('override')
    expect(params.value.isOnline).toBe(false)
  })

  it('resetParams restores the defaults after modifications', async () => {
    const { params, setAssertiveness, setOnlineStatus, setKnowledgeLevel, resetParams }
      = await load()

    setAssertiveness(10)
    setOnlineStatus(false)
    setKnowledgeLevel('novice')

    resetParams()

    expect(params.value.assertiveness).toBe(65)
    expect(params.value.proceduralKnowledge).toBe('expert')
    expect(params.value.isOnline).toBe(true)
  })
})
