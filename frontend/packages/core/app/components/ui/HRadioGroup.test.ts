import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import HRadioGroup from './HRadioGroup.vue'

const options = [
  { value: 'beginner', label: 'Beginner' },
  { value: 'advanced', label: 'Advanced' },
]

describe('HRadioGroup', () => {
  it('renders every option label', () => {
    const wrapper = mount(HRadioGroup, {
      props: { modelValue: 'beginner', options, name: 'level' },
    })
    expect(wrapper.text()).toContain('Beginner')
    expect(wrapper.text()).toContain('Advanced')
  })

  it('applies the selected class to the matching option', () => {
    const wrapper = mount(HRadioGroup, {
      props: { modelValue: 'beginner', options, name: 'level' },
    })
    const buttons = wrapper.findAll('button')
    expect(buttons[0]!.classes()).toContain('bg-horus-accent-cyan/10')
    expect(buttons[1]!.classes()).not.toContain('bg-horus-accent-cyan/10')
  })

  it('renders the inner selection dot only for the selected option', () => {
    const wrapper = mount(HRadioGroup, {
      props: { modelValue: 'advanced', options, name: 'level' },
    })
    expect(wrapper.findAll('.bg-horus-accent-cyan')).toHaveLength(1)
  })

  it('emits update:modelValue when another option is clicked', async () => {
    const wrapper = mount(HRadioGroup, {
      props: { modelValue: 'beginner', options, name: 'level' },
    })
    await wrapper.findAll('button')[1]!.trigger('click')
    expect(wrapper.emitted('update:modelValue')).toEqual([['advanced']])
  })
})
