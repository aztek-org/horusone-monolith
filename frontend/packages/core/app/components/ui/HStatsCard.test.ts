import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import HStatsCard from './HStatsCard.vue'

// Stub child components
const globalStubs = {
  global: {
    stubs: {
      Icon: { template: '<span />' },
      NuxtIcon: { template: '<span />' },
      HCard: { template: '<div class="h-card"><slot /></div>' },
    },
  },
}

describe('HStatsCard', () => {
  it('renders label and value', () => {
    const wrapper = mount(HStatsCard, {
      ...globalStubs,
      props: { label: 'Flight Hours', value: '42.5' },
    })
    expect(wrapper.text()).toContain('Flight Hours')
    expect(wrapper.text()).toContain('42.5')
  })

  it('renders unit when provided', () => {
    const wrapper = mount(HStatsCard, {
      ...globalStubs,
      props: { label: 'Flight Hours', value: '42.5', unit: 'hrs' },
    })
    expect(wrapper.text()).toContain('hrs')
  })

  it('renders trend value when trend is up', () => {
    const wrapper = mount(HStatsCard, {
      ...globalStubs,
      props: { label: 'Score', value: '85', trend: 'up' as const, trendValue: '+5%' },
    })
    expect(wrapper.text()).toContain('+5%')
  })

  it('does not render trend indicator when trend is stable', () => {
    const wrapper = mount(HStatsCard, {
      ...globalStubs,
      props: { label: 'Score', value: '85', trend: 'stable' as const },
    })
    // Stable trend should not show trend section
    const trendSection = wrapper.find('.flex.items-center.gap-1.mt-1\\.5')
    expect(trendSection.exists()).toBe(false)
  })

  it('accepts numeric value prop', () => {
    const wrapper = mount(HStatsCard, {
      ...globalStubs,
      props: { label: 'Count', value: 10 },
    })
    expect(wrapper.text()).toContain('10')
  })
})
