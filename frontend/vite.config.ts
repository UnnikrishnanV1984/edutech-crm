import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
  server: {
    // Specify the exact hostnames allowed to access the dev server
    allowedHosts: [
      'localhost:5173',
      '0dd0-2401-4900-883b-47e4-904a-f05b-af1f-748.ngrok-free.app'
    ]
  }
})
