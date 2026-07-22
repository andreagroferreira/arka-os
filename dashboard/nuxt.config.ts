// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  modules: [
    '@nuxt/eslint',
    '@nuxt/fonts',
    '@nuxt/ui',
    '@vueuse/nuxt',
    '@nuxt/test-utils/module'
  ],

  ssr: false,

  devtools: {
    enabled: true
  },

  app: {
    pageTransition: {
      name: 'arka-page',
      mode: 'out-in'
    }
  },

  css: ['~/assets/css/main.css'],

  colorMode: {
    preference: 'dark',
    fallback: 'dark'
  },

  runtimeConfig: {
    public: {
      apiBase: 'http://localhost:3334'
    }
  },

  routeRules: {
    '/api/**': {
      cors: true
    }
  },

  compatibilityDate: '2024-07-11',

  eslint: {
    config: {
      stylistic: {
        commaDangle: 'never',
        braceStyle: '1tbs'
      }
    }
  },

  fonts: {
    families: [
      // Explicit entry guarantees the italic axis (Instrument Serif ships
      // 400 normal+italic only); the other families auto-resolve from @theme.
      { name: 'Instrument Serif', provider: 'google', weights: [400], styles: ['normal', 'italic'] }
    ]
  },

  vite: {
    optimizeDeps: {
      include: ['@unovis/ts > striptags']
    }
  }
})
