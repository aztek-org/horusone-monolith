export interface AICopilotParams {
  assertiveness: number
  simulatedErrorRate: number
  proceduralKnowledge: 'novice' | 'proficient' | 'expert'
  commsStyle: string
  interventionMode: 'monitor' | 'assistance' | 'override'
  confidence: number
  isOnline: boolean
}

const defaultParams: AICopilotParams = {
  assertiveness: 65,
  simulatedErrorRate: 12.5,
  proceduralKnowledge: 'expert',
  commsStyle: 'brevity-military',
  interventionMode: 'assistance',
  confidence: 92,
  isOnline: true
}

export const useAICopilot = () => {
  const params = useState<AICopilotParams>('aiCopilot', () => ({ ...defaultParams }))

  const commsStyleOptions = [
    { value: 'brevity-military', label: 'Brevity-Focused (Military)' },
    { value: 'standard-icao', label: 'Standard ICAO' },
    { value: 'verbose', label: 'Verbose/Training' },
    { value: 'minimal', label: 'Minimal Response' }
  ]

  const knowledgeLevels = [
    { value: 'novice', label: 'Novice' },
    { value: 'proficient', label: 'Proficient' },
    { value: 'expert', label: 'Expert' }
  ]

  const interventionModes = [
    { value: 'monitor', label: 'Monitor Only' },
    { value: 'assistance', label: 'Active Assistance' },
    { value: 'override', label: 'Emergency Override' }
  ]

  function setAssertiveness(value: number) {
    params.value.assertiveness = Math.min(100, Math.max(0, value))
  }

  function setErrorRate(value: number) {
    params.value.simulatedErrorRate = Math.min(100, Math.max(0, value))
  }

  function setKnowledgeLevel(level: 'novice' | 'proficient' | 'expert') {
    params.value.proceduralKnowledge = level
  }

  function setCommsStyle(style: string) {
    params.value.commsStyle = style
  }

  function setInterventionMode(mode: 'monitor' | 'assistance' | 'override') {
    params.value.interventionMode = mode
  }

  function setOnlineStatus(online: boolean) {
    params.value.isOnline = online
  }

  function updateConfidence(confidence: number) {
    params.value.confidence = Math.min(100, Math.max(0, confidence))
  }

  function resetParams() {
    params.value = { ...defaultParams }
  }

  return {
    params: readonly(params),
    commsStyleOptions,
    knowledgeLevels,
    interventionModes,
    setAssertiveness,
    setErrorRate,
    setKnowledgeLevel,
    setCommsStyle,
    setInterventionMode,
    setOnlineStatus,
    updateConfidence,
    resetParams
  }
}
