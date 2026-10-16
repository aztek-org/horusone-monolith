import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockEnabledFeatures = { value: ['hangar', 'tower'] as string[] }

vi.mock('./useAuth', () => ({
  useAuth: () => ({ enabledFeatures: mockEnabledFeatures }),
}))

async function setup() {
  const { useFeatureFlags } = await import('./useFeatureFlags')
  return useFeatureFlags()
}

describe('useFeatureFlags', () => {
  beforeEach(() => {
    mockEnabledFeatures.value = ['hangar', 'tower']
  })

  it('isEnabled returns true for an enabled feature', async () => {
    const flags = await setup()
    expect(flags.isEnabled('hangar')).toBe(true)
    expect(flags.isEnabled('tower')).toBe(true)
  })

  it('isEnabled returns false for a disabled feature', async () => {
    const flags = await setup()
    expect(flags.isEnabled('squawk')).toBe(false)
  })

  it('areAllEnabled is false when any feature is missing', async () => {
    const flags = await setup()
    expect(flags.areAllEnabled()).toBe(false)
  })

  it('areAllEnabled is true when all features are enabled', async () => {
    mockEnabledFeatures.value = ['hangar', 'squawk', 'tower']
    const flags = await setup()
    expect(flags.areAllEnabled()).toBe(true)
  })

  it('getEnabledFeatures returns the enabled feature list', async () => {
    const flags = await setup()
    expect(flags.getEnabledFeatures()).toEqual(['hangar', 'tower'])
  })

  it('getEnabledFeatures is empty when nothing is enabled', async () => {
    mockEnabledFeatures.value = []
    const flags = await setup()
    expect(flags.getEnabledFeatures()).toEqual([])
    expect(flags.areAllEnabled()).toBe(false)
  })
})
