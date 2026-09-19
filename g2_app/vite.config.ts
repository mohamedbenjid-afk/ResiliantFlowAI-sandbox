import { defineConfig } from 'vite'

export default defineConfig({
  build: {
    outDir: 'dist',
    target: 'es2022',
  },
  server: {
    port: 5174,
    strictPort: true,
    host: true,        // expose sur le réseau local (téléphone Even Hub)
    proxy: {
      // Proxy /notion-api → api.notion.com pour éviter les erreurs CORS en dev
      '/notion-api': {
        target: 'https://api.notion.com',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/notion-api/, ''),
      },
      '/rul-api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/rul-api/, ''),
      },
    },
  },
  envPrefix: 'VITE_',
})
