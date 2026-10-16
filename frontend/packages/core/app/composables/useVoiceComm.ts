/**
 * Composable for voice communication with ATC backend
 * Handles WebSocket connection, audio recording, and playback
 */

import { ref, onUnmounted } from 'vue'

export interface VoiceCommStatus {
  connected: boolean
  recording: boolean
  processing: boolean
  speaking: boolean
  /**
   * True while the last transmission is held for instructor review (HITL).
   * The pilot must not hear silence without knowing why, so the UI surfaces
   * this state instead of treating the held exchange as a normal response.
   */
  pendingInstructor: boolean
  error: string | null
}

export const useVoiceComm = () => {
  const status = ref<VoiceCommStatus>({
    connected: false,
    recording: false,
    processing: false,
    speaking: false,
    pendingInstructor: false,
    error: null,
  })

  let ws: WebSocket | null = null
  let mediaRecorder: MediaRecorder | null = null
  let audioChunks: Blob[] = []
  let heartbeatTimer: ReturnType<typeof setInterval> | null = null
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let reconnectAttempts = 0
  let isConnecting = false
  const MAX_RECONNECT_ATTEMPTS = 5

  const config = useRuntimeConfig()
  const wsUrl = config.public.wsUrl as string

  const { accessToken, isAuthenticated } = useAuth()

  const connect = async (): Promise<void> => {
    if (isConnecting) return
    if (!isAuthenticated.value || !accessToken.value) {
      status.value.error = 'Authentication required'
      return
    }

    isConnecting = true
    try {
      const url = new URL(wsUrl, window.location.origin)
      url.searchParams.set('token', accessToken.value)
      ws = new WebSocket(url.toString())

      ws.onopen = () => {
        console.log('Voice communication connected')
        status.value.connected = true
        status.value.error = null
        reconnectAttempts = 0
        isConnecting = false
        _startHeartbeat()
      }

      ws.onmessage = async (event) => {
        if (event.data instanceof Blob) {
          console.log('Received audio response')
          await playAudio(event.data)
        }
        else if (typeof event.data === 'string') {
          try {
            const message = JSON.parse(event.data)
            handleServerMessage(message)
          }
          catch (e) {
            console.error('Failed to parse server message:', e)
          }
        }
      }

      ws.onerror = () => {
        console.error('WebSocket error')
        status.value.error = 'Connection error'
        status.value.connected = false
        isConnecting = false
      }

      ws.onclose = () => {
        console.log('Voice communication disconnected')
        status.value.connected = false
        isConnecting = false
        _stopHeartbeat()
        _tryReconnect()
      }
    }
    catch (error) {
      console.error('Failed to connect:', error)
      status.value.error = 'Failed to connect to server'
      isConnecting = false
    }
  }

  const _startHeartbeat = (): void => {
    _stopHeartbeat()
    heartbeatTimer = setInterval(() => {
      sendHeartbeat()
    }, 30000)
  }

  const _stopHeartbeat = (): void => {
    if (heartbeatTimer) {
      clearInterval(heartbeatTimer)
      heartbeatTimer = null
    }
  }

  const _tryReconnect = (): void => {
    if (
      !isAuthenticated.value
      || reconnectAttempts >= MAX_RECONNECT_ATTEMPTS
      || reconnectTimer
    ) return

    const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000)
    reconnectAttempts++
    console.log(`Voice reconnecting in ${delay}ms (attempt ${reconnectAttempts})`)
    status.value.error = `Reconnecting... (${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`

    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      connect()
    }, delay)
  }

  const disconnect = (): void => {
    _stopHeartbeat()
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    reconnectAttempts = MAX_RECONNECT_ATTEMPTS
    if (ws) {
      ws.close()
      ws = null
    }
    status.value.connected = false
  }

  const setLanguage = (lang: string): void => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'language_change', language: lang }))
    }
  }

  /**
   * Handle server messages
   */
  const handleServerMessage = (message: any): void => {
    console.log('Server message:', message)

    switch (message.type) {
      case 'connected':
        console.log('Connection confirmed:', message.client_id)
        // A fresh connection has no held transmission in flight.
        status.value.pendingInstructor = false
        break

      case 'processing':
        status.value.processing = true
        break

      case 'awaiting_instructor':
        // The exchange is held: no ATC audio will follow until an instructor
        // releases it, so stop the spinner and show the pending state.
        status.value.processing = false
        status.value.pendingInstructor = true
        break

      case 'response_complete':
        status.value.processing = false
        status.value.pendingInstructor = false
        break

      case 'error':
        status.value.error = message.message
        status.value.processing = false
        break

      case 'pong':
        // Heartbeat response
        break
    }
  }

  /**
   * Start recording audio from microphone
   */
  const startRecording = async (): Promise<void> => {
    try {
      // Request microphone access
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1, // Mono
          sampleRate: 16000, // 16kHz for Whisper
          echoCancellation: true,
          noiseSuppression: true,
        },
      })

      // Create MediaRecorder
      mediaRecorder = new MediaRecorder(stream, {
        mimeType: 'audio/webm;codecs=opus',
      })

      audioChunks = []

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunks.push(event.data)
        }
      }

      mediaRecorder.onstop = async () => {
        // Create audio blob
        const audioBlob = new Blob(audioChunks, { type: 'audio/webm' })

        // Convert to WAV and send to server
        await sendAudio(audioBlob)

        // Stop all tracks
        stream.getTracks().forEach(track => track.stop())
      }

      // Start recording
      mediaRecorder.start()
      status.value.recording = true
      status.value.error = null

      console.log('Recording started')
    }
    catch (error) {
      console.error('Failed to start recording:', error)
      status.value.error = 'Microphone access denied'
    }
  }

  /**
   * Stop recording and send audio to server
   */
  const stopRecording = (): void => {
    if (mediaRecorder && status.value.recording) {
      mediaRecorder.stop()
      status.value.recording = false
      console.log('Recording stopped')
    }
  }

  /**
   * Send audio data to server via WebSocket
   */
  const sendAudio = async (audioBlob: Blob): Promise<void> => {
    if (!ws || ws.readyState !== WebSocket.OPEN) {
      status.value.error = 'Not connected to server'
      return
    }

    try {
      // Convert blob to ArrayBuffer
      const arrayBuffer = await audioBlob.arrayBuffer()

      // Send audio data
      ws.send(arrayBuffer)

      // Send end signal
      ws.send(JSON.stringify({ type: 'audio_end' }))

      console.log('Audio sent to server')
    }
    catch (error) {
      console.error('Failed to send audio:', error)
      status.value.error = 'Failed to send audio'
    }
  }

  /**
   * Play audio response from server
   */
  const playAudio = async (audioBlob: Blob): Promise<void> => {
    try {
      status.value.speaking = true

      // Create audio element
      const audioUrl = URL.createObjectURL(audioBlob)
      const audio = new Audio(audioUrl)

      // Play audio
      audio.onended = () => {
        status.value.speaking = false
        URL.revokeObjectURL(audioUrl)
      }

      audio.onerror = () => {
        status.value.speaking = false
        status.value.error = 'Failed to play audio'
        URL.revokeObjectURL(audioUrl)
      }

      await audio.play()

      console.log('Playing ATC response')
    }
    catch (error) {
      console.error('Failed to play audio:', error)
      status.value.speaking = false
      status.value.error = 'Failed to play audio'
    }
  }

  /**
   * Reset conversation
   */
  const resetConversation = (): void => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'reset' }))
    }
  }

  /**
   * Send heartbeat
   */
  const sendHeartbeat = (): void => {
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.send(JSON.stringify({ type: 'ping' }))
    }
  }

  // Cleanup on unmount
  onUnmounted(() => {
    disconnect()
  })

  return {
    status,
    connect,
    disconnect,
    setLanguage,
    startRecording,
    stopRecording,
    resetConversation,
    sendHeartbeat,
  }
}

export function useVoiceCommStatus(): Ref<VoiceCommStatus> {
  return useVoiceComm().status
}
