import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    open: true
  },
  define: {
    // Makes VITE_API_URL available at build time via import.meta.env
    // Falls back to localhost for local dev if not set
  }
})
