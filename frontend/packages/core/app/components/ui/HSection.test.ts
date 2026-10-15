import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import HSection from './HSection.vue'

const globalStubs = {
  global: {
    stubs: {
      Icon: { template: '<span class="icon-stub" />' },
      NuxtIcon: { template: '<span class="icon-stub" />' },
    },
  },
}

describe('HSection', () => {
  it('renders the title and slot content', () => {
    const wrapper = mount(HSection, {
      ...globalStubs,
      props: { title: 'Weather' },
      slots: { default: 'Clear skies' },
    })
    expect(wrapper.text()).toContain('Weather')
    expect(wrapper.text()).toContain('Clear skies')
  })

  it('disables the header button when not collapsible', () => {
    const wrapper = mount(HSection, {
      ...globalStubs,
      props: { title: 'Weather' },
    })
    expect(wrapper.find('button').attributes('disabled')).toBeDefined()
  })

  it('renders the icon when provided', () => {
    const wrapper = mount(HSection, {
      ...globalStubs,
      props: { title: 'Weather', icon: 'heroicons:cloud' },
    })
    expect(wrapper.find('.icon-stub').exists()).toBe(true)
  })

  it('shows content by default when collapsible and expanded', () => {
    const wrapper = mount(HSection, {
      ...globalStubs,
      props: { title: 'Weather', collapsible: true },
      slots: { default: 'Clear skies' },
    })
    expect(wrapper.find('.space-y-2').attributes('style') || '').not.toContain('display: none')
  })

  it('collapses the content when the header is clicked', async () => {
    const wrapper = mount(HSection, {
      ...globalStubs,
      props: { title: 'Weather', collapsible: true },
      slots: { default: 'Clear skies' },
    })
    await wrapper.find('button').trigger('click')
    expect(wrapper.find('.space-y-2').attributes('style')).toContain('display: none')
  })

  it('hides content when defaultExpanded is false', () => {
    const wrapper = mount(HSection, {
      ...globalStubs,
      props: { title: 'Weather', collapsible: true, defaultExpanded: false },
      slots: { default: 'Clear skies' },
    })
    expect(wrapper.find('.space-y-2').attributes('style')).toContain('display: none')
  })
})
