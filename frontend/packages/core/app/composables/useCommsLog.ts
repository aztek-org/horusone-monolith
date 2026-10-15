export interface CommsLogEntry {
  id: string
  timestamp: string
  type: 'ai' | 'user' | 'system' | 'atc'
  message: string
  variant?: 'default' | 'warning' | 'info'
}

const defaultLog: CommsLogEntry[] = [
  {
    id: 'log-1',
    timestamp: '14:01:02',
    type: 'ai',
    message: 'Analyzing storm cell intensity...',
    variant: 'info',
  },
  {
    id: 'log-2',
    timestamp: '14:01:15',
    type: 'atc',
    message: 'Aero-Alpha, maintain 12,000.',
  },
  {
    id: 'log-3',
    timestamp: '14:02:00',
    type: 'system',
    message: 'Icing detected on probe.',
    variant: 'warning',
  },
  {
    id: 'log-4',
    timestamp: '14:02:10',
    type: 'ai',
    message: 'Anti-ice activated. Recalculating descent profile.',
    variant: 'info',
  },
]

export const useCommsLog = () => {
  const entries = useState<CommsLogEntry[]>('commsLog', () => [...defaultLog])
  const maxEntries = 50

  const latestEntries = computed(() => entries.value.slice(-10))

  function addEntry(entry: Omit<CommsLogEntry, 'id' | 'timestamp'>) {
    const id = `log-${Date.now()}`
    const timestamp = new Date().toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })

    entries.value.push({ ...entry, id, timestamp })

    // Trim old entries
    if (entries.value.length > maxEntries) {
      entries.value = entries.value.slice(-maxEntries)
    }
  }

  function addAIMessage(message: string, variant: 'default' | 'info' = 'info') {
    addEntry({ type: 'ai', message, variant })
  }

  function addSystemMessage(message: string, variant: 'default' | 'warning' = 'warning') {
    addEntry({ type: 'system', message, variant })
  }

  function addATCMessage(message: string) {
    addEntry({ type: 'atc', message })
  }

  function clearLog() {
    entries.value = []
  }

  function resetLog() {
    entries.value = [...defaultLog]
  }

  return {
    entries: readonly(entries),
    latestEntries,
    addEntry,
    addAIMessage,
    addSystemMessage,
    addATCMessage,
    clearLog,
    resetLog,
  }
}
