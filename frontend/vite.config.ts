import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, './'),
      '@ui': resolve(__dirname, './components/ui'),
      '@chat': resolve(__dirname, './components/chat'),
      '@workspace': resolve(__dirname, './components/workspace'),
      '@settings': resolve(__dirname, './components/settings'),
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8080',
        ws: true,
      },
    },
  },
  optimizeDeps: {
    include: [],
  },
  build: {
    outDir: 'dist',
    sourcemap: true,
    commonjsOptions: {
      include: [/node_modules/],
      transformMixedEsModules: true,
    },
    rollupOptions: {
      output: {
        manualChunks: {
          'vendor': ['vue', 'vue-router', 'pinia'],
          'editor': ['monaco-editor'],
          'markdown': ['marked', 'highlight.js', 'katex'],
        },
      },
    },
  },
})
