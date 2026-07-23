import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { fileURLToPath } from 'node:url'

// https://vite.dev/config/
// Two HTML entries share this config: the chat app (index.html) and the
// admin-only trace viewer dashboard (traces.html, CHO-262). The framework-free
// corner widget builds from its own config (vite.widget.config.ts).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    rollupOptions: {
      input: {
        main: fileURLToPath(new URL('./index.html', import.meta.url)),
        traces: fileURLToPath(new URL('./traces.html', import.meta.url)),
      },
    },
  },
  server: {
    proxy: {
      // Backend (FastAPI) is developed in parallel on port 8000.
      '/api': 'http://localhost:8000',
    },
  },
})
