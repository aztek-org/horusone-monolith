export default defineNuxtConfig({
  extends: ['../../packages/core'],

  app: {
    head: {
      titleTemplate: '%s · Squawk · Horus',
      meta: [{ name: 'application-name', content: 'Horus Squawk' }],
    },
  },
  runtimeConfig: {
    public: {
      appId: 'squawk',
    },
  },
  buildDir: '.nuxt',
  devServer: {
    port: 3000,
  },
})
