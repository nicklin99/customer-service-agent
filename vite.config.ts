import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/chat': 'http://localhost:8080',
      '/stop': 'http://localhost:8080',
      '/crm-sync': 'http://localhost:8080',
      '/leads': 'http://localhost:8080',
      '/profile': 'http://localhost:8080',
    },
  },
})
