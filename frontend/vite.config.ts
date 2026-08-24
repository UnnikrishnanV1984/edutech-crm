import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Specify the exact hostnames allowed to access the dev server
    allowedHosts: [
      'localhost:5173',
      'https://tableware-ceramics-crimp.ngrok-free.dev'
    ]
  }
})
