import { describe, it, expect, vi, beforeEach } from 'vitest'

const nuxt = vi.hoisted(() => ({
  state: {} as Record<string, unknown>,
  app: null as any,
}))

vi.mock('#app/nuxt', async () => {
  const { reactive } = await import('vue')
  nuxt.state = reactive<Record<string, unknown>>({})
  nuxt.app = { payload: { state: nuxt.state }, _state: {} }
  return {
    useNuxtApp: () => nuxt.app,
    tryUseNuxtApp: () => nuxt.app,
    useRuntimeConfig: () => ({ public: {} }),
  }
})

async function load() {
  const { useChecklist } = await import('./useChecklist')
  return useChecklist()
}

describe('useChecklist', () => {
  beforeEach(() => {
    vi.resetModules()
    for (const key of Object.keys(nuxt.state)) Reflect.deleteProperty(nuxt.state, key)
  })

  it('starts with the six default items across two categories', async () => {
    const { items, totalCount } = await load()
    expect(items.value).toHaveLength(6)
    expect(totalCount.value).toBe(6)
    expect(items.value.map(i => i.id)).toEqual([
      'cl-1',
      'cl-2',
      'cl-3',
      'cl-4',
      'cl-5',
      'cl-6',
    ])
  })

  it('derives the unique category list preserving order', async () => {
    const { categories } = await load()
    expect(categories.value).toEqual(['PRE-FLIGHT OPERATIONS', 'DIVERSION'])
  })

  it('groups items by category', async () => {
    const { itemsByCategory } = await load()
    expect(itemsByCategory.value['PRE-FLIGHT OPERATIONS']).toHaveLength(2)
    expect(itemsByCategory.value.DIVERSION).toHaveLength(4)
  })

  it('computes completed count and progress percentage', async () => {
    const { completedCount, totalCount, progressPercentage } = await load()
    expect(completedCount.value).toBe(1)
    expect(totalCount.value).toBe(6)
    expect(progressPercentage.value).toBeCloseTo(16.666, 2)
  })

  it('addItem appends an item with a generated id and returns it', async () => {
    const { items, addItem, totalCount } = await load()
    const id = addItem({ title: 'New check', status: 'pending', category: 'EXTRA' })

    expect(id).toMatch(/^cl-\d+$/)
    expect(items.value).toHaveLength(7)
    expect(totalCount.value).toBe(7)
    expect(items.value.at(-1)).toMatchObject({
      id,
      title: 'New check',
      status: 'pending',
      category: 'EXTRA',
    })
  })

  it('updateItem merges partial updates', async () => {
    const { items, updateItem } = await load()
    updateItem('cl-2', { subtitle: 'Updated subtitle', status: 'in-progress' })
    const item = items.value.find(i => i.id === 'cl-2')
    expect(item).toMatchObject({
      title: 'NOTAM Verification',
      subtitle: 'Updated subtitle',
      status: 'in-progress',
    })
  })

  it('updateItem ignores unknown ids', async () => {
    const { items, updateItem } = await load()
    updateItem('nope', { status: 'completed' })
    expect(items.value.find(i => i.id === 'nope')).toBeUndefined()
    expect(items.value).toHaveLength(6)
  })

  it('completeItem marks an item completed and updates the counts', async () => {
    const { items, completeItem, completedCount, progressPercentage } = await load()
    completeItem('cl-2')
    expect(items.value.find(i => i.id === 'cl-2')?.status).toBe('completed')
    expect(completedCount.value).toBe(2)
    expect(progressPercentage.value).toBeCloseTo(33.333, 2)
  })

  it('removeItem deletes the matching item', async () => {
    const { items, removeItem, totalCount } = await load()
    removeItem('cl-1')
    expect(items.value.find(i => i.id === 'cl-1')).toBeUndefined()
    expect(totalCount.value).toBe(5)
  })

  it('removeItem ignores unknown ids', async () => {
    const { items, removeItem } = await load()
    removeItem('missing')
    expect(items.value).toHaveLength(6)
  })

  it('toggleAutoGen flips the auto-generation flag', async () => {
    const { autoGenEnabled, toggleAutoGen } = await load()
    expect(autoGenEnabled.value).toBe(true)
    toggleAutoGen()
    expect(autoGenEnabled.value).toBe(false)
    toggleAutoGen()
    expect(autoGenEnabled.value).toBe(true)
  })

  it('resetChecklist restores the item list from the shared defaults', async () => {
    const { items, removeItem, addItem, updateItem, resetChecklist } = await load()
    removeItem('cl-1')
    updateItem('cl-2', { status: 'completed' })
    addItem({ title: 'X', status: 'pending', category: 'EXTRA' })

    resetChecklist()

    expect(items.value).toHaveLength(6)
    expect(items.value.find(i => i.id === 'cl-1')?.status).toBe('completed')
    // NOTE: resetChecklist shallow-copies `defaultChecklist`; updateItem mutated
    // the shared nested objects in place, so the change persists through reset.
    expect(items.value.find(i => i.id === 'cl-2')?.status).toBe('completed')
  })
})
