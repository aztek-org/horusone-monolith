<script setup lang="ts">
import type { TrainingModule, ModuleCreatePayload, ModuleUpdatePayload } from '~/composables/useAdmin'

definePageMeta({
  layout: 'admin',
  middleware: ['auth', 'admin'],
})

const admin = useAdmin()

const modules = ref<TrainingModule[]>([])
const isLoading = ref(true)
const error = ref<string | null>(null)

// Create module
const showCreateForm = ref(false)
const createForm = ref<ModuleCreatePayload>({
  name: '',
  description: '',
  difficulty_level: 'beginner',
  is_published: false,
  org_id: null,
  sort_order: 0,
})
const isCreating = ref(false)
const createError = ref<string | null>(null)

// Edit module
const editingModuleId = ref<string | null>(null)
const editForm = ref<ModuleUpdatePayload>({})
const isSaving = ref(false)

// Scenario linking
const linkingModuleId = ref<string | null>(null)
const linkScenarioId = ref('')
const linkSortOrder = ref(0)
const isLinking = ref(false)

const difficultyOptions = [
  { value: 'beginner', label: 'Beginner' },
  { value: 'intermediate', label: 'Intermediate' },
  { value: 'advanced', label: 'Advanced' },
  { value: 'expert', label: 'Expert' },
]

const difficultyColors: Record<string, string> = {
  beginner: 'success',
  intermediate: 'info',
  advanced: 'warning',
  expert: 'danger',
}

async function loadModules() {
  isLoading.value = true
  error.value = null
  try {
    modules.value = await admin.fetchModules()
  }
  catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load modules'
  }
  finally {
    isLoading.value = false
  }
}

async function handleCreate() {
  isCreating.value = true
  createError.value = null
  try {
    const newModule = await admin.createModule(createForm.value)
    modules.value.push(newModule)
    showCreateForm.value = false
    createForm.value = {
      name: '',
      description: '',
      difficulty_level: 'beginner',
      is_published: false,
      org_id: null,
      sort_order: 0,
    }
  }
  catch (e) {
    createError.value = e instanceof Error ? e.message : 'Failed to create module'
  }
  finally {
    isCreating.value = false
  }
}

function startEditing(mod: TrainingModule) {
  editingModuleId.value = mod.id
  editForm.value = {
    name: mod.name,
    description: mod.description,
    difficulty_level: mod.difficulty_level,
    is_published: mod.is_published,
    sort_order: mod.sort_order,
  }
}

function cancelEditing() {
  editingModuleId.value = null
}

async function saveModule(moduleId: string) {
  isSaving.value = true
  try {
    const updated = await admin.updateModule(moduleId, editForm.value)
    const idx = modules.value.findIndex(m => m.id === moduleId)
    if (idx !== -1) modules.value[idx] = { ...modules.value[idx], ...updated }
    editingModuleId.value = null
  }
  catch {
    // Silent fail
  }
  finally {
    isSaving.value = false
  }
}

async function deleteModule(moduleId: string) {
  try {
    await admin.deleteModule(moduleId)
    modules.value = modules.value.filter(m => m.id !== moduleId)
  }
  catch {
    // Silent fail
  }
}

async function togglePublished(mod: TrainingModule) {
  try {
    const updated = await admin.updateModule(mod.id, { is_published: !mod.is_published })
    const idx = modules.value.findIndex(m => m.id === mod.id)
    if (idx !== -1) modules.value[idx] = { ...modules.value[idx], ...updated }
  }
  catch {
    // Silent fail
  }
}

function startLinking(moduleId: string) {
  linkingModuleId.value = moduleId
  linkScenarioId.value = ''
  linkSortOrder.value = 0
}

async function handleLinkScenario() {
  if (!linkingModuleId.value || !linkScenarioId.value) return
  isLinking.value = true
  try {
    await admin.linkScenario(linkingModuleId.value, linkScenarioId.value, linkSortOrder.value)
    // Reload module to see updated scenarios
    const updated = await admin.fetchModule(linkingModuleId.value)
    const idx = modules.value.findIndex(m => m.id === linkingModuleId.value)
    if (idx !== -1) modules.value[idx] = updated
    linkingModuleId.value = null
  }
  catch {
    // Silent fail
  }
  finally {
    isLinking.value = false
  }
}

async function handleUnlinkScenario(moduleId: string, scenarioId: string) {
  try {
    await admin.unlinkScenario(moduleId, scenarioId)
    // Update local state
    const idx = modules.value.findIndex(m => m.id === moduleId)
    if (idx !== -1 && modules.value[idx].scenarios) {
      modules.value[idx] = {
        ...modules.value[idx],
        scenarios: modules.value[idx].scenarios!.filter(s => s.scenario_id !== scenarioId),
      }
    }
  }
  catch {
    // Silent fail
  }
}

