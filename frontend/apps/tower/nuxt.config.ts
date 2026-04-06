export default defineNuxtConfig({
  extends: ['../../packages/core'],

  app: {
    head: {
      titleTemplate: '%s · Tower · Horus',
      meta: [{ name: 'application-name', content: 'Horus Tower' }],
    },
  },
  runtimeConfig: {
    public: {
      appId: 'tower',
    },
  },
  buildDir: '.nuxt',
  devServer: {
    port: 3001,
  },
})
