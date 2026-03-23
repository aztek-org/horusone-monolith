<script setup lang="ts">
import type { InstructorProfile, InstructorProfileUpdate, AvailabilitySlot } from '~/composables/useInstructor'

definePageMeta({
  layout: false,
  middleware: ['auth', 'instructor'],
})

const { user } = useAuth()
const instructor = useInstructor()

const profile = ref<InstructorProfile | null>(null)
const isLoading = ref(true)
const isSaving = ref(false)
const error = ref<string | null>(null)
const saveSuccess = ref(false)

// Editable form state
const bio = ref('')
const qualifications = ref<string[]>([])
const certifications = ref<string[]>([])
const specializations = ref<string[]>([])
const availability = ref<AvailabilitySlot[]>([])

// Input fields for adding tags
const newQualification = ref('')
const newCertification = ref('')

// Pre-defined specialization options
const specializationOptions = [
  'IFR Training',
  'VFR Training',
  'Multi-Engine',
  'CRM',
  'Night Operations',
  'Mountain Flying',
  'Aerobatics',
  'Cross-Country',
  'Emergency Procedures',
  'Radio Navigation',
  'Glass Cockpit',
  'ATC Communication',
]

const days: AvailabilitySlot['day'][] = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
const periods: AvailabilitySlot['period'][] = ['am', 'pm']

const dayLabels: Record<AvailabilitySlot['day'], string> = {
  monday: 'Mon',
  tuesday: 'Tue',
  wednesday: 'Wed',
  thursday: 'Thu',
  friday: 'Fri',
  saturday: 'Sat',
  sunday: 'Sun',
}

async function loadProfile() {
  isLoading.value = true
  error.value = null
  try {
    const data = await instructor.getMyProfile()
    profile.value = data
    populateForm(data)
  }
  catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to load profile'
  }
  finally {
    isLoading.value = false
  }
}

function populateForm(data: InstructorProfile) {
  bio.value = data.bio ?? ''
  qualifications.value = [...(data.qualifications ?? [])]
  certifications.value = [...(data.certifications ?? [])]
  specializations.value = [...(data.specializations ?? [])]

  // Initialize availability grid
  if (data.availability && data.availability.length > 0) {
    availability.value = [...data.availability]
  }
  else {
    // Generate default availability (all unavailable)
    availability.value = []
    for (const day of days) {
      for (const period of periods) {
        availability.value.push({ day, period, available: false })
      }
    }
  }
}

function getSlotAvailable(day: AvailabilitySlot['day'], period: AvailabilitySlot['period']): boolean {
  const slot = availability.value.find(s => s.day === day && s.period === period)
  return slot?.available ?? false
}

function toggleSlot(day: AvailabilitySlot['day'], period: AvailabilitySlot['period']) {
  const idx = availability.value.findIndex(s => s.day === day && s.period === period)
  if (idx !== -1) {
    availability.value[idx] = { ...availability.value[idx], available: !availability.value[idx].available }
  }
}

function addQualification() {
  const val = newQualification.value.trim()
  if (val && !qualifications.value.includes(val)) {
    qualifications.value.push(val)
    newQualification.value = ''
  }
}

function removeQualification(index: number) {
  qualifications.value.splice(index, 1)
}

function addCertification() {
  const val = newCertification.value.trim()
  if (val && !certifications.value.includes(val)) {
    certifications.value.push(val)
    newCertification.value = ''
  }
}

function removeCertification(index: number) {
  certifications.value.splice(index, 1)
}

function toggleSpecialization(spec: string) {
  const idx = specializations.value.indexOf(spec)
  if (idx !== -1) {
    specializations.value.splice(idx, 1)
  }
  else {
    specializations.value.push(spec)
  }
}

async function saveProfile() {
  isSaving.value = true
  error.value = null
  saveSuccess.value = false
  try {
    const payload: InstructorProfileUpdate = {
      bio: bio.value,
      qualifications: qualifications.value,
      certifications: certifications.value,
      specializations: specializations.value,
      availability: availability.value,
    }
    profile.value = await instructor.updateMyProfile(payload)
    saveSuccess.value = true
    setTimeout(() => {
      saveSuccess.value = false
    }, 3000)
  }
  catch (e) {
    error.value = e instanceof Error ? e.message : 'Failed to save profile'
  }
  finally {
    isSaving.value = false
  }
}

