import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import HCard from './HCard.vue'

describe('HCard', () => {
  it('renders slot content', () => {
    const wrapper = mount(HCard, { slots: { default: 'Card body' } })
    expect(wrapper.text()).toContain('Card body')
  })

  it('applies the default variant classes', () => {
    const wrapper = mount(HCard)
    expect(wrapper.classes().join(' ')).toContain('bg-horus-bg-card/80')
  })

  it('applies the elevated variant classes', () => {
    const wrapper = mount(HCard, { props: { variant: 'elevated' } })
    expect(wrapper.classes().join(' ')).toContain('bg-horus-bg-elevated/90')
  })

  it('applies the glass variant classes', () => {
    const wrapper = mount(HCard, { props: { variant: 'glass' } })
    expect(wrapper.classes().join(' ')).toContain('backdrop-blur-lg')
  })

  it('applies the lg padding class', () => {
    const wrapper = mount(HCard, { props: { padding: 'lg' } })
    expect(wrapper.classes()).toContain('p-6')
  })

  it('applies no padding class when padding is none', () => {
    const wrapper = mount(HCard, { props: { padding: 'none' } })
    expect(wrapper.classes()).not.toContain('p-4')
    expect(wrapper.classes()).not.toContain('p-6')
  })

  it('applies the hover class when hover is true', () => {
    const wrapper = mount(HCard, { props: { hover: true } })
    expect(wrapper.classes().join(' ')).toContain('hover:border-horus-accent-cyan/30')
  })
})
