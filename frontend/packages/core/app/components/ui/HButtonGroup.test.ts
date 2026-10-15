import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import HButtonGroup from './HButtonGroup.vue'

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
  { value: 'b', label: 'Bravo', icon: 'heroicons:star' },
]

describe('HButtonGroup', () => {
  it('renders every option label', () => {
    const wrapper = mount(HButtonGroup, {
      ...globalStubs,
      props: { modelValue: 'a', options },
    })
    expect(wrapper.text()).toContain('Alpha')
    expect(wrapper.text()).toContain('Bravo')
  })

  it('applies the active class to the selected option', () => {
    const wrapper = mount(HButtonGroup, {
      ...globalStubs,
      props: { modelValue: 'a', options },
    })
    const buttons = wrapper.findAll('button')
    expect(buttons[0].classes()).toContain('bg-horus-accent-cyan')
    expect(buttons[1].classes()).not.toContain('bg-horus-accent-cyan')
  })

  it('emits update:modelValue when an option is clicked', async () => {
    const wrapper = mount(HButtonGroup, {
      ...globalStubs,
      props: { modelValue: 'a', options },
    })
    await wrapper.findAll('button')[1].trigger('click')
    expect(wrapper.emitted('update:modelValue')).toEqual([['b']])
  })

  it('renders an icon for options that provide one', () => {
    const wrapper = mount(HButtonGroup, {
      ...globalStubs,
      props: { modelValue: 'a', options },
    })
    expect(wrapper.findAll('.icon-stub')).toHaveLength(1)
  })

  it('applies the small size classes', () => {
    const wrapper = mount(HButtonGroup, {
      ...globalStubs,
      props: { modelValue: 'a', options, size: 'sm' },
    })
    expect(wrapper.findAll('button')[0].classes()).toContain('text-xs')
  })
})
