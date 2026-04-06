/**
 * Typed API client composable for knowledge-base content endpoints.
 * Provides methods to fetch categories, articles, and search content.
 */

export interface ContentCategory {
  id: number
  name: string
  slug: string
  description: string | null
  icon: string | null
  articleCount: number
  sortOrder: number
}

export interface ContentArticle {
  id: number
  title: string
  slug: string
  summary: string
  body: string
  categoryId: number
  categoryName: string
  categorySlug: string
  difficulty: 'beginner' | 'intermediate' | 'advanced'
  tags: string[]
  author: string | null
  viewCount: number
  createdAt: string
  updatedAt: string
}

export interface ContentSearchResult {
  id: number
  title: string
  slug: string
  summary: string
  snippet: string
  categoryName: string
  categorySlug: string
  difficulty: 'beginner' | 'intermediate' | 'advanced'
  viewCount: number
  score: number
}

interface ContentCategoryDetail extends ContentCategory {
  articles: ContentArticle[]
}

interface PaginatedSearch {
  items: ContentSearchResult[]
  total: number
  hasMore: boolean
}

export function useContent() {
  const api = useApi()

  async function getCategories(): Promise<ContentCategory[]> {
    return api.get<ContentCategory[]>('/api/v1/content/categories')
  }

  async function getCategoryBySlug(slug: string): Promise<ContentCategoryDetail> {
    return api.get<ContentCategoryDetail>(`/api/v1/content/categories/${slug}`)
  }

  async function getArticleBySlug(slug: string): Promise<ContentArticle> {
    return api.get<ContentArticle>(`/api/v1/content/articles/${slug}`)
  }

  async function searchArticles(
    query: string,
    limit = 20,
    offset = 0,
  ): Promise<PaginatedSearch> {
    const params = new URLSearchParams({
      q: query,
      limit: String(limit),
      offset: String(offset),
    })
    return api.get<PaginatedSearch>(
      `/api/v1/content/search?${params.toString()}`,
    )
  }

  return {
    getCategories,
    getCategoryBySlug,
    getArticleBySlug,
    searchArticles,
  }
}
