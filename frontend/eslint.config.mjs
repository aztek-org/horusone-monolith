import { createConfigForNuxt } from '@nuxt/eslint/config'

export default createConfigForNuxt({
  features: {
    stylistic: true,
  },
}).append({
  rules: {
    'no-console': 'warn',
    '@typescript-eslint/no-explicit-any': 'warn',
  },
})
