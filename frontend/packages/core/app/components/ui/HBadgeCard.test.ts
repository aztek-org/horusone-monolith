import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import HBadgeCard from './HBadgeCard.vue'

const globalStubs = {
  global: {
    stubs: {
      Icon: { template: '<span class="icon-stub" />' },
      NuxtIcon: { template: '<span class="icon-stub" />' },
    },
  },
}

describe('HBadgeCard', () => {
  const baseProps = {
    name: 'First Solo',
    description: 'Complete your first solo flight',
    icon: '🏅',
    tier: 'gold' as const,
    category: 'flight' as const,
    earned: false,
  }

  it('renders name and description', () => {
    const wrapper = mount(HBadgeCard, { ...globalStubs, props: baseProps })
    expect(wrapper.text()).toContain('First Solo')
    expect(wrapper.text()).toContain('Complete your first solo flight')
  })

  it('renders the tier label and category label', () => {
    const wrapper = mount(HBadgeCard, { ...globalStubs, props: baseProps })
    expect(wrapper.text()).toContain('Gold')
    expect(wrapper.text()).toContain('Flight')
  })

  it('renders a lock icon and no earned icon when not earned', () => {
    const wrapper = mount(HBadgeCard, { ...globalStubs, props: baseProps })
    expect(wrapper.text()).not.toContain('🏅')
    expect(wrapper.find('.icon-stub').exists()).toBe(true)
  })

  it('shows the earned date when earned with an earnedAt value', () => {
    const wrapper = mount(HBadgeCard, {
      ...globalStubs,
      props: { ...baseProps, earned: true, earnedAt: '2024-01-15' },
    })
    expect(wrapper.text()).toContain('Earned')
    expect(wrapper.text()).toContain('🏅')
  })

  it('shows the rounded progress percentage when not earned and progress > 0', () => {
    const wrapper = mount(HBadgeCard, {
      ...globalStubs,
      props: { ...baseProps, progress: 42.6 },
    })
    expect(wrapper.text()).toContain('Progress')
    expect(wrapper.text()).toContain('43%')
  })

  it('does not show the progress bar when progress is 0', () => {
    const wrapper = mount(HBadgeCard, { ...globalStubs, props: baseProps })
    expect(wrapper.text()).not.toContain('Progress')
  })

  it('applies a dimmed style when not earned', () => {
    const wrapper = mount(HBadgeCard, { ...globalStubs, props: baseProps })
    expect(wrapper.classes().join(' ')).toContain('opacity-60')
  })
})
