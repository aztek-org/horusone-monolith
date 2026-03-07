import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import HButton from './HButton.vue'

// Icon is registered globally by @nuxt/icon as NuxtIcon — stub both names
const globalStubs = {
  global: {
    stubs: {
      Icon: { template: '<span />' },
      NuxtIcon: { template: '<span />' },
    },
  },
}

describe('HButton', () => {
  it('renders slot content', () => {
    const wrapper = mount(HButton, {
      ...globalStubs,
      slots: { default: 'Click me' },
    })
    expect(wrapper.text()).toContain('Click me')
  })

  it('emits click event when clicked', async () => {
    const wrapper = mount(HButton, {
      ...globalStubs,
      slots: { default: 'Click me' },
    })
    await wrapper.trigger('click')
    expect(wrapper.emitted('click')).toBeTruthy()
  })

  it('does not emit click when disabled', async () => {
    const wrapper = mount(HButton, {
      ...globalStubs,
      props: { disabled: true },
      slots: { default: 'Click me' },
    })
    await wrapper.trigger('click')
    expect(wrapper.emitted('click')).toBeFalsy()
  })

  it('does not emit click when loading', async () => {
    const wrapper = mount(HButton, {
      ...globalStubs,
      props: { loading: true },
      slots: { default: 'Click me' },
    })
    await wrapper.trigger('click')
    expect(wrapper.emitted('click')).toBeFalsy()
  })

  it('applies variant class for primary variant', () => {
    const wrapper = mount(HButton, { ...globalStubs, props: { variant: 'primary' } })
    expect(wrapper.classes().join(' ')).toContain('bg-horus-accent-cyan')
  })
})
