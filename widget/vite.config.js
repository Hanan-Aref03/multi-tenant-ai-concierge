import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [react()],
  build: {
    rollupOptions: {
      input: {
        index: fileURLToPath(new URL('./index.html', import.meta.url)),
        embed: fileURLToPath(new URL('./embed.html', import.meta.url)),
      },
      output: {
        manualChunks: undefined,
      },
    },
  },
})
