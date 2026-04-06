export default defineNuxtConfig({
  extends: ['../../packages/core'],

  app: {
    head: {
      titleTemplate: '%s · Hangar · Horus',
      meta: [{ name: 'application-name', content: 'Horus Hangar' }],
    },
  },
  runtimeConfig: {
    public: {
      appId: 'hangar',
    },
  },
  buildDir: '.nuxt',
  devServer: {
    port: 3002,
  },
})
