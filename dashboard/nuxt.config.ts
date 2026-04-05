export default defineNuxtConfig({
  modules: ['@nuxt/ui'],

  ssr: false,

  app: {
    head: {
      title: 'ArkaOS Dashboard',
      meta: [
        { charset: 'utf-8' },
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
        { name: 'description', content: 'ArkaOS — AI Agent Operating System Dashboard' },
      ],
    },
  },

  runtimeConfig: {
    public: {
      apiBase: 'http://localhost:3334',
    },
  },

  compatibilityDate: '2025-01-01',
})
