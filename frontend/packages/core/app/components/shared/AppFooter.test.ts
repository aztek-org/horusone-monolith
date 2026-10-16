import { mount } from '@vue/test-utils'
import { describe, it, expect, vi } from 'vitest'
import AppFooter from './AppFooter.vue'

vi.mock('../../composables/useSimulationState', () => ({
  useSimulationState: () => ({
    state: { latency: 42, systemLoad: 1.25 },
  }),
}))

describe('AppFooter', () => {
  it('renders the default route id and validated status', () => {
    const wrapper = mount(AppFooter)
    expect(wrapper.text()).toContain('LAX-TYO-992')
    expect(wrapper.text()).toContain('VALIDATED')
  })

  it('renders a custom route id', () => {
    const wrapper = mount(AppFooter, { props: { routeId: 'JFK-LAX-001' } })
    expect(wrapper.text()).toContain('JFK-LAX-001')
  })

  it('renders PENDING when not validated', () => {
    const wrapper = mount(AppFooter, { props: { validated: false } })
    expect(wrapper.text()).toContain('PENDING')
    expect(wrapper.text()).not.toContain('VALIDATED')
  })

  it('renders simulation metrics from the composable state', () => {
    const wrapper = mount(AppFooter)
    expect(wrapper.text()).toContain('42ms')
    expect(wrapper.text()).toContain('1.3 TFLOPS')
  })
})
