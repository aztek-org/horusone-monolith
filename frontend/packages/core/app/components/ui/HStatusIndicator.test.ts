import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import HStatusIndicator from './HStatusIndicator.vue'

describe('HStatusIndicator', () => {
  it('renders the label and value', () => {
    const wrapper = mount(HStatusIndicator, {
      props: { status: 'nominal', label: 'Hydraulics', value: 'OK' },
    })
    expect(wrapper.text()).toContain('Hydraulics')
    expect(wrapper.text()).toContain('OK')
  })

  it('does not render a value when omitted', () => {
    const wrapper = mount(HStatusIndicator, {
      props: { status: 'nominal', label: 'Hydraulics' },
    })
    expect(wrapper.find('p').exists()).toBe(false)
  })

  it('applies the nominal success colors', () => {
    const wrapper = mount(HStatusIndicator, {
      props: { status: 'nominal', label: 'Hydraulics', value: 'OK' },
    })
    expect(wrapper.find('.bg-horus-status-success').exists()).toBe(true)
    expect(wrapper.find('p').classes()).toContain('text-horus-status-success')
  })

  it('applies the critical danger colors with a pulsing dot', () => {
    const wrapper = mount(HStatusIndicator, {
      props: { status: 'critical', label: 'Hydraulics', value: 'FAIL' },
    })
    const dot = wrapper.find('.bg-horus-status-danger')
    expect(dot.exists()).toBe(true)
    expect(dot.classes()).toContain('animate-pulse')
  })

  it('applies muted colors when offline', () => {
    const wrapper = mount(HStatusIndicator, {
      props: { status: 'offline', label: 'Hydraulics' },
    })
    expect(wrapper.find('.bg-horus-text-muted').exists()).toBe(true)
  })
})