onMounted(loadModules)
</script>

<template>
  <div class="space-y-6 max-w-6xl mx-auto">
    <!-- Page Header -->
    <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
      <div>
        <h1 class="text-2xl font-bold text-horus-text-primary">Modules</h1>
        <p class="text-sm text-horus-text-secondary mt-1">
          Manage training modules and link scenarios
        </p>
      </div>
      <HButton
        variant="primary"
        size="sm"
        icon="heroicons:plus"
        @click="showCreateForm = !showCreateForm"
      >
        New Module
      </HButton>
    </div>

    <!-- Create Module Form -->
    <Transition
      enter-active-class="transition-all duration-200"
      enter-from-class="opacity-0 -translate-y-2"
      enter-to-class="opacity-100 translate-y-0"
      leave-active-class="transition-all duration-150"
      leave-from-class="opacity-100 translate-y-0"
      leave-to-class="opacity-0 -translate-y-2"
    >
      <HCard v-if="showCreateForm" variant="elevated" padding="lg">
        <form class="space-y-4" @submit.prevent="handleCreate">
          <h3 class="text-sm font-semibold text-horus-text-primary">Create New Module</h3>

          <div v-if="createError" class="flex items-center gap-2 p-3 rounded-lg bg-horus-status-danger/10 border border-horus-status-danger/20">
            <Icon name="heroicons:exclamation-circle" class="w-4 h-4 text-horus-status-danger flex-shrink-0" />
            <p class="text-sm text-horus-status-danger">{{ createError }}</p>
          </div>

          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div class="space-y-1.5">
              <label class="block text-xs font-medium text-horus-text-secondary uppercase tracking-wider">Name</label>
              <input
                v-model="createForm.name"
                type="text"
                required
                placeholder="e.g. Basic ATC Communication"
                class="w-full bg-horus-bg-secondary border border-horus-border-subtle rounded-lg px-3 py-2.5 text-sm text-horus-text-primary placeholder:text-horus-text-muted focus:outline-none focus:border-horus-accent-cyan focus:ring-1 focus:ring-horus-accent-cyan/50"
              />
            </div>
            <HDropdown
              v-model="createForm.difficulty_level"
              :options="difficultyOptions"
              label="Difficulty"
            />
          </div>

          <div class="space-y-1.5">
            <label class="block text-xs font-medium text-horus-text-secondary uppercase tracking-wider">Description</label>
            <textarea
              v-model="createForm.description"
              rows="3"
              placeholder="Module description..."
              class="w-full bg-horus-bg-secondary border border-horus-border-subtle rounded-lg px-3 py-2.5 text-sm text-horus-text-primary placeholder:text-horus-text-muted focus:outline-none focus:border-horus-accent-cyan focus:ring-1 focus:ring-horus-accent-cyan/50 resize-none"
            />
          </div>

          <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div class="space-y-1.5">
              <label class="block text-xs font-medium text-horus-text-secondary uppercase tracking-wider">Sort Order</label>
              <input
                v-model.number="createForm.sort_order"
                type="number"
                min="0"
                class="w-full bg-horus-bg-secondary border border-horus-border-subtle rounded-lg px-3 py-2.5 text-sm text-horus-text-primary focus:outline-none focus:border-horus-accent-cyan focus:ring-1 focus:ring-horus-accent-cyan/50"
              />
            </div>
            <div class="space-y-1.5">
              <label class="block text-xs font-medium text-horus-text-secondary uppercase tracking-wider">Published</label>
              <div class="flex items-center h-[42px]">
                <HCheckbox
                  :model-value="createForm.is_published"
                  label="Published"
                  @update:model-value="createForm.is_published = $event"
                />
              </div>
            </div>
          </div>

          <div class="flex justify-end gap-3 pt-2">
            <HButton variant="ghost" size="sm" type="button" @click="showCreateForm = false">
              Cancel
            </HButton>
            <HButton variant="primary" size="sm" type="submit" :loading="isCreating" icon="heroicons:plus">
              Create Module
            </HButton>
          </div>
        </form>
      </HCard>
    </Transition>

    <!-- Error -->
    <HCard v-if="error" variant="elevated" padding="lg">
      <div class="flex items-center gap-3 text-horus-status-danger">
        <Icon name="heroicons:exclamation-triangle" class="w-6 h-6 flex-shrink-0" />
        <div class="flex-1">
          <p class="font-medium">{{ error }}</p>
        </div>
        <HButton variant="secondary" size="sm" icon="heroicons:arrow-path" @click="loadModules">
          Retry
        </HButton>
      </div>
    </HCard>

    <!-- Loading -->
    <div v-else-if="isLoading" class="space-y-4">
      <HCard v-for="n in 3" :key="n" variant="elevated" padding="md">
        <div class="animate-pulse space-y-3">
          <div class="h-5 w-48 rounded bg-horus-bg-tertiary" />
          <div class="h-3 w-full rounded bg-horus-bg-tertiary" />
          <div class="flex gap-2">
            <div class="h-5 w-20 rounded bg-horus-bg-tertiary" />
            <div class="h-5 w-16 rounded bg-horus-bg-tertiary" />
          </div>
        </div>
      </HCard>
    </div>

    <!-- Empty State -->
    <HCard v-else-if="modules.length === 0" variant="elevated" padding="lg">
      <div class="py-8 text-center">
        <Icon name="heroicons:academic-cap" class="w-12 h-12 text-horus-text-muted mx-auto mb-3" />
        <p class="text-horus-text-secondary font-medium">No modules yet</p>
        <p class="text-sm text-horus-text-muted mt-1">Create your first training module to get started</p>
      </div>
    </HCard>

    <!-- Module List -->
    <div v-else class="space-y-4">
      <HCard
        v-for="mod in modules"
        :key="mod.id"
        variant="elevated"
        padding="md"
      >
        <!-- View Mode -->
        <template v-if="editingModuleId !== mod.id">
          <div class="flex flex-col sm:flex-row sm:items-start gap-4">
            <div class="flex-1 min-w-0">
              <div class="flex items-center gap-2 flex-wrap">
                <h3 class="text-base font-semibold text-horus-text-primary">{{ mod.name }}</h3>
                <HBadge :variant="(difficultyColors[mod.difficulty_level] ?? 'default') as 'success' | 'info' | 'warning' | 'danger' | 'default'" size="sm">
                  {{ mod.difficulty_level }}
                </HBadge>
                <HBadge :variant="mod.is_published ? 'success' : 'idle'" size="sm">
                  {{ mod.is_published ? 'Published' : 'Draft' }}
                </HBadge>
              </div>
              <p v-if="mod.description" class="text-sm text-horus-text-secondary mt-1.5 line-clamp-2">
                {{ mod.description }}
              </p>
              <div class="flex items-center gap-4 mt-2 text-xs text-horus-text-muted">
                <span class="flex items-center gap-1">
                  <Icon name="heroicons:list-bullet" class="w-3.5 h-3.5" />
                  Order: {{ mod.sort_order }}
                </span>
                <span v-if="mod.scenario_count !== undefined" class="flex items-center gap-1">
                  <Icon name="heroicons:map" class="w-3.5 h-3.5" />
                  {{ mod.scenario_count }} scenarios
                </span>
                <span v-if="mod.org_id" class="flex items-center gap-1">
                  <Icon name="heroicons:building-office-2" class="w-3.5 h-3.5" />
                  Org-scoped
                </span>
              </div>
            </div>

            <div class="flex items-center gap-1 flex-shrink-0">
              <button
                class="p-1.5 rounded-md text-horus-text-muted hover:text-horus-accent-cyan hover:bg-horus-accent-cyan/10 transition-colors"
                title="Link scenario"
                @click="startLinking(mod.id)"
              >
                <Icon name="heroicons:link" class="w-4 h-4" />
              </button>
              <button
                class="p-1.5 rounded-md text-horus-text-muted hover:text-horus-text-primary hover:bg-horus-bg-tertiary transition-colors"
                :title="mod.is_published ? 'Unpublish' : 'Publish'"
                @click="togglePublished(mod)"
              >
                <Icon :name="mod.is_published ? 'heroicons:eye-slash' : 'heroicons:eye'" class="w-4 h-4" />
              </button>
              <button
                class="p-1.5 rounded-md text-horus-text-muted hover:text-horus-text-primary hover:bg-horus-bg-tertiary transition-colors"
                title="Edit"
                @click="startEditing(mod)"
              >
                <Icon name="heroicons:pencil" class="w-4 h-4" />
              </button>
              <button
                class="p-1.5 rounded-md text-horus-text-muted hover:text-horus-status-danger hover:bg-horus-status-danger/10 transition-colors"
                title="Delete"
                @click="deleteModule(mod.id)"
              >
                <Icon name="heroicons:trash" class="w-4 h-4" />
              </button>
            </div>
          </div>

          <!-- Link Scenario Form -->
          <div v-if="linkingModuleId === mod.id" class="mt-4 pt-4 border-t border-horus-border-subtle">
            <form class="flex items-end gap-3" @submit.prevent="handleLinkScenario">
              <div class="flex-1 space-y-1.5">
                <label class="block text-xs font-medium text-horus-text-secondary uppercase tracking-wider">Scenario ID</label>
                <input
                  v-model="linkScenarioId"
                  type="text"
                  required
                  placeholder="Enter scenario UUID"
                  class="w-full bg-horus-bg-secondary border border-horus-border-subtle rounded-lg px-3 py-2 text-sm text-horus-text-primary placeholder:text-horus-text-muted focus:outline-none focus:border-horus-accent-cyan focus:ring-1 focus:ring-horus-accent-cyan/50 font-mono"
                />
              </div>
              <div class="w-24 space-y-1.5">
                <label class="block text-xs font-medium text-horus-text-secondary uppercase tracking-wider">Order</label>
                <input
                  v-model.number="linkSortOrder"
                  type="number"
                  min="0"
                  class="w-full bg-horus-bg-secondary border border-horus-border-subtle rounded-lg px-3 py-2 text-sm text-horus-text-primary focus:outline-none focus:border-horus-accent-cyan focus:ring-1 focus:ring-horus-accent-cyan/50"
                />
              </div>
              <HButton variant="primary" size="sm" type="submit" :loading="isLinking" icon="heroicons:link">
                Link
              </HButton>
              <HButton variant="ghost" size="sm" type="button" @click="linkingModuleId = null">
                Cancel
              </HButton>
            </form>
          </div>

          <!-- Linked Scenarios -->
          <div v-if="mod.scenarios && mod.scenarios.length > 0" class="mt-4 pt-4 border-t border-horus-border-subtle">
            <p class="text-xs font-semibold text-horus-text-secondary uppercase tracking-wider mb-2">
              Linked Scenarios
            </p>
            <div class="flex flex-wrap gap-2">
              <div
                v-for="scenario in mod.scenarios"
                :key="scenario.scenario_id"
                class="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-horus-bg-secondary border border-horus-border-subtle text-xs"
              >
                <Icon name="heroicons:map" class="w-3.5 h-3.5 text-horus-text-muted" />
                <span class="text-horus-text-primary">{{ scenario.name }}</span>
                <button
                  class="text-horus-text-muted hover:text-horus-status-danger transition-colors"
                  @click="handleUnlinkScenario(mod.id, scenario.scenario_id)"
                >
                  <Icon name="heroicons:x-mark" class="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          </div>
        </template>

        <!-- Edit Mode -->
        <template v-else>
          <form class="space-y-4" @submit.prevent="saveModule(mod.id)">
            <h3 class="text-sm font-semibold text-horus-text-primary">Edit Module</h3>

            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div class="space-y-1.5">
                <label class="block text-xs font-medium text-horus-text-secondary uppercase tracking-wider">Name</label>
                <input
                  v-model="editForm.name"
                  type="text"
                  class="w-full bg-horus-bg-secondary border border-horus-border-subtle rounded-lg px-3 py-2.5 text-sm text-horus-text-primary focus:outline-none focus:border-horus-accent-cyan focus:ring-1 focus:ring-horus-accent-cyan/50"
                />
              </div>
              <HDropdown
                v-model="editForm.difficulty_level!"
                :options="difficultyOptions"
                label="Difficulty"
              />
            </div>

            <div class="space-y-1.5">
              <label class="block text-xs font-medium text-horus-text-secondary uppercase tracking-wider">Description</label>
              <textarea
                v-model="editForm.description"
                rows="2"
                class="w-full bg-horus-bg-secondary border border-horus-border-subtle rounded-lg px-3 py-2.5 text-sm text-horus-text-primary focus:outline-none focus:border-horus-accent-cyan focus:ring-1 focus:ring-horus-accent-cyan/50 resize-none"
              />
            </div>

            <div class="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div class="space-y-1.5">
                <label class="block text-xs font-medium text-horus-text-secondary uppercase tracking-wider">Sort Order</label>
                <input
                  v-model.number="editForm.sort_order"
                  type="number"
                  min="0"
                  class="w-full bg-horus-bg-secondary border border-horus-border-subtle rounded-lg px-3 py-2.5 text-sm text-horus-text-primary focus:outline-none focus:border-horus-accent-cyan focus:ring-1 focus:ring-horus-accent-cyan/50"
                />
              </div>
              <div class="space-y-1.5">
                <label class="block text-xs font-medium text-horus-text-secondary uppercase tracking-wider">Published</label>
                <div class="flex items-center h-[42px]">
                  <HCheckbox
                    :model-value="editForm.is_published ?? false"
                    label="Published"
                    @update:model-value="editForm.is_published = $event"
                  />
                </div>
              </div>
            </div>

            <div class="flex justify-end gap-3 pt-2">
              <HButton variant="ghost" size="sm" type="button" @click="cancelEditing">
                Cancel
              </HButton>
              <HButton variant="primary" size="sm" type="submit" :loading="isSaving" icon="heroicons:check">
                Save
              </HButton>
            </div>
          </form>
        </template>
      </HCard>
    </div>
  </div>
</template>