function renderStars(rating: number): string[] {
  const stars: string[] = []
  for (let i = 1; i <= 5; i++) {
    if (i <= Math.floor(rating)) stars.push('full')
    else if (i - 0.5 <= rating) stars.push('half')
    else stars.push('empty')
  }
  return stars
}

onMounted(loadProfile)
</script>

<template>
  <NuxtLayout>
    <template #header>
      <AppHeader title="Instructor Profile" subtitle="TRAINING SYSTEM - HORUS V.0.2-TOKYO" />
    </template>

    <template #default>
      <div class="p-4 lg:p-6 space-y-6 max-w-4xl mx-auto">
        <!-- Page Header -->
        <div class="flex items-center gap-3">
          <NuxtLink
            to="/instructor"
            class="p-1.5 rounded-md text-horus-text-muted hover:text-horus-text-primary hover:bg-horus-bg-tertiary transition-colors"
          >
            <Icon name="heroicons:arrow-left" class="w-5 h-5" />
          </NuxtLink>
          <div>
            <h1 class="text-2xl font-bold text-horus-text-primary">Instructor Profile</h1>
            <p class="text-sm text-horus-text-secondary mt-1">Manage your instructor details and availability</p>
          </div>
        </div>

        <!-- Error State -->
        <HCard v-if="error" variant="elevated" padding="lg">
          <div class="flex items-center gap-3 text-horus-status-danger">
            <Icon name="heroicons:exclamation-triangle" class="w-6 h-6 flex-shrink-0" />
            <div class="flex-1">
              <p class="font-medium">{{ error }}</p>
            </div>
            <HButton variant="secondary" size="sm" icon="heroicons:arrow-path" @click="loadProfile">
              Retry
            </HButton>
          </div>
        </HCard>

        <!-- Save Success -->
        <Transition
          enter-active-class="transition-all duration-200"
          enter-from-class="opacity-0 -translate-y-2"
          enter-to-class="opacity-100 translate-y-0"
          leave-active-class="transition-all duration-150"
          leave-from-class="opacity-100"
          leave-to-class="opacity-0"
        >
          <div
            v-if="saveSuccess"
            class="flex items-center gap-3 p-3 rounded-lg bg-horus-status-success/10 border border-horus-status-success/30"
          >
            <Icon name="heroicons:check-circle" class="w-5 h-5 text-horus-status-success flex-shrink-0" />
            <span class="text-sm text-horus-status-success">Profile updated successfully</span>
          </div>
        </Transition>

        <!-- Loading -->
        <template v-if="isLoading">
          <HCard variant="elevated" padding="lg">
            <div class="animate-pulse space-y-6">
              <div class="flex items-center gap-4">
                <div class="w-16 h-16 rounded-full bg-horus-bg-tertiary" />
                <div class="space-y-2">
                  <div class="h-5 w-40 rounded bg-horus-bg-tertiary" />
                  <div class="h-3 w-56 rounded bg-horus-bg-tertiary" />
                </div>
              </div>
              <div class="h-24 rounded bg-horus-bg-tertiary" />
              <div class="h-12 rounded bg-horus-bg-tertiary" />
            </div>
          </HCard>
        </template>

        <!-- Profile Form -->
        <template v-else-if="profile">
          <!-- Profile Header -->
          <HCard variant="elevated" padding="lg">
            <div class="flex items-center gap-4">
              <div class="w-16 h-16 rounded-full bg-horus-bg-tertiary border-2 border-horus-accent-cyan/30 overflow-hidden flex-shrink-0">
                <img
                  :src="`https://api.dicebear.com/7.x/avataaars/svg?seed=${profile.avatar_seed || user?.keycloakId}`"
                  :alt="profile.display_name"
                  class="w-full h-full object-cover"
                />
              </div>
              <div>
                <h2 class="text-lg font-bold text-horus-text-primary">{{ profile.display_name }}</h2>
                <p class="text-sm text-horus-text-muted">{{ profile.email }}</p>
                <!-- Rating Stars -->
                <div v-if="profile.rating > 0" class="flex items-center gap-1 mt-1.5">
                  <Icon
                    v-for="(star, idx) in renderStars(profile.rating)"
                    :key="idx"
                    :name="star === 'full' ? 'heroicons:star-solid' : star === 'half' ? 'heroicons:star' : 'heroicons:star'"
                    :class="[
                      'w-4 h-4',
                      star === 'full' ? 'text-yellow-400' : star === 'half' ? 'text-yellow-400/50' : 'text-horus-text-muted/30',
                    ]"
                  />
                  <span class="text-xs text-horus-text-secondary ml-1">{{ profile.rating.toFixed(1) }}</span>
                </div>
              </div>
              <div class="ml-auto hidden sm:flex items-center gap-4 text-center">
                <div>
                  <p class="text-lg font-bold text-horus-text-primary font-mono">{{ profile.total_students }}</p>
                  <p class="text-xxs text-horus-text-muted uppercase tracking-wider">Students</p>
                </div>
                <div class="w-px h-8 bg-horus-border-subtle" />
                <div>
                  <p class="text-lg font-bold text-horus-text-primary font-mono">{{ profile.total_sessions_conducted }}</p>
                  <p class="text-xxs text-horus-text-muted uppercase tracking-wider">Sessions</p>
                </div>
              </div>
            </div>
          </HCard>

          <!-- Bio Section -->
          <HSection title="Bio" icon="heroicons:document-text">
            <HCard variant="elevated" padding="md">
              <textarea
                v-model="bio"
                rows="4"
                placeholder="Write a brief bio about your experience and teaching philosophy..."
                class="w-full bg-horus-bg-secondary border border-horus-border-subtle rounded-lg px-4 py-3 text-sm text-horus-text-primary placeholder:text-horus-text-muted focus:outline-none focus:border-horus-accent-cyan focus:ring-1 focus:ring-horus-accent-cyan/50 resize-none"
              />
            </HCard>
          </HSection>

          <!-- Qualifications -->
          <HSection title="Qualifications" icon="heroicons:academic-cap">
            <HCard variant="elevated" padding="md">
              <div class="space-y-3">
                <!-- Tags -->
                <div class="flex flex-wrap gap-2">
                  <span
                    v-for="(qual, idx) in qualifications"
                    :key="qual"
                    class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-horus-accent-cyan/10 text-horus-accent-cyan border border-horus-accent-cyan/20"
                  >
                    {{ qual }}
                    <button
                      class="p-0.5 rounded-full hover:bg-horus-accent-cyan/20 transition-colors"
                      @click="removeQualification(idx)"
                    >
                      <Icon name="heroicons:x-mark" class="w-3 h-3" />
                    </button>
                  </span>
                  <span
                    v-if="qualifications.length === 0"
                    class="text-xs text-horus-text-muted"
                  >
                    No qualifications added yet
                  </span>
                </div>

                <!-- Add Input -->
                <div class="flex items-center gap-2">
                  <input
                    v-model="newQualification"
                    type="text"
                    placeholder="Add qualification (e.g., CFI, CFII, MEI, ATP)..."
                    class="flex-1 bg-horus-bg-secondary border border-horus-border-subtle rounded-lg px-3 py-2 text-sm text-horus-text-primary placeholder:text-horus-text-muted focus:outline-none focus:border-horus-accent-cyan focus:ring-1 focus:ring-horus-accent-cyan/50"
                    @keydown.enter.prevent="addQualification"
                  />
                  <HButton variant="secondary" size="sm" icon="heroicons:plus" @click="addQualification">
                    Add
                  </HButton>
                </div>
              </div>
            </HCard>
          </HSection>

          <!-- Certifications -->
          <HSection title="Certifications" icon="heroicons:shield-check">
            <HCard variant="elevated" padding="md">
              <div class="space-y-3">
                <!-- Tags -->
                <div class="flex flex-wrap gap-2">
                  <span
                    v-for="(cert, idx) in certifications"
                    :key="cert"
                    class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-horus-status-info/10 text-horus-status-info border border-horus-status-info/20"
                  >
                    {{ cert }}
                    <button
                      class="p-0.5 rounded-full hover:bg-horus-status-info/20 transition-colors"
                      @click="removeCertification(idx)"
                    >
                      <Icon name="heroicons:x-mark" class="w-3 h-3" />
                    </button>
                  </span>
                  <span
                    v-if="certifications.length === 0"
                    class="text-xs text-horus-text-muted"
                  >
                    No certifications added yet
                  </span>
                </div>

                <!-- Add Input -->
                <div class="flex items-center gap-2">
                  <input
                    v-model="newCertification"
                    type="text"
                    placeholder="Add certification (e.g., FAA Part 141, EASA)..."
                    class="flex-1 bg-horus-bg-secondary border border-horus-border-subtle rounded-lg px-3 py-2 text-sm text-horus-text-primary placeholder:text-horus-text-muted focus:outline-none focus:border-horus-accent-cyan focus:ring-1 focus:ring-horus-accent-cyan/50"
                    @keydown.enter.prevent="addCertification"
                  />
                  <HButton variant="secondary" size="sm" icon="heroicons:plus" @click="addCertification">
                    Add
                  </HButton>
                </div>
              </div>
            </HCard>
          </HSection>

          <!-- Specializations -->
          <HSection title="Specializations" icon="heroicons:tag">
            <HCard variant="elevated" padding="md">
              <div class="grid grid-cols-2 sm:grid-cols-3 gap-2">
                <button
                  v-for="spec in specializationOptions"
                  :key="spec"
                  :class="[
                    'flex items-center gap-2 px-3 py-2.5 rounded-lg text-xs font-medium transition-all duration-200 border text-left',
                    specializations.includes(spec)
                      ? 'bg-horus-accent-cyan/10 text-horus-accent-cyan border-horus-accent-cyan/30'
                      : 'bg-horus-bg-secondary text-horus-text-secondary border-horus-border-subtle hover:border-horus-accent-cyan/20 hover:text-horus-text-primary',
                  ]"
                  @click="toggleSpecialization(spec)"
                >
                  <Icon
                    :name="specializations.includes(spec) ? 'heroicons:check-circle' : 'heroicons:plus-circle'"
                    :class="[
                      'w-4 h-4 flex-shrink-0',
                      specializations.includes(spec) ? 'text-horus-accent-cyan' : 'text-horus-text-muted',
                    ]"
                  />
                  {{ spec }}
                </button>
              </div>
            </HCard>
          </HSection>

          <!-- Availability Schedule -->
          <HSection title="Availability Schedule" icon="heroicons:calendar-days">
            <HCard variant="elevated" padding="md">
              <div class="space-y-4">
                <p class="text-xs text-horus-text-secondary">
                  Click to toggle your availability for each time slot
                </p>

                <!-- Grid Header -->
                <div class="overflow-x-auto">
                  <table class="w-full min-w-[400px]">
                    <thead>
                      <tr>
                        <th class="text-left text-xxs font-semibold uppercase tracking-wider text-horus-text-muted px-2 py-2 w-16" />
                        <th
                          v-for="day in days"
                          :key="day"
                          class="text-center text-xxs font-semibold uppercase tracking-wider text-horus-text-muted px-1 py-2"
                        >
                          {{ dayLabels[day] }}
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="period in periods" :key="period">
                        <td class="text-right text-xxs font-semibold uppercase tracking-wider text-horus-text-muted px-2 py-1">
                          {{ period.toUpperCase() }}
                        </td>
                        <td
                          v-for="day in days"
                          :key="`${day}-${period}`"
                          class="text-center px-1 py-1"
                        >
                          <button
                            :class="[
                              'w-full h-10 rounded-lg border transition-all duration-200',
                              getSlotAvailable(day, period)
                                ? 'bg-horus-status-success/20 border-horus-status-success/30 hover:bg-horus-status-success/30'
                                : 'bg-horus-bg-secondary border-horus-border-subtle hover:border-horus-accent-cyan/30 hover:bg-horus-bg-tertiary',
                            ]"
                            @click="toggleSlot(day, period)"
                          >
                            <Icon
                              v-if="getSlotAvailable(day, period)"
                              name="heroicons:check"
                              class="w-4 h-4 text-horus-status-success mx-auto"
                            />
                          </button>
                        </td>
                      </tr>
                    </tbody>
                  </table>
                </div>

                <!-- Legend -->
                <div class="flex items-center gap-4 text-xs text-horus-text-muted">
                  <div class="flex items-center gap-1.5">
                    <div class="w-4 h-4 rounded bg-horus-status-success/20 border border-horus-status-success/30" />
                    <span>Available</span>
                  </div>
                  <div class="flex items-center gap-1.5">
                    <div class="w-4 h-4 rounded bg-horus-bg-secondary border border-horus-border-subtle" />
                    <span>Unavailable</span>
                  </div>
                </div>
              </div>
            </HCard>
          </HSection>

          <!-- Save Button -->
          <div class="flex items-center justify-end gap-3 pt-2 pb-8">
            <NuxtLink to="/instructor">
              <HButton variant="ghost" size="md">
                Cancel
              </HButton>
            </NuxtLink>
            <HButton
              variant="primary"
              size="md"
              icon="heroicons:check"
              :loading="isSaving"
              @click="saveProfile"
            >
              Save Profile
            </HButton>
          </div>
        </template>
      </div>
    </template>
  </NuxtLayout>
</template>
