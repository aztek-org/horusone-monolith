export type FeatureKey = 'hangar' | 'squawk' | 'tower'

export function useFeatureFlags() {
  const { enabledFeatures } = useAuth()

  function isEnabled(feature: FeatureKey): boolean {
    if (import.meta.server) return true
    return enabledFeatures.value.includes(feature)
  }

  function areAllEnabled(): boolean {
    return isEnabled('hangar') && isEnabled('squawk') && isEnabled('tower')
  }

  function getEnabledFeatures(): FeatureKey[] {
    if (import.meta.server) return ['hangar', 'squawk', 'tower']
    return enabledFeatures.value as FeatureKey[]
  }

  return {
    isEnabled,
    areAllEnabled,
    getEnabledFeatures,
  }
}
