import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Vite configuration for the React frontend. The proxy directs API calls
// from the dev server to the backend service when running in docker
// compose. In production the static files will be served by Nginx.

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3000,
    proxy: {
      '/login': {
        target: 'http://backend:8000',
        changeOrigin: true,
      },
      '/upload': {
        target: 'http://backend:8000',
        changeOrigin: true,
      },
      '/photos': {
        target: 'http://backend:8000',
        changeOrigin: true,
      },
      '/export': {
        target: 'http://backend:8000',
        changeOrigin: true,
      },
      '/client': {
        target: 'http://backend:8000',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
  },
});