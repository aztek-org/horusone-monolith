<script setup lang="ts">
import type {
  ContentCategory,
  ContentArticle,
  ContentSearchResult,
} from '~/composables/useContent'

definePageMeta({
  layout: false,
  middleware: 'auth',
})

const content = useContent()
const route = useRoute()
const router = useRouter()

// --- State ---

type ViewMode = 'categories' | 'category' | 'article' | 'search'

const viewMode = ref<ViewMode>('categories')
const categories = ref<ContentCategory[]>([])
const selectedCategory = ref<ContentCategory | null>(null)
const categoryArticles = ref<ContentArticle[]>([])
const selectedArticle = ref<ContentArticle | null>(null)
const searchResults = ref<ContentSearchResult[]>([])

const searchQuery = ref('')
const searchDebounce = ref<ReturnType<typeof setTimeout> | null>(null)

const isLoadingCategories = ref(true)
const isLoadingArticles = ref(true)
const isLoadingArticle = ref(false)
const isSearching = ref(false)

const errorMessage = ref<string | null>(null)

// --- Category icons mapping ---

const categoryIcons: Record<string, string> = {
  'aerodynamics': 'heroicons:paper-airplane',
  'navigation': 'heroicons:map',
  'weather': 'heroicons:cloud',
  'communications': 'heroicons:signal',
  'regulations': 'heroicons:document-text',
  'instruments': 'heroicons:adjustments-horizontal',
  'emergency': 'heroicons:exclamation-triangle',
  'performance': 'heroicons:chart-bar',
}

function getCategoryIcon(slug: string): string {
  return categoryIcons[slug] ?? 'heroicons:academic-cap'
}

// --- Data Fetching ---

async function fetchCategories() {
  isLoadingCategories.value = true
  try {
    categories.value = await content.getCategories()
  }
  catch (err) {
    const apiErr = err as { detail?: string }
    errorMessage.value = apiErr.detail ?? 'Failed to load categories'
  }
  finally {
    isLoadingCategories.value = false
  }
}

async function selectCategory(category: ContentCategory) {
  selectedCategory.value = category
  viewMode.value = 'category'
  selectedArticle.value = null
  isLoadingArticles.value = true

  try {
    const detail = await content.getCategoryBySlug(category.slug)
    categoryArticles.value = detail.articles
  }
  catch (err) {
    const apiErr = err as { detail?: string }
    errorMessage.value = apiErr.detail ?? 'Failed to load articles'
    categoryArticles.value = []
  }
  finally {
    isLoadingArticles.value = false
  }
}

async function selectArticle(slug: string) {
  isLoadingArticle.value = true
  viewMode.value = 'article'

  try {
    selectedArticle.value = await content.getArticleBySlug(slug)
  }
  catch (err) {
    const apiErr = err as { detail?: string }
    errorMessage.value = apiErr.detail ?? 'Failed to load article'
  }
  finally {
    isLoadingArticle.value = false
  }
}

function handleSearch() {
  if (searchDebounce.value) clearTimeout(searchDebounce.value)

  if (!searchQuery.value.trim()) {
    searchResults.value = []
    if (selectedCategory.value) {
      viewMode.value = 'category'
    }
    else {
      viewMode.value = 'categories'
    }
    return
  }

  searchDebounce.value = setTimeout(async () => {
    isSearching.value = true
    viewMode.value = 'search'

    try {
      const result = await content.searchArticles(searchQuery.value.trim())
      searchResults.value = result.items
    }
    catch (err) {
      const apiErr = err as { detail?: string }
      errorMessage.value = apiErr.detail ?? 'Search failed'
    }
    finally {
      isSearching.value = false
    }
  }, 300)
}

function navigateBack() {
  if (viewMode.value === 'article') {
    selectedArticle.value = null
    viewMode.value = selectedCategory.value ? 'category' : 'categories'
  }
  else if (viewMode.value === 'category') {
    selectedCategory.value = null
    categoryArticles.value = []
    viewMode.value = 'categories'
  }
  else if (viewMode.value === 'search') {
    searchQuery.value = ''
    searchResults.value = []
    viewMode.value = selectedCategory.value ? 'category' : 'categories'
  }
}

