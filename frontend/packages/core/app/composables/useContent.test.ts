import { describe, it, expect, vi, beforeEach } from 'vitest'

const mockApi = {
  get: vi.fn(),
}

vi.mock('./useApi', () => ({
  useApi: () => mockApi,
}))

async function setup() {
  const { useContent } = await import('./useContent')
  return useContent()
}

describe('useContent', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockApi.get.mockResolvedValue([])
  })

  it('getCategories GETs the flat categories collection', async () => {
    const content = await setup()
    await content.getCategories()
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/content/categories')
  })

  it('getCategoryBySlug GETs the category detail endpoint', async () => {
    const content = await setup()
    await content.getCategoryBySlug('weather-basics')
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/content/categories/weather-basics')
  })

  it('getArticleBySlug GETs the article endpoint', async () => {
    const content = await setup()
    await content.getArticleBySlug('metar-decoded')
    expect(mockApi.get).toHaveBeenCalledWith('/api/v1/content/articles/metar-decoded')
  })

  it('searchArticles builds encoded query params with defaults', async () => {
    const content = await setup()
    await content.searchArticles('icing conditions')
    expect(mockApi.get).toHaveBeenCalledWith(
      '/api/v1/content/search?q=icing+conditions&limit=20&offset=0',
    )
  })

  it('searchArticles passes through custom limit and offset', async () => {
    const content = await setup()
    await content.searchArticles('icing', 5, 10)
    expect(mockApi.get).toHaveBeenCalledWith(
      '/api/v1/content/search?q=icing&limit=5&offset=10',
    )
  })
})
