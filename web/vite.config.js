import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  base: '/opencodego-compare/',
  plugins: [vue()],
  server: { fs: { allow: ['..'] } },
  build: { outDir: 'dist' },
})
