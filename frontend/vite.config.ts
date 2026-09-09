import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
export default defineConfig({
  plugins: [vue()],
  base: '/erp/',
  server: {
    host: '127.0.0.1',
    port: 18310,
    proxy: {
      '/api': { target: process.env.VITE_API_BASE_URL || 'http://127.0.0.1:18301', changeOrigin: true },
    },
  },
})
