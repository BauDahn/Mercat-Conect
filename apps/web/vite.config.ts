import { resolve } from 'node:path'
import { defineConfig, loadEnv } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'

// Puertos: WEB_PORT (def. 5173) y API_PORT (def. 8000). Se leen del entorno o del .env de la raíz (solo lectura).
export default defineConfig(({ mode }) => {
  const env = { ...loadEnv(mode, resolve(__dirname, '../..'), ''), ...process.env }
  const webPort = Number(env.WEB_PORT ?? 5173)
  const apiTarget = env.API_TARGET || `http://localhost:${env.API_PORT ?? 8000}`
  // El contrato no lleva prefijo /api: el proxy lo elimina.
  const proxy = {
    '/api': { target: apiTarget, changeOrigin: false, rewrite: (p: string) => p.replace(/^\/api/, '') },
    // Fotos subidas por productores: la API las sirve en la raíz (photo_url = /uploads/...).
    '/uploads': { target: apiTarget, changeOrigin: false },
  }
  return {
    plugins: [
      react(),
      tailwindcss(),
      VitePWA({
        registerType: 'autoUpdate',
        includeAssets: ['icon.svg', 'icon-192.png', 'icon-512.png'],
        manifest: {
          name: 'Mercat-Conect',
          short_name: 'Mercat',
          description: 'Rescata producto fresco de los mercados de València',
          lang: 'es',
          start_url: '/',
          scope: '/',
          display: 'standalone',
          background_color: '#f6f3ec',
          theme_color: '#14633c',
          icons: [
            { src: 'icon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any' },
            { src: 'icon-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
            { src: 'icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
            { src: 'icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
          ],
        },
        workbox: {
          navigateFallback: '/index.html',
          navigateFallbackDenylist: [/^\/api\//],
          globPatterns: ['**/*.{js,css,html,svg,json,woff2}'],
          runtimeCaching: [
            {
              // Último listado para verlo sin conexión (la compra se bloquea en la UI).
              urlPattern: ({ url, request }) => request.method === 'GET' && url.pathname === '/api/offers',
              handler: 'NetworkFirst',
              options: { cacheName: 'offers-list', networkTimeoutSeconds: 4 },
            },
          ],
        },
      }),
    ],
    server: { port: webPort, strictPort: true, host: true, proxy },
    preview: { port: webPort, proxy },
  }
})
