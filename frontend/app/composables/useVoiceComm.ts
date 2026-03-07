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
  error: string | null
}

export const useVoiceComm = () => {
  // State
  const status = ref<VoiceCommStatus>({
    connected: false,
    recording: false,
    processing: false,
    speaking: false,
    error: null,
  })

  // WebSocket connection
  let ws: WebSocket | null = null
  let mediaRecorder: MediaRecorder | null = null
  let audioContext: AudioContext | null = null
  let audioChunks: Blob[] = []

  // WebSocket URL from runtime config (set via NUXT_PUBLIC_WS_URL env var)
  const config = useRuntimeConfig()
  const wsUrl = config.public.wsUrl as string

  /**
   * Connect to the WebSocket server
   */
  const connect = async (): Promise<void> => {
    try {
      ws = new WebSocket(wsUrl)

      ws.onopen = () => {
        console.log('Voice communication connected')
        status.value.connected = true
        status.value.error = null
      }

      ws.onmessage = async (event) => {
        // Handle binary audio data
        if (event.data instanceof Blob) {
          console.log('Received audio response')
          await playAudio(event.data)
        }
        // Handle JSON messages
        else if (typeof event.data === 'string') {
          try {
            const message = JSON.parse(event.data)
            handleServerMessage(message)
          } catch (e) {
            console.error('Failed to parse server message:', e)
          }
        }
      }

      ws.onerror = (error) => {
        console.error('WebSocket error:', error)
        status.value.error = 'Connection error'
        status.value.connected = false
      }

      ws.onclose = () => {
        console.log('Voice communication disconnected')
        status.value.connected = false
      }
    } catch (error) {
      console.error('Failed to connect:', error)
      status.value.error = 'Failed to connect to server'
    }
  }

  /**
   * Disconnect from WebSocket
   */
  const disconnect = (): void => {
    if (ws) {
      ws.close()
      ws = null
    }
    status.value.connected = false
  }

  /**
   * Handle server messages
   */
  const handleServerMessage = (message: any): void => {
    console.log('Server message:', message)

    switch (message.type) {
      case 'connected':
        console.log('Connection confirmed:', message.client_id)
        break

      case 'processing':
        status.value.processing = true
        break

      case 'response_complete':
        status.value.processing = false
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
        stream.getTracks().forEach((track) => track.stop())
      }

      // Start recording
      mediaRecorder.start()
      status.value.recording = true
      status.value.error = null

      console.log('Recording started')
    } catch (error) {
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
    } catch (error) {
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
    } catch (error) {
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
    startRecording,
    stopRecording,
    resetConversation,
    sendHeartbeat,
  }
}
