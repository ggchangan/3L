import { defineConfig } from 'vite'
import { resolve } from 'path'

// Multi-page app: all .html files in root are entry points
const htmlPages = [
  'index', 'review', 'monitor', 'macro', 'stock_analysis',
  'simulation', 'watchlist', 'trend_candidates', 'tips',
  'tip-detail', 'industry', 'journal', 'top_gainers',
  'skills',
]

export default defineConfig({
  root: '.',
  base: '/',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    // Multi-page: one rollup input per HTML file
    rollupOptions: {
      input: htmlPages.map(p => resolve(__dirname, `${p}.html`)),
    },
  },
  server: {
    port: 5173,
    // Proxy API requests to backend server
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
