import { mount, flushPromises } from '@vue/test-utils'
import { describe, it, expect, vi, beforeEach } from 'vitest'
import InstructorReviewPanel from './InstructorReviewPanel.vue'

const mocks = vi.hoisted(() => ({
  getSessionEvents: vi.fn(),
  respondToHeldExchange: vi.fn(),
}))

vi.mock('../../composables/useInstructor', async () => {
  const actual = await vi.importActual<typeof import('../../composables/useInstructor')>(
    '../../composables/useInstructor',
  )
  return {
    ...actual,
    useInstructor: () => ({
      getSessionEvents: mocks.getSessionEvents,
      respondToHeldExchange: mocks.respondToHeldExchange,
    }),
  }
})

const globalStubs = {
  global: {
    stubs: {
      Icon: { template: '<span class="icon-stub" />' },
      NuxtIcon: { template: '<span class="icon-stub" />' },
      HCard: { template: '<div><slot /></div>' },
      HButton: {
        props: ['disabled', 'loading', 'variant', 'size'],
        emits: ['click'],
        template: '<button @click="$emit(\'click\')"><slot /></button>',
      },
    },
  },
}

const heldEvent = { event_type: 'awaiting_instructor' }
const resolvedEvent = { event_type: 'exchange_completed' }

describe('InstructorReviewPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.getSessionEvents.mockResolvedValue([heldEvent])
    mocks.respondToHeldExchange.mockResolvedValue({
      session_id: 5,
      applied: true,
      atc_response: 'Cleared',
      exchange_count: 2,
      pending_instructor: false,
      instructor_overridden: true,
    })
  })

  it('shows review actions when the last exchange is held', async () => {
    const wrapper = mount(InstructorReviewPanel, {
      props: { sessionId: 5 },
      ...globalStubs,
    })
    await flushPromises()

    expect(mocks.getSessionEvents).toHaveBeenCalledWith(5)
    expect(wrapper.text()).toContain('Send override')
    expect(wrapper.find('[data-testid="release-ai-response"]').exists()).toBe(true)
  })

  it('shows an empty state when nothing is held', async () => {
    mocks.getSessionEvents.mockResolvedValue([resolvedEvent])
    const wrapper = mount(InstructorReviewPanel, {
      props: { sessionId: 5 },
      ...globalStubs,
    })
    await flushPromises()

    expect(wrapper.text()).toContain('No exchange is awaiting review')
    expect(wrapper.find('[data-testid="release-ai-response"]').exists()).toBe(false)
  })

  it('sends an override with the entered text', async () => {
    const wrapper = mount(InstructorReviewPanel, {
      props: { sessionId: 5 },
      ...globalStubs,
    })
    await flushPromises()

    const textarea = wrapper.find('textarea')
    await textarea.setValue('Cleared for takeoff')
    await wrapper.find('button').trigger('click')
    await flushPromises()

    expect(mocks.respondToHeldExchange).toHaveBeenCalledWith(5, 'Cleared for takeoff')
    expect(wrapper.emitted('released')).toBeTruthy()
    expect(wrapper.text()).toContain('No exchange is awaiting review')
  })

  it('releases the AI response when no text is entered', async () => {
    const wrapper = mount(InstructorReviewPanel, {
      props: { sessionId: 5 },
      ...globalStubs,
    })
    await flushPromises()

    await wrapper.find('[data-testid="release-ai-response"]').trigger('click')
    await flushPromises()

    expect(mocks.respondToHeldExchange).toHaveBeenCalledWith(5, undefined)
    expect(wrapper.emitted('released')).toBeTruthy()
  })

  it('surfaces a load error', async () => {
    mocks.getSessionEvents.mockRejectedValue({ detail: 'Session not found' })
    const wrapper = mount(InstructorReviewPanel, {
      props: { sessionId: 404 },
      ...globalStubs,
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Session not found')
  })
})
