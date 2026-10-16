import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import HLogEntry from './HLogEntry.vue'

describe('HLogEntry', () => {
  it('renders slot content with the default system prefix', () => {
    const wrapper = mount(HLogEntry, { slots: { default: 'Engine started' } })
    expect(wrapper.text()).toContain('Engine started')
    expect(wrapper.text()).toContain('SYS:')
  })

  it('renders the AI prefix for the ai type', () => {
    const wrapper = mount(HLogEntry, { props: { type: 'ai' }, slots: { default: 'Clearance' } })
    expect(wrapper.text()).toContain('AI:')
  })

  it('renders the USER prefix for the user type', () => {
    const wrapper = mount(HLogEntry, { props: { type: 'user' }, slots: { default: 'Roger' } })
    expect(wrapper.text()).toContain('USER:')
  })

  it('renders the ATC prefix for the atc type', () => {
    const wrapper = mount(HLogEntry, { props: { type: 'atc' }, slots: { default: 'Cleared' } })
    expect(wrapper.text()).toContain('ATC:')
  })

  it('renders the timestamp when provided', () => {
    const wrapper = mount(HLogEntry, {
      props: { timestamp: '12:00:01' },
      slots: { default: 'Event' },
    })
    expect(wrapper.text()).toContain('[12:00:01]')
  })

  it('does not render a timestamp when omitted', () => {
    const wrapper = mount(HLogEntry, { slots: { default: 'Event' } })
    expect(wrapper.text()).not.toContain('[')
  })

  it('applies the warning variant color to content', () => {
    const wrapper = mount(HLogEntry, {
      props: { variant: 'warning' },
      slots: { default: 'Caution' },
    })
    expect(wrapper.find('.text-horus-status-warning').exists()).toBe(true)
  })

  it('applies the info variant color to content', () => {
    const wrapper = mount(HLogEntry, {
      props: { variant: 'info' },
      slots: { default: 'Notice' },
    })
    expect(wrapper.find('.text-horus-accent-cyan').exists()).toBe(true)
  })
})
