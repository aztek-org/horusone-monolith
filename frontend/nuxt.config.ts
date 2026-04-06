// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },

  // Cloudflare Pages deployment
  nitro: {
    preset: process.env.CF_PAGES ? 'cloudflare-pages' : undefined,
  },

  // Runtime config — values injected from env at build time
  runtimeConfig: {
    public: {
      apiUrl: process.env.NUXT_PUBLIC_API_URL ?? 'http://localhost:8000',
      wsUrl: process.env.NUXT_PUBLIC_WS_URL ?? 'ws://localhost:8000/ws/voice',
      keycloakUrl: process.env.NUXT_PUBLIC_KEYCLOAK_URL ?? 'http://localhost:8080',
      keycloakRealm: process.env.NUXT_PUBLIC_KEYCLOAK_REALM ?? 'horus',
      keycloakClientId: process.env.NUXT_PUBLIC_KEYCLOAK_CLIENT_ID ?? 'horus-web',
    },
  },

  modules: ['@nuxt/icon', '@nuxt/eslint', '@nuxt/image'],

  css: [
    '~/assets/css/main.css',
    'leaflet/dist/leaflet.css'
  ],

  postcss: {
    plugins: {
      tailwindcss: {},
      autoprefixer: {},
    },
  },

  components: [
    { path: '~/components/ui', pathPrefix: false },
    { path: '~/components/shared', pathPrefix: false },
    { path: '~/components/scenario-architect', pathPrefix: false },
    { path: '~/components/mission-hub', pathPrefix: false },
    { path: '~/components/instructor', pathPrefix: false },
    { path: '~/components/flight-plan', pathPrefix: false },
    { path: '~/components/session', pathPrefix: false },
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
})