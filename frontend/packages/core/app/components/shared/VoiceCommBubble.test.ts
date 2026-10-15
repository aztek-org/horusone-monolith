import { mount } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import VoiceCommBubble from './VoiceCommBubble.vue'

const mocks = vi.hoisted(() => ({
  status: null as null | { value: Record<string, unknown> },
  isAuthenticated: null as null | { value: boolean },
  connect: vi.fn(),
  disconnect: vi.fn(),
  startRecording: vi.fn(),
  stopRecording: vi.fn(),
}))

vi.mock('../../composables/useVoiceComm', async () => {
  const { ref } = await import('vue')
  mocks.status = ref({
    connected: true,
    recording: false,
    processing: false,
    speaking: false,
    error: null,
  })
  return {
    useVoiceComm: () => ({
      status: mocks.status,
      connect: mocks.connect,
      disconnect: mocks.disconnect,
      startRecording: mocks.startRecording,
      stopRecording: mocks.stopRecording,
    }),
  }
})

vi.mock('../../composables/useAuth', async () => {
  const { ref } = await import('vue')
  mocks.isAuthenticated = ref(false)
  return { useAuth: () => ({ isAuthenticated: mocks.isAuthenticated }) }
})

const globalStubs = {
  global: {
    stubs: {
      Icon: { template: '<span class="icon-stub" />' },
      NuxtIcon: { template: '<span class="icon-stub" />' },
    },
  },
}

describe('VoiceCommBubble', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    if (mocks.status) {
      Object.assign(mocks.status.value, {
        connected: true,
        recording: false,
        processing: false,
        speaking: false,
        error: null,
      })
    }
    if (mocks.isAuthenticated) mocks.isAuthenticated.value = false
  })

  it('renders the mic button', () => {
    const wrapper = mount(VoiceCommBubble, globalStubs)
    expect(wrapper.find('button').exists()).toBe(true)
    expect(wrapper.find('.icon-stub').exists()).toBe(true)
  })

  it('disables the button while disconnected', () => {
    if (mocks.status) mocks.status.value.connected = false
    const wrapper = mount(VoiceCommBubble, globalStubs)
    expect(wrapper.find('button').attributes('disabled')).toBeDefined()
  })

  it('starts recording on mouse down when connected', async () => {
    const wrapper = mount(VoiceCommBubble, globalStubs)
    await wrapper.find('button').trigger('mousedown')
    expect(mocks.startRecording).toHaveBeenCalled()
  })

  it('does not start recording while disconnected', async () => {
    if (mocks.status) mocks.status.value.connected = false
    const wrapper = mount(VoiceCommBubble, globalStubs)
    await wrapper.find('button').trigger('mousedown')
    expect(mocks.startRecording).not.toHaveBeenCalled()
  })

  it('stops recording on mouse up while recording', async () => {
    if (mocks.status) mocks.status.value.recording = true
    const wrapper = mount(VoiceCommBubble, globalStubs)
    await wrapper.find('button').trigger('mouseup')
    expect(mocks.stopRecording).toHaveBeenCalled()
  })

  it('renders the error notification when status has an error', () => {
    if (mocks.status) mocks.status.value.error = 'Microphone unavailable'
    const wrapper = mount(VoiceCommBubble, globalStubs)
    expect(wrapper.text()).toContain('Microphone unavailable')
  })

  it('shows a connected indicator title', () => {
    const wrapper = mount(VoiceCommBubble, globalStubs)
    expect(wrapper.find('div[title="Connected to ATC"]').exists()).toBe(true)
  })
})
