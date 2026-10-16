import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import HCheckbox from './HCheckbox.vue'

describe('HCheckbox', () => {
  it('renders the label and description', () => {
    const wrapper = mount(HCheckbox, {
      props: { modelValue: false, label: 'Enable voice', description: 'Turn on push-to-talk' },
    })
    expect(wrapper.text()).toContain('Enable voice')
    expect(wrapper.text()).toContain('Turn on push-to-talk')
  })

  it('does not render label or description when omitted', () => {
    const wrapper = mount(HCheckbox, { props: { modelValue: true } })
    expect(wrapper.find('span').exists()).toBe(false)
    expect(wrapper.find('p').exists()).toBe(false)
  })

  it('shows the checkmark when modelValue is true', () => {
    const wrapper = mount(HCheckbox, { props: { modelValue: true } })
    expect(wrapper.find('svg').exists()).toBe(true)
  })

  it('hides the checkmark when modelValue is false', () => {
    const wrapper = mount(HCheckbox, { props: { modelValue: false } })
    expect(wrapper.find('svg').exists()).toBe(false)
  })

  it('emits update:modelValue(true) when toggled from false', async () => {
    const wrapper = mount(HCheckbox, { props: { modelValue: false, label: 'Opt in' } })
    await wrapper.find('label').trigger('click')
    expect(wrapper.emitted('update:modelValue')).toEqual([[true]])
  })

  it('emits update:modelValue(false) when toggled from true', async () => {
    const wrapper = mount(HCheckbox, { props: { modelValue: true, label: 'Opt in' } })
    await wrapper.find('label').trigger('click')
    expect(wrapper.emitted('update:modelValue')).toEqual([[false]])
  })

  it('does not emit when disabled and marks itself disabled', async () => {
    const wrapper = mount(HCheckbox, {
      props: { modelValue: false, disabled: true, label: 'Opt in' },
    })
    await wrapper.find('label').trigger('click')
    expect(wrapper.emitted('update:modelValue')).toBeFalsy()
    expect(wrapper.classes().join(' ')).toContain('cursor-not-allowed')
  })
})
