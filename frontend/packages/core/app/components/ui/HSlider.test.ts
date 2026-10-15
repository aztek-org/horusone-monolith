import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import HSlider from './HSlider.vue'

describe('HSlider', () => {
  it('renders the label and default percentage value', () => {
    const wrapper = mount(HSlider, { props: { modelValue: 50, label: 'Volume' } })
    expect(wrapper.text()).toContain('Volume')
    expect(wrapper.text()).toContain('50%')
  })

  it('uses a custom value formatter when provided', () => {
    const wrapper = mount(HSlider, {
      props: { modelValue: 50, valueFormat: (v: number) => `${v} kt` },
    })
    expect(wrapper.text()).toContain('50 kt')
  })

  it('hides the value when showValue is false', () => {
    const wrapper = mount(HSlider, { props: { modelValue: 50, showValue: false } })
    expect(wrapper.text()).not.toContain('50%')
  })

  it('emits a numeric update when the range input changes', async () => {
    const wrapper = mount(HSlider, { props: { modelValue: 10 } })
    await wrapper.find('input[type="range"]').setValue('42')
    expect(wrapper.emitted('update:modelValue')).toEqual([[42]])
  })

  it('applies the danger variant classes', () => {
    const wrapper = mount(HSlider, { props: { modelValue: 50, variant: 'danger' } })
    expect(wrapper.find('.h-full').classes()).toContain('bg-horus-status-danger')
  })

  it('passes min, max and step through to the native input', () => {
    const wrapper = mount(HSlider, { props: { modelValue: 5, min: 0, max: 10, step: 0.5 } })
    const input = wrapper.find('input[type="range"]')
    expect(input.attributes('min')).toBe('0')
    expect(input.attributes('max')).toBe('10')
    expect(input.attributes('step')).toBe('0.5')
  })
})
