<template>
  <HCard variant="default" padding="md">
    <div class="space-y-3">
      <div class="flex items-center gap-2">
        <Icon name="heroicons:hand-raised" class="w-4 h-4 text-horus-status-warning" />
        <h2 class="text-sm font-semibold text-horus-text-primary">
          Held Exchange Review
        </h2>
      </div>

      <div v-if="isLoading" class="flex items-center gap-2 py-4 text-horus-text-muted">
        <Icon name="svg-spinners:ring-resize" class="w-4 h-4" />
        <span class="text-xs">Checking for a held exchange...</span>
      </div>

      <p v-else-if="error" class="text-xs text-horus-status-danger">
        {{ error }}
      </p>

      <div v-else-if="!held" class="rounded-lg border border-horus-border-subtle p-3">
        <p class="text-xs text-horus-text-muted">
          No exchange is awaiting review for this session.
        </p>
        <HButton
          variant="secondary"
          size="sm"
          class="mt-2"
          :loading="isSubmitting"
          @click="refresh"
        >
          Refresh
        </HButton>
      </div>

      <div v-else class="space-y-3">
        <p class="text-xs text-horus-text-secondary">
          The pilot's last transmission is held. Send an instructor response, or
          release the AI's own response.
        </p>

        <textarea
          v-model="responseText"
          rows="3"
          placeholder="Instructor response (optional)"
          class="w-full rounded-lg border border-horus-border-subtle bg-horus-bg-tertiary px-3 py-2 text-sm text-horus-text-primary focus:border-horus-accent-cyan focus:outline-none"
        />

        <div class="flex items-center gap-2">
          <HButton
            variant="primary"
            size="sm"
            :disabled="!responseText.trim() || isSubmitting"
            :loading="isSubmitting"
            @click="submit(responseText)"
          >
            Send override
          </HButton>
          <HButton
            variant="secondary"
            size="sm"
            :disabled="isSubmitting"
            data-testid="release-ai-response"
            @click="submit()"
          >
            Release AI response
          </HButton>
        </div>
      </div>
    </div>
  </HCard>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import {
  heldExchangeFromEvents,
  type InstructorExchangeResponse,
  useInstructor,
} from '~/composables/useInstructor'

const props = defineProps<{ sessionId: number | string }>()

const emit = defineEmits<{ released: [InstructorExchangeResponse] }>()

const { getSessionEvents, respondToHeldExchange } = useInstructor()

const isLoading = ref(true)
const isSubmitting = ref(false)
const error = ref<string | null>(null)
const held = ref(false)
const responseText = ref('')

async function refresh(): Promise<void> {
  isLoading.value = true
  error.value = null
  try {
    const events = await getSessionEvents(props.sessionId)
    held.value = heldExchangeFromEvents(events)
  }
  catch (err) {
    error.value = (err as { detail?: string }).detail ?? 'Failed to load exchange state'
  }
  finally {
    isLoading.value = false
  }
}

async function submit(instructorResponse?: string): Promise<void> {
  if (isSubmitting.value) return

  const text = instructorResponse?.trim()
  isSubmitting.value = true
  error.value = null
  try {
    const result = await respondToHeldExchange(props.sessionId, text || undefined)
    held.value = false
    responseText.value = ''
    emit('released', result)
  }
  catch (err) {
    error.value = (err as { detail?: string }).detail ?? 'Failed to release exchange'
  }
  finally {
    isSubmitting.value = false
  }
}

onMounted(refresh)

defineExpose({ refresh })
</script>
