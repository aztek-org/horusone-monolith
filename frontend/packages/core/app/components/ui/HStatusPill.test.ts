import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import HStatusPill from './HStatusPill.vue'

describe('HStatusPill', () => {
  it('renders the label when provided', () => {
    const wrapper = mount(HStatusPill, { props: { label: 'Connected' } })
    expect(wrapper.text()).toContain('Connected')
  })

  it('renders the default slot when no label is provided', () => {
    const wrapper = mount(HStatusPill, { slots: { default: 'RADAR ONLINE' } })
    expect(wrapper.text()).toContain('RADAR ONLINE')
  })

  it('shows the offline muted colors when online is false', () => {
    const wrapper = mount(HStatusPill, { props: { online: false, label: 'Offline' } })
    const dot = wrapper.find('span.rounded-full')
    expect(dot.classes()).toContain('bg-horus-text-muted')
    expect(dot.classes()).not.toContain('animate-pulse')
  })

  it('pulses the dot when online', () => {
    const wrapper = mount(HStatusPill, { props: { label: 'Online' } })
    expect(wrapper.find('span.rounded-full').classes()).toContain('animate-pulse')
  })

  it('applies the danger variant colors', () => {
    const wrapper = mount(HStatusPill, { props: { variant: 'danger', label: 'Alarm' } })
    expect(wrapper.find('span.rounded-full').classes()).toContain('bg-horus-status-danger')
    expect(wrapper.find('.text-horus-status-danger').exists()).toBe(true)
  })

  it('applies the warning variant colors', () => {
    const wrapper = mount(HStatusPill, { props: { variant: 'warning', label: 'Caution' } })
    expect(wrapper.find('span.rounded-full').classes()).toContain('bg-horus-status-warning')
  })
})
