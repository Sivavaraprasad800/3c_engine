import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Local dev: proxy to local FRS server (port 8001 — 8000 is used by Django)
// Production (Render): frontend is served from same origin — no proxy needed
const LOCAL_SERVER = "http://127.0.0.1:8001"

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api':          { target: LOCAL_SERVER, changeOrigin: true },
      '/snapshots':    { target: LOCAL_SERVER, changeOrigin: true },
      '/train_images': { target: LOCAL_SERVER, changeOrigin: true }
    }
  }
})
