import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import HDataPanel from './HDataPanel.vue'

const globalStubs = {
  global: {
    stubs: {
      Icon: { template: '<span class="icon-stub" />' },
      NuxtIcon: { template: '<span class="icon-stub" />' },
    },
  },
}

describe('HDataPanel', () => {
  it('renders value, label and unit', () => {
    const wrapper = mount(HDataPanel, {
      ...globalStubs,
      props: { value: 'FL350', label: 'Altitude', unit: 'ft' },
    })
    expect(wrapper.text()).toContain('FL350')
    expect(wrapper.text()).toContain('Altitude')
    expect(wrapper.text()).toContain('ft')
  })

  it('renders a numeric value', () => {
    const wrapper = mount(HDataPanel, { ...globalStubs, props: { value: 42 } })
    expect(wrapper.text()).toContain('42')
  })

  it('applies the large value size class', () => {
    const wrapper = mount(HDataPanel, {
      ...globalStubs,
      props: { value: 100, variant: 'large' },
    })
    expect(wrapper.find('span').classes()).toContain('text-3xl')
  })

  it('applies the compact value size class', () => {
    const wrapper = mount(HDataPanel, {
      ...globalStubs,
      props: { value: 100, variant: 'compact' },
    })
    expect(wrapper.find('span').classes()).toContain('text-lg')
  })

  it('applies the highlight text color', () => {
    const wrapper = mount(HDataPanel, {
      ...globalStubs,
      props: { value: 100, highlight: true },
    })
    expect(wrapper.find('span').classes()).toContain('text-horus-accent-cyan')
  })

  it('renders the trend value and icon when provided', () => {
    const wrapper = mount(HDataPanel, {
      ...globalStubs,
      props: { value: 100, trend: 'up', trendValue: '+12%' },
    })
    expect(wrapper.text()).toContain('+12%')
    expect(wrapper.find('.icon-stub').exists()).toBe(true)
  })

  it('does not render a trend section when no trend is provided', () => {
    const wrapper = mount(HDataPanel, { ...globalStubs, props: { value: 100 } })
    expect(wrapper.find('.icon-stub').exists()).toBe(false)
  })
})
