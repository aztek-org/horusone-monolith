// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },

  modules: [
    '@nuxtjs/tailwindcss',
    '@nuxt/icon',
  ],

  css: ['~/assets/css/main.css'],

  components: [
    { path: '~/components/ui', pathPrefix: false },
    { path: '~/components/shared', pathPrefix: false },
    { path: '~/components/scenario-architect', pathPrefix: false },
    { path: '~/components/mission-hub', pathPrefix: false },
  ],

  app: {
    head: {
      title: 'Horus - Aviation Training Platform',
      meta: [
        { name: 'description', content: 'AI-Powered Aviation Training & Simulation Platform' },
        { name: 'theme-color', content: '#0a0f1a' }
      ],
      link: [
        { rel: 'preconnect', href: 'https://fonts.googleapis.com' },
        { rel: 'preconnect', href: 'https://fonts.gstatic.com', crossorigin: '' },
        { rel: 'stylesheet', href: 'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap' }
      ]
    }
  },

  tailwindcss: {
    configPath: 'tailwind.config.ts',
  },
})