function getDifficultyVariant(d: string): 'active' | 'warning' | 'danger' {
  switch (d) {
    case 'advanced': return 'danger'
    case 'intermediate': return 'warning'
    default: return 'active'
  }
}

function getDifficultyLabel(d: string): string {
  switch (d) {
    case 'advanced': return 'Advanced'
    case 'intermediate': return 'Intermediate'
    default: return 'Beginner'
  }
}

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  })
}

/**
 * Minimal markdown→HTML for article body rendering.
 * Supports headings, bold, italic, inline code, code blocks, lists, links, and paragraphs.
 */
function renderMarkdown(md: string): string {
  let html = md
    // Code blocks (fenced)
    .replace(/```(\w*)\n([\s\S]*?)```/g, '<pre class="bg-horus-bg-secondary rounded-lg p-4 overflow-x-auto my-4 text-sm font-mono text-horus-text-secondary"><code>$2</code></pre>')
    // Headings
    .replace(/^### (.+)$/gm, '<h3 class="text-lg font-semibold text-horus-text-primary mt-6 mb-3">$1</h3>')
    .replace(/^## (.+)$/gm, '<h2 class="text-xl font-semibold text-horus-text-primary mt-8 mb-4">$1</h2>')
    .replace(/^# (.+)$/gm, '<h1 class="text-2xl font-bold text-horus-text-primary mt-8 mb-4">$1</h1>')
    // Bold & italic
    .replace(/\*\*(.+?)\*\*/g, '<strong class="font-semibold text-horus-text-primary">$1</strong>')
    .replace(/\*(.+?)\*/g, '<em>$1</em>')
    // Inline code
    .replace(/`([^`]+)`/g, '<code class="bg-horus-bg-secondary px-1.5 py-0.5 rounded text-sm font-mono text-horus-accent-cyan">$1</code>')
    // Unordered lists
    .replace(/^- (.+)$/gm, '<li class="ml-4 text-horus-text-secondary list-disc">$1</li>')
    // Ordered lists
    .replace(/^\d+\. (.+)$/gm, '<li class="ml-4 text-horus-text-secondary list-decimal">$1</li>')
    // Links
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" class="text-horus-accent-cyan hover:underline" target="_blank" rel="noopener">$1</a>')
    // Paragraphs (simple: wrap non-tag lines)
    .replace(/^(?!<[hluopra])((?!\s*$).+)$/gm, '<p class="text-sm text-horus-text-secondary leading-relaxed mb-3">$1</p>')

  return html
}

// --- Watchers ---

watch(searchQuery, handleSearch)

onMounted(() => {
  fetchCategories()
})
</script>

<template>
  <NuxtLayout name="default">
    <!-- Category Sidebar -->
    <template #sidebar>
      <div class="space-y-4">
        <div class="flex items-center gap-2">
          <Icon name="heroicons:academic-cap" class="w-5 h-5 text-horus-accent-cyan" />
          <h2 class="text-sm font-semibold text-horus-text-primary">CATEGORIES</h2>
        </div>

        <!-- Loading -->
        <div v-if="isLoadingCategories" class="flex items-center justify-center py-4">
          <Icon name="svg-spinners:ring-resize" class="w-5 h-5 text-horus-accent-cyan" />
        </div>

        <!-- Category List -->
        <div v-else class="space-y-1">
          <button
            v-for="cat in categories"
            :key="cat.id"
            :class="[
              'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-colors',
              selectedCategory?.id === cat.id
                ? 'bg-horus-accent-cyan/10 text-horus-accent-cyan border border-horus-accent-cyan/30'
                : 'text-horus-text-secondary hover:text-horus-text-primary hover:bg-horus-bg-tertiary border border-transparent'
            ]"
            @click="selectCategory(cat)"
          >
            <Icon
              :name="cat.icon ?? getCategoryIcon(cat.slug)"
              :class="[
                'w-4 h-4 flex-shrink-0',
                selectedCategory?.id === cat.id ? 'text-horus-accent-cyan' : 'text-horus-text-muted'
              ]"
            />
            <span class="text-sm flex-1 truncate">{{ cat.name }}</span>
            <span class="text-xxs font-mono text-horus-text-muted">
              {{ cat.articleCount }}
            </span>
          </button>
        </div>

        <!-- Browse All -->
        <div class="pt-3 border-t border-horus-border-subtle">
          <button
            :class="[
              'w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-colors',
              viewMode === 'categories' && !selectedCategory
                ? 'bg-horus-accent-cyan/10 text-horus-accent-cyan'
                : 'text-horus-text-secondary hover:text-horus-text-primary hover:bg-horus-bg-tertiary'
            ]"
            @click="navigateBack(); selectedCategory = null; viewMode = 'categories'"
          >
            <Icon name="heroicons:squares-2x2" class="w-4 h-4" />
            <span class="text-sm">All Categories</span>
          </button>
        </div>
      </div>
    </template>

    <!-- Main Content -->
    <template #default>
      <div class="p-4 lg:p-6 space-y-6">
        <!-- Header with Search -->
        <div class="space-y-4">
          <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <div>
              <h1 class="text-xl font-semibold text-horus-text-primary">
                Aviation Knowledge Base
              </h1>
              <p class="text-sm text-horus-text-secondary mt-1">
                Study materials, procedures, and reference guides
              </p>
            </div>
          </div>

          <!-- Search Bar -->
          <div class="relative">
            <Icon
              name="heroicons:magnifying-glass"
              class="absolute left-3 top-1/2 -translate-y-1/2 w-5 h-5 text-horus-text-muted"
            />
            <input
              v-model="searchQuery"
              type="text"
              placeholder="Search articles, topics, and procedures..."
              class="w-full bg-horus-bg-secondary border border-horus-border-subtle rounded-lg pl-10 pr-4 py-2.5 text-sm text-horus-text-primary placeholder:text-horus-text-muted focus:outline-none focus:border-horus-accent-cyan focus:ring-1 focus:ring-horus-accent-cyan/50 transition-colors"
            />
            <button
              v-if="searchQuery"
              class="absolute right-3 top-1/2 -translate-y-1/2"
              @click="searchQuery = ''"
            >
              <Icon name="heroicons:x-mark" class="w-4 h-4 text-horus-text-muted hover:text-horus-text-primary" />
            </button>
          </div>
        </div>

        <!-- Error Banner -->
        <div
          v-if="errorMessage"
          class="flex items-center gap-3 p-3 rounded-lg bg-horus-status-danger/10 border border-horus-status-danger/30"
        >
          <Icon name="heroicons:exclamation-triangle" class="w-5 h-5 text-horus-status-danger flex-shrink-0" />
          <span class="text-sm text-horus-status-danger">{{ errorMessage }}</span>
          <button
            class="ml-auto text-horus-status-danger hover:text-horus-text-primary"
            @click="errorMessage = null"
          >
            <Icon name="heroicons:x-mark" class="w-4 h-4" />
          </button>
        </div>

        <!-- Breadcrumbs -->
        <nav
          v-if="viewMode !== 'categories' && viewMode !== 'search'"
          class="flex items-center gap-2 text-sm"
        >
          <button
            class="text-horus-text-muted hover:text-horus-accent-cyan transition-colors"
            @click="selectedCategory = null; selectedArticle = null; viewMode = 'categories'"
          >
            Knowledge
          </button>
          <Icon name="heroicons:chevron-right" class="w-3 h-3 text-horus-text-muted" />

          <button
            v-if="selectedCategory"
            :class="[
              viewMode === 'article'
                ? 'text-horus-text-muted hover:text-horus-accent-cyan transition-colors'
                : 'text-horus-text-primary'
            ]"
            @click="viewMode === 'article' ? navigateBack() : undefined"
          >
            {{ selectedCategory.name }}
          </button>

          <template v-if="selectedArticle && viewMode === 'article'">
            <Icon name="heroicons:chevron-right" class="w-3 h-3 text-horus-text-muted" />
            <span class="text-horus-text-primary truncate">{{ selectedArticle.title }}</span>
          </template>
        </nav>

        <!-- ===== SEARCH RESULTS VIEW ===== -->
        <template v-if="viewMode === 'search'">
          <div v-if="isSearching" class="flex items-center justify-center py-16">
            <div class="text-center space-y-3">
              <Icon name="svg-spinners:ring-resize" class="w-8 h-8 text-horus-accent-cyan mx-auto" />
              <p class="text-sm text-horus-text-muted">Searching...</p>
            </div>
          </div>

          <div v-else-if="searchResults.length === 0" class="text-center py-16">
            <Icon name="heroicons:magnifying-glass" class="w-12 h-12 text-horus-text-muted mx-auto mb-4 opacity-50" />
            <p class="text-sm text-horus-text-secondary">No results found for "{{ searchQuery }}"</p>
            <p class="text-xs text-horus-text-muted mt-1">Try adjusting your search terms</p>
          </div>

          <div v-else class="space-y-3">
            <p class="text-xs text-horus-text-muted">
              {{ searchResults.length }} result{{ searchResults.length === 1 ? '' : 's' }} for "{{ searchQuery }}"
            </p>
            <div class="space-y-3">
              <HCard
                v-for="result in searchResults"
                :key="result.id"
                variant="default"
                padding="md"
                hover
                class="cursor-pointer"
                @click="selectArticle(result.slug)"
              >
                <div class="space-y-2">
                  <div class="flex items-start justify-between gap-2">
                    <h3 class="text-sm font-semibold text-horus-text-primary">
                      {{ result.title }}
                    </h3>
                    <HBadge :variant="getDifficultyVariant(result.difficulty)" size="sm" class="flex-shrink-0">
                      {{ getDifficultyLabel(result.difficulty) }}
                    </HBadge>
                  </div>
                  <p class="text-xs text-horus-text-secondary line-clamp-2">
                    {{ result.snippet || result.summary }}
                  </p>
                  <div class="flex items-center gap-3 text-xxs text-horus-text-muted">
                    <span class="flex items-center gap-1">
                      <Icon name="heroicons:folder" class="w-3 h-3" />
                      {{ result.categoryName }}
                    </span>
                    <span v-if="result.viewCount > 0" class="flex items-center gap-1">
                      <Icon name="heroicons:eye" class="w-3 h-3" />
                      {{ result.viewCount }}
                    </span>
                  </div>
                </div>
              </HCard>
            </div>
          </div>
        </template>

        <!-- ===== CATEGORIES OVERVIEW ===== -->
        <template v-else-if="viewMode === 'categories'">
          <div v-if="isLoadingCategories" class="flex items-center justify-center py-16">
            <div class="text-center space-y-3">
              <Icon name="svg-spinners:ring-resize" class="w-8 h-8 text-horus-accent-cyan mx-auto" />
              <p class="text-sm text-horus-text-muted">Loading categories...</p>
            </div>
          </div>

          <div v-else-if="categories.length === 0" class="text-center py-16">
            <Icon name="heroicons:academic-cap" class="w-12 h-12 text-horus-text-muted mx-auto mb-4 opacity-50" />
            <p class="text-sm text-horus-text-secondary">No knowledge base content available yet</p>
          </div>

          <div v-else class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <HCard
              v-for="cat in categories"
              :key="cat.id"
              variant="default"
              padding="lg"
              hover
              class="cursor-pointer"
              @click="selectCategory(cat)"
            >
              <div class="space-y-3">
                <div class="w-12 h-12 rounded-xl bg-horus-accent-cyan/10 flex items-center justify-center">
                  <Icon
                    :name="cat.icon ?? getCategoryIcon(cat.slug)"
                    class="w-6 h-6 text-horus-accent-cyan"
                  />
                </div>
                <div>
                  <h3 class="text-sm font-semibold text-horus-text-primary">
                    {{ cat.name }}
                  </h3>
                  <p v-if="cat.description" class="text-xs text-horus-text-secondary mt-1 line-clamp-2">
                    {{ cat.description }}
                  </p>
                </div>
                <div class="flex items-center gap-1 text-xxs text-horus-text-muted">
                  <Icon name="heroicons:document-text" class="w-3 h-3" />
                  {{ cat.articleCount }} article{{ cat.articleCount === 1 ? '' : 's' }}
                </div>
              </div>
            </HCard>
          </div>
        </template>

        <!-- ===== CATEGORY ARTICLES LIST ===== -->
        <template v-else-if="viewMode === 'category'">
          <div class="flex items-center justify-between mb-4">
            <div class="flex items-center gap-3">
              <button
                class="p-1.5 rounded-lg hover:bg-horus-bg-tertiary transition-colors"
                @click="navigateBack"
              >
                <Icon name="heroicons:arrow-left" class="w-5 h-5 text-horus-text-secondary" />
              </button>
              <div>
                <h2 class="text-lg font-semibold text-horus-text-primary">
                  {{ selectedCategory?.name }}
                </h2>
                <p v-if="selectedCategory?.description" class="text-xs text-horus-text-secondary mt-0.5">
                  {{ selectedCategory.description }}
                </p>
              </div>
            </div>
          </div>

          <div v-if="isLoadingArticles" class="flex items-center justify-center py-16">
            <div class="text-center space-y-3">
              <Icon name="svg-spinners:ring-resize" class="w-8 h-8 text-horus-accent-cyan mx-auto" />
              <p class="text-sm text-horus-text-muted">Loading articles...</p>
            </div>
          </div>

          <div v-else-if="categoryArticles.length === 0" class="text-center py-16">
            <Icon name="heroicons:document-text" class="w-12 h-12 text-horus-text-muted mx-auto mb-4 opacity-50" />
            <p class="text-sm text-horus-text-secondary">No articles in this category yet</p>
          </div>

          <div v-else class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            <HArticleCard
              v-for="article in categoryArticles"
              :key="article.id"
              :title="article.title"
              :summary="article.summary"
              :category="article.categoryName"
              :difficulty="article.difficulty"
              :tags="article.tags"
              :view-count="article.viewCount"
              :slug="article.slug"
              @navigate="selectArticle"
            />
          </div>
        </template>

        <!-- ===== ARTICLE VIEW ===== -->
        <template v-else-if="viewMode === 'article'">
          <div v-if="isLoadingArticle" class="flex items-center justify-center py-16">
            <div class="text-center space-y-3">
              <Icon name="svg-spinners:ring-resize" class="w-8 h-8 text-horus-accent-cyan mx-auto" />
              <p class="text-sm text-horus-text-muted">Loading article...</p>
            </div>
          </div>

          <template v-else-if="selectedArticle">
            <!-- Back Button -->
            <button
              class="flex items-center gap-2 text-sm text-horus-text-secondary hover:text-horus-accent-cyan transition-colors mb-4"
              @click="navigateBack"
            >
              <Icon name="heroicons:arrow-left" class="w-4 h-4" />
              Back to articles
            </button>

            <!-- Article Header -->
            <HCard variant="elevated" padding="lg">
              <div class="space-y-4">
                <div class="flex flex-wrap items-center gap-2">
                  <HBadge :variant="getDifficultyVariant(selectedArticle.difficulty)" size="sm">
                    {{ getDifficultyLabel(selectedArticle.difficulty) }}
                  </HBadge>
                  <HBadge variant="info" size="sm">
                    {{ selectedArticle.categoryName }}
                  </HBadge>
                </div>

                <h1 class="text-2xl font-bold text-horus-text-primary">
                  {{ selectedArticle.title }}
                </h1>

                <p class="text-sm text-horus-text-secondary">
                  {{ selectedArticle.summary }}
                </p>

                <div class="flex items-center gap-4 text-xxs text-horus-text-muted border-t border-horus-border-subtle pt-4">
                  <span v-if="selectedArticle.author" class="flex items-center gap-1">
                    <Icon name="heroicons:user" class="w-3 h-3" />
                    {{ selectedArticle.author }}
                  </span>
                  <span class="flex items-center gap-1">
                    <Icon name="heroicons:calendar" class="w-3 h-3" />
                    {{ formatDate(selectedArticle.updatedAt) }}
                  </span>
                  <span class="flex items-center gap-1">
                    <Icon name="heroicons:eye" class="w-3 h-3" />
                    {{ selectedArticle.viewCount }} views
                  </span>
                </div>

                <!-- Tags -->
                <div v-if="selectedArticle.tags.length > 0" class="flex flex-wrap gap-1.5">
                  <span
                    v-for="tag in selectedArticle.tags"
                    :key="tag"
                    class="inline-flex items-center px-2 py-0.5 rounded text-xxs bg-horus-bg-tertiary text-horus-text-muted border border-horus-border-subtle"
                  >
                    {{ tag }}
                  </span>
                </div>
              </div>
            </HCard>

            <!-- Article Body -->
            <HCard variant="default" padding="lg" class="mt-4">
              <!-- eslint-disable-next-line vue/no-v-html -->
              <div class="prose-horus space-y-1" v-html="renderMarkdown(selectedArticle.body)" />
            </HCard>
          </template>
        </template>
      </div>
    </template>

    <!-- Right Panel -->
    <template #panel>
      <div class="space-y-6">
        <!-- Quick Stats -->
        <div class="space-y-3">
          <div class="flex items-center gap-2">
            <Icon name="heroicons:book-open" class="w-5 h-5 text-horus-accent-cyan" />
            <h2 class="text-sm font-semibold text-horus-text-primary">LIBRARY STATS</h2>
          </div>

          <div class="space-y-3">
            <HDataPanel
              :value="String(categories.length)"
              label="Categories"
              variant="compact"
            />
            <HDataPanel
              :value="String(categories.reduce((sum, c) => sum + c.articleCount, 0))"
              label="Total Articles"
              variant="compact"
            />
          </div>
        </div>

        <!-- Article Info (when viewing article) -->
        <div v-if="selectedArticle && viewMode === 'article'" class="space-y-3">
          <div class="flex items-center gap-2">
            <Icon name="heroicons:information-circle" class="w-5 h-5 text-horus-accent-cyan" />
            <h2 class="text-sm font-semibold text-horus-text-primary">ARTICLE INFO</h2>
          </div>

          <HCard variant="glass" padding="md">
            <div class="space-y-3 text-sm">
              <div>
                <p class="text-xxs text-horus-text-muted uppercase tracking-wider">Difficulty</p>
                <HBadge :variant="getDifficultyVariant(selectedArticle.difficulty)" size="sm" class="mt-1">
                  {{ getDifficultyLabel(selectedArticle.difficulty) }}
                </HBadge>
              </div>
              <div>
                <p class="text-xxs text-horus-text-muted uppercase tracking-wider">Last Updated</p>
                <p class="text-horus-text-secondary mt-0.5">{{ formatDate(selectedArticle.updatedAt) }}</p>
              </div>
              <div>
                <p class="text-xxs text-horus-text-muted uppercase tracking-wider">Views</p>
                <p class="text-horus-text-secondary mt-0.5 font-mono">{{ selectedArticle.viewCount }}</p>
              </div>
            </div>
          </HCard>
        </div>

        <!-- Quick Navigation -->
        <div class="space-y-3">
          <div class="flex items-center gap-2">
            <Icon name="heroicons:bolt" class="w-5 h-5 text-horus-accent-cyan" />
            <h2 class="text-sm font-semibold text-horus-text-primary">QUICK LINKS</h2>
          </div>

          <div class="space-y-2">
            <HButton
              variant="secondary"
              size="sm"
              icon="heroicons:academic-cap"
              class="w-full justify-start"
              @click="router.push('/assessments')"
            >
              Take Assessment
            </HButton>
            <HButton
              variant="secondary"
              size="sm"
              icon="heroicons:chart-bar"
              class="w-full justify-start"
              @click="router.push('/stats')"
            >
              View Stats
            </HButton>
            <HButton
              variant="secondary"
              size="sm"
              icon="heroicons:play"
              class="w-full justify-start"
              @click="router.push('/configurator')"
            >
              Start Simulation
            </HButton>
          </div>
        </div>
      </div>
    </template>
  </NuxtLayout>
</template>
