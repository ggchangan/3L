/// <reference types="vitest" />
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { resolve } from 'path'

// 多页 + React SPA 混合模式
// 旧 HTML 页面走多页入口，React 页面走 react.html 入口
const htmlPages = [
  'react',       // React SPA 入口（Monitor 首期迁移）
  'review', 'macro', 'stock_analysis',
  'simulation', 'watchlist', 'trend_candidates', 'tips',
  'tip-detail', 'industry', 'journal', 'top_gainers',
  'skills', 'holdings',
]

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
