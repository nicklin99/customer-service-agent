import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { readFileSync } from 'fs'

const pkg = JSON.parse(readFileSync('./package.json', 'utf-8'))

export default defineConfig({
  plugins: [react()],
  define: {
    __APP_VERSION__: JSON.stringify('v' + pkg.version),
  },
  server: {
    proxy: {
      '/chat': 'http://localhost:8080',
      '/stop': 'http://localhost:8080',
      '/crm-sync': 'http://localhost:8080',
      '/leads': 'http://localhost:8080',
      '/profile': 'http://localhost:8080',
      '/settings': 'http://localhost:8080',
    },
  },
})
