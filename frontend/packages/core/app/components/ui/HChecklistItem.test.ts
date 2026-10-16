import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import HChecklistItem from './HChecklistItem.vue'

const globalStubs = {
  global: {
    stubs: {
      Icon: { template: '<span class="icon-stub" />' },
      NuxtIcon: { template: '<span class="icon-stub" />' },
    },
  },
}

describe('HChecklistItem', () => {
  it('renders title, subtitle and meta', () => {
    const wrapper = mount(HChecklistItem, {
      ...globalStubs,
      props: { status: 'pending', title: 'Pre-flight', subtitle: 'Check fuel', meta: '2/5' },
    })
    expect(wrapper.text()).toContain('Pre-flight')
    expect(wrapper.text()).toContain('Check fuel')
    expect(wrapper.text()).toContain('2/5')
  })

  it('emits click when enabled', async () => {
    const wrapper = mount(HChecklistItem, {
      ...globalStubs,
      props: { status: 'pending', title: 'Pre-flight' },
    })
    await wrapper.find('button').trigger('click')
    expect(wrapper.emitted('click')).toBeTruthy()
  })

  it('marks the button disabled when disabled is true', () => {
    const wrapper = mount(HChecklistItem, {
      ...globalStubs,
      props: { status: 'pending', title: 'Pre-flight', disabled: true },
    })
    expect(wrapper.find('button').attributes('disabled')).toBeDefined()
    expect(wrapper.classes().join(' ')).toContain('cursor-not-allowed')
  })

  it('applies line-through styling to completed titles', () => {
    const wrapper = mount(HChecklistItem, {
      ...globalStubs,
      props: { status: 'completed', title: 'Pre-flight' },
    })
    expect(wrapper.find('.line-through').exists()).toBe(true)
  })

  it('renders a status icon', () => {
    const wrapper = mount(HChecklistItem, {
      ...globalStubs,
      props: { status: 'warning', title: 'Pre-flight' },
    })
    expect(wrapper.find('.icon-stub').exists()).toBe(true)
  })
})
