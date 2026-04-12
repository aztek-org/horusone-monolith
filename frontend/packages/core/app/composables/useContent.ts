/**
 * Typed API client composable for knowledge-base content endpoints.
 * Provides methods to fetch categories, articles, and search content.
 *
 * All interfaces mirror the backend snake_case JSON responses exactly.
 */

export interface ContentCategory {
  id: string
  name: string
  slug: string
  description: string | null
  parent_id: string | null
  sort_order: number
  icon: string | null
  is_active: boolean
  created_at: string
  children: ContentCategory[]
}

export interface ContentArticle {
  id: string
  category_id: string
  title: string
  slug: string
  content: string
  summary: string | null
  difficulty_level: number
  tags: string[]
  author_id: string | null
  org_id: string | null
  is_published: boolean
  view_count: number
  created_at: string
  updated_at: string
}

interface ContentCategoryDetail extends ContentCategory {
  articles: ContentArticle[]
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
  ): Promise<ContentArticle[]> {
    const params = new URLSearchParams({
      q: query,
      limit: String(limit),
      offset: String(offset),
    })
    return api.get<ContentArticle[]>(
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
