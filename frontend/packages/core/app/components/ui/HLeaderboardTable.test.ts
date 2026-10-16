import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import HLeaderboardTable from './HLeaderboardTable.vue'

const globalStubs = {
  global: {
    stubs: {
      Icon: { template: '<span class="icon-stub" />' },
      NuxtIcon: { template: '<span class="icon-stub" />' },
      HCard: { template: '<div class="h-card"><slot /></div>' },
    },
  },
}

const entries = [
  {
    user_id: 'u1',
    rank: 1,
    display_name: 'Maverick',
    avatar_seed: 'maverick',
    flight_hours: 120.456,
    scenarios_completed: 30,
    total_score: 12345,
    badges_count: 7,
    email: 'maverick@horus.test',
    category_scores: { communication: 80, decision_making: 90, procedures: 85 },
  },
  {
    user_id: 'u2',
    rank: 4,
    display_name: 'Goose',
    avatar_seed: 'goose',
    flight_hours: 10,
    scenarios_completed: 3,
    total_score: 900,
    badges_count: 1,
    email: 'goose@horus.test',
    category_scores: { communication: 70, decision_making: 75, procedures: 72 },
  },
]

describe('HLeaderboardTable', () => {
  it('renders an empty state when there are no entries', () => {
    const wrapper = mount(HLeaderboardTable, {
      ...globalStubs,
      props: { entries: [] },
    })
    expect(wrapper.text()).toContain('No leaderboard data yet')
  })

  it('renders pilot names and formatted scores', () => {
    const wrapper = mount(HLeaderboardTable, { ...globalStubs, props: { entries } })
    expect(wrapper.text()).toContain('Maverick')
    expect(wrapper.text()).toContain('Goose')
    expect(wrapper.text()).toContain('12,345')
    expect(wrapper.text()).toContain('900')
  })

  it('shows a medal emoji for top three ranks', () => {
    const wrapper = mount(HLeaderboardTable, { ...globalStubs, props: { entries } })
    expect(wrapper.text()).toContain('🥇')
  })

  it('renders the numeric rank for positions outside the top three', () => {
    const wrapper = mount(HLeaderboardTable, { ...globalStubs, props: { entries } })
    expect(wrapper.text()).toContain('4')
  })

  it('marks the current user and appends (You)', () => {
    const wrapper = mount(HLeaderboardTable, {
      ...globalStubs,
      props: { entries, currentUserId: 'u2' },
    })
    expect(wrapper.text()).toContain('(You)')
  })

  it('formats flight hours to one decimal place', () => {
    const wrapper = mount(HLeaderboardTable, { ...globalStubs, props: { entries } })
    expect(wrapper.text()).toContain('120.5h')
  })

  it('hides the badges column when showBadges is false', () => {
    const wrapper = mount(HLeaderboardTable, {
      ...globalStubs,
      props: { entries, showBadges: false },
    })
    expect(wrapper.text()).not.toContain('Badges')
  })

  it('shows the badges column by default', () => {
    const wrapper = mount(HLeaderboardTable, { ...globalStubs, props: { entries } })
    expect(wrapper.text()).toContain('Badges')
  })
})
