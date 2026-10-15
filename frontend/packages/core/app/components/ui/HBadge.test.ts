import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import HBadge from './HBadge.vue'

describe('HBadge', () => {
  it('renders slot content', () => {
    const wrapper = mount(HBadge, { slots: { default: 'Active' } })
    expect(wrapper.text()).toContain('Active')
  })

  it('applies the info variant classes', () => {
    const wrapper = mount(HBadge, { props: { variant: 'info' } })
    expect(wrapper.classes().join(' ')).toContain('text-horus-accent-cyan')
  })

  it('applies the danger variant classes', () => {
    const wrapper = mount(HBadge, { props: { variant: 'danger' } })
    expect(wrapper.classes().join(' ')).toContain('text-horus-status-danger')
  })

  it('applies the warning variant classes', () => {
    const wrapper = mount(HBadge, { props: { variant: 'warning' } })
    expect(wrapper.classes().join(' ')).toContain('text-horus-status-warning')
  })

  it('renders the pulse dot and animation when pulse is true', () => {
    const wrapper = mount(HBadge, { props: { pulse: true } })
    expect(wrapper.find('.rounded-full.bg-current').exists()).toBe(true)
    expect(wrapper.classes().join(' ')).toContain('animate-pulse-slow')
  })

  it('does not render the pulse dot by default', () => {
    const wrapper = mount(HBadge)
    expect(wrapper.find('.rounded-full.bg-current').exists()).toBe(false)
  })

  it('applies the small size padding', () => {
    const wrapper = mount(HBadge, { props: { size: 'sm' } })
    expect(wrapper.classes()).toContain('px-1.5')
  })

  it('applies the medium size padding', () => {
    const wrapper = mount(HBadge, { props: { size: 'md' } })
    expect(wrapper.classes()).toContain('px-2')
  })
})
