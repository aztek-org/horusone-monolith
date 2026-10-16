import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import HProgress from './HProgress.vue'

describe('HProgress', () => {
  it('renders the label and rounded percentage', () => {
    const wrapper = mount(HProgress, { props: { value: 50, label: 'Training' } })
    expect(wrapper.text()).toContain('Training')
    expect(wrapper.text()).toContain('50% COMPLETE')
  })

  it('rounds the percentage to the nearest integer', () => {
    const wrapper = mount(HProgress, { props: { value: 1, max: 3 } })
    expect(wrapper.text()).toContain('33% COMPLETE')
  })

  it('hides the percentage when showPercentage is false', () => {
    const wrapper = mount(HProgress, { props: { value: 50, showPercentage: false, label: 'Training' } })
    expect(wrapper.text()).not.toContain('COMPLETE')
  })

  it('clamps the fill width between 0 and 100%', () => {
    const high = mount(HProgress, { props: { value: 250, max: 100 } })
    expect(high.find('.h-full').attributes('style')).toContain('width: 100%')

    const low = mount(HProgress, { props: { value: -10 } })
    expect(low.find('.h-full').attributes('style')).toContain('width: 0%')
  })

  it('applies the explicit success variant color', () => {
    const wrapper = mount(HProgress, { props: { value: 30, variant: 'success' } })
    expect(wrapper.find('.h-full').classes()).toContain('bg-horus-status-success')
  })

  it('auto-colors the fill green at 75% or above', () => {
    const wrapper = mount(HProgress, { props: { value: 80 } })
    expect(wrapper.find('.h-full').classes()).toContain('bg-horus-status-success')
  })

  it('auto-colors the fill danger below 20%', () => {
    const wrapper = mount(HProgress, { props: { value: 10 } })
    expect(wrapper.find('.h-full').classes()).toContain('bg-horus-status-danger')
  })

  it('applies the small height class', () => {
    const wrapper = mount(HProgress, { props: { value: 50, size: 'sm' } })
    expect(wrapper.find('.h-1').exists()).toBe(true)
  })
})
