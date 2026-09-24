import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

// Servidor de desarrollo en http://localhost:5173.
// Todas las llamadas a /api se reenvian al backend Java. Se usa 127.0.0.1 (y no
// "localhost") porque en algunas computadoras "localhost" resuelve primero a IPv6.
export default defineConfig({
  plugins: [react()],
  // Aplicacion local: un unico paquete de ~850 kB es aceptable (evita el aviso de tamano).
  build: {
    chunkSizeWarningLimit: 1000,
  },
  server: {
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8080',
        changeOrigin: true,
      },
    },
  },
})
