import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import HDropdown from './HDropdown.vue'

const globalStubs = {
  global: {
    stubs: {
      Icon: { template: '<span class="icon-stub" />' },
      NuxtIcon: { template: '<span class="icon-stub" />' },
    },
  },
}

const options = [
  { value: 'a', label: 'Alpha' },
  { value: 'b', label: 'Bravo' },
]

describe('HDropdown', () => {
  it('renders the label and options', () => {
    const wrapper = mount(HDropdown, {
      ...globalStubs,
      props: { modelValue: 'a', options, label: 'Choose' },
    })
    expect(wrapper.text()).toContain('Choose')
    expect(wrapper.text()).toContain('Alpha')
    expect(wrapper.text()).toContain('Bravo')
  })

  it('renders a disabled placeholder option by default', () => {
    const wrapper = mount(HDropdown, {
      ...globalStubs,
      props: { modelValue: '', options },
    })
    const placeholder = wrapper.find('option[value=""]')
    expect(placeholder.exists()).toBe(true)
    expect(placeholder.attributes('disabled')).toBeDefined()
  })

  it('emits update:modelValue when the selection changes', async () => {
    const wrapper = mount(HDropdown, {
      ...globalStubs,
      props: { modelValue: 'a', options },
    })
    await wrapper.find('select').setValue('b')
    expect(wrapper.emitted('update:modelValue')).toEqual([['b']])
  })

  it('disables the select when disabled is true', () => {
    const wrapper = mount(HDropdown, {
      ...globalStubs,
      props: { modelValue: 'a', options, disabled: true },
    })
    expect(wrapper.find('select').attributes('disabled')).toBeDefined()
  })

  it('renders a chevron icon', () => {
    const wrapper = mount(HDropdown, {
      ...globalStubs,
      props: { modelValue: 'a', options },
    })
    expect(wrapper.find('.icon-stub').exists()).toBe(true)
  })
})
