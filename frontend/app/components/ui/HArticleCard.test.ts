import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import HArticleCard from './HArticleCard.vue'

// Stub child components
const mountOptions = {
  global: {
    stubs: {
      Icon: { template: '<span />' },
      NuxtIcon: { template: '<span />' },
      HCard: {
        template: '<div class="h-card"><slot /></div>',
      },
      HBadge: { template: '<span class="h-badge"><slot /></span>' },
    },
  },
}

describe('HArticleCard', () => {
  const baseProps = {
    title: 'Principles of Flight',
    summary: 'Learn about the four forces of flight.',
    slug: 'principles-of-flight',
  }

  it('renders title and summary', () => {
    const wrapper = mount(HArticleCard, {
      ...mountOptions,
      props: baseProps,
    })
    expect(wrapper.text()).toContain('Principles of Flight')
    expect(wrapper.text()).toContain('Learn about the four forces of flight.')
  })

  it('renders category when provided', () => {
    const wrapper = mount(HArticleCard, {
      ...mountOptions,
      props: { ...baseProps, category: 'Aerodynamics' },
    })
    expect(wrapper.text()).toContain('Aerodynamics')
  })

  it('renders tags when provided', () => {
    const wrapper = mount(HArticleCard, {
      ...mountOptions,
      props: { ...baseProps, tags: ['lift', 'drag', 'thrust'] },
    })
    expect(wrapper.text()).toContain('lift')
    expect(wrapper.text()).toContain('drag')
    expect(wrapper.text()).toContain('thrust')
  })

  it('truncates tags to 4 and shows overflow count', () => {
    const wrapper = mount(HArticleCard, {
      ...mountOptions,
      props: { ...baseProps, tags: ['a', 'b', 'c', 'd', 'e', 'f'] },
    })
    expect(wrapper.text()).toContain('+2')
  })

  it('renders difficulty badge when provided', () => {
    const wrapper = mount(HArticleCard, {
      ...mountOptions,
      props: { ...baseProps, difficulty: 'intermediate' as const },
    })
    expect(wrapper.text()).toContain('Intermediate')
  })
})
