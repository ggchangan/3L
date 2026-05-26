/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'

// 单页 React SPA 入口
const htmlPages = ['react']

export default defineConfig({
  root: '.',
  base: '/',
  plugins: [react()],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    rollupOptions: {
      input: htmlPages.map(p => resolve(__dirname, `${p}.html`)),
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
      '/private': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
      '/download': {
        target: 'http://localhost:8080',
        changeOrigin: true,
      },
    },
  },
})
