import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { VitePWA } from 'vite-plugin-pwa';

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      workbox: {
        globPatterns: ['**/*.{js,css,html,svg,png,ico}'],
        runtimeCaching: [
          { urlPattern: /scores\.json$/, handler: 'CacheFirst', options: { cacheName: 'scores', expiration: { maxEntries: 1 } } },
          { urlPattern: /provenance\.json$/, handler: 'CacheFirst', options: { cacheName: 'provenance', expiration: { maxEntries: 1 } } }
        ]
      },
      manifest: {
        name: 'STARSAI', short_name: 'STARSAI',
        description: 'TTC nighttime safety',
        theme_color: '#0b0f1a', background_color: '#0b0f1a',
        display: 'standalone', start_url: '/',
        icons: [
          { src: 'icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icon-512.png', sizes: '512x512', type: 'image/png' }
        ]
      }
    })
  ]
});
