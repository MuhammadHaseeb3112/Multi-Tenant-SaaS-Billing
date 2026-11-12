import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Same-origin API in development: the browser talks to Vite only and
    // Vite forwards /api to Django, so the httpOnly refresh cookie is a
    // first-party cookie (same setup as nginx in production).
    proxy: {
      '/api': {
        target: process.env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000',
        changeOrigin: false,
      },
    },
  },
})
