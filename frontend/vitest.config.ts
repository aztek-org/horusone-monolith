import { defineVitestConfig } from '@nuxt/test-utils/config'
import { fileURLToPath } from 'node:url'

const workspaceRoot = fileURLToPath(new URL('.', import.meta.url))

export default defineVitestConfig({
  test: {
    root: workspaceRoot,
    environment: 'happy-dom',
    globals: true,
    include: ['packages/core/app/**/*.test.ts', 'packages/core/app/**/*.spec.ts'],
  },
})
