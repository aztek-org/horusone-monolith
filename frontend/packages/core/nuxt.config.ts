import { fileURLToPath } from 'node:url'

const rootDir = fileURLToPath(new URL('../../', import.meta.url))
const defaultHangarUrl = process.env.NUXT_PUBLIC_HANGAR_URL ?? 'http://localhost:3002'
const defaultTowerUrl = process.env.NUXT_PUBLIC_TOWER_URL ?? 'http://localhost:3001'
const defaultSquawkUrl = process.env.NUXT_PUBLIC_SQUAWK_URL ?? 'http://localhost:3000'
const defaultAuthGatewayUrl = process.env.NUXT_PUBLIC_AUTH_GATEWAY_URL ?? defaultHangarUrl

// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({

  modules: ['@nuxt/icon', '@nuxt/eslint', '@nuxt/image', '@nuxtjs/tailwindcss'],

  icon: {
    serverBundle: 'local',
    clientBundle: {
      scan: true,
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
  devtools: { enabled: true },

  app: {
    head: {
      title: 'Horus - Aviation Training Platform',
      meta: [
        {
          name: 'description',
          content: 'AI-Powered Aviation Training & Simulation Platform',
        },
        { name: 'theme-color', content: '#0a0f1a' },
      ],
      link: [
        { rel: 'preconnect', href: 'https://fonts.googleapis.com' },
        { rel: 'preconnect', href: 'https://fonts.gstatic.com', crossorigin: '' },
        {
          rel: 'stylesheet',
          href: 'https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap',
        },
      ],
    },
  },

  css: ['leaflet/dist/leaflet.css'],

  // Runtime config — values injected from env at build time
  runtimeConfig: {
    public: {
      apiUrl: process.env.NUXT_PUBLIC_API_URL ?? '',
      wsUrl: process.env.NUXT_PUBLIC_WS_URL ?? 'ws://localhost:8000/ws/voice',
      keycloakUrl: process.env.NUXT_PUBLIC_KEYCLOAK_URL ?? 'http://localhost:8180',
      keycloakRealm: process.env.NUXT_PUBLIC_KEYCLOAK_REALM ?? 'horus',
      keycloakClientId: process.env.NUXT_PUBLIC_KEYCLOAK_CLIENT_ID ?? 'horus-web',
      appId: process.env.NUXT_PUBLIC_APP_ID ?? 'hangar',
      hangarUrl: defaultHangarUrl,
      towerUrl: defaultTowerUrl,
      squawkUrl: defaultSquawkUrl,
      authGatewayUrl: defaultAuthGatewayUrl,
    },
  },
  srcDir: 'app',

  alias: {
    '~': fileURLToPath(new URL('./app', import.meta.url)),
    '@': fileURLToPath(new URL('./app', import.meta.url)),
    '~~': rootDir,
    '@@': rootDir,
  },
  compatibilityDate: '2025-07-15',

  // Cloudflare Pages deployment
  nitro: {
    preset: process.env.CF_PAGES ? 'cloudflare-pages' : undefined,
    devProxy: {
      '/api/': { target: 'http://localhost:8000/api/', changeOrigin: true },
      '/health': { target: 'http://localhost:8000/health', changeOrigin: true },
      '/ws/': { target: 'ws://localhost:8000/ws/', changeOrigin: true, ws: true },
    },
  },

  tailwindcss: {
    cssPath: '~/assets/css/main.css',
    configPath: fileURLToPath(new URL('./tailwind.config.ts', import.meta.url)),
  },
})
