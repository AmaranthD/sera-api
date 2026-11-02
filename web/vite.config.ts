/// <reference types="vitest/config" />
import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      includeAssets: ['favicon.svg', 'icons/*.png'],
      manifest: {
        name: 'Sera',
        short_name: 'Sera',
        description: 'Um lugar calmo para conversar.',
        lang: 'pt-BR',
        id: '/',
        start_url: '/',
        scope: '/',
        display: 'standalone',
        display_override: ['standalone'],
        orientation: 'portrait-primary',
        background_color: '#080c18',
        theme_color: '#080c18',
        categories: ['lifestyle', 'social'],
        icons: [
          {
            src: '/icons/icon-192-v2.png',
            sizes: '192x192',
            type: 'image/png',
          },
          {
            src: '/icons/icon-512-v2.png',
            sizes: '512x512',
            type: 'image/png',
          },
          {
            src: '/icons/icon-maskable-512-v2.png',
            sizes: '512x512',
            type: 'image/png',
            purpose: 'maskable',
          },
        ],
      },
      workbox: {
        importScripts: ['/push-handlers.js'],
        globPatterns: ['**/*.{js,css,html,svg,png,webp,woff2}'],
        globIgnores: ['**/fundo/paladina.webm', '**/fundo/paladina.mp4'],
        navigateFallback: '/index.html',
        navigateFallbackDenylist: [/^\/api\//],
        cleanupOutdatedCaches: true,
        clientsClaim: true,
        skipWaiting: true,
      },
      devOptions: {
        enabled: false,
      },
    }),
  ],
  build: {
    target: 'es2022',
    sourcemap: false,
    rolldownOptions: {
      output: {
        codeSplitting: {
          groups: [
            {
              name: 'supabase',
              test: /node_modules[\\/]@supabase[\\/]/,
            },
            {
              name: 'react',
              test: /node_modules[\\/](react|react-dom|react-router|react-router-dom)[\\/]/,
            },
          ],
        },
      },
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    css: true,
    setupFiles: ['./src/test/setup.ts'],
    exclude: ['e2e/**', 'node_modules/**', 'dist/**'],
    coverage: {
      reporter: ['text', 'html'],
      include: ['src/**/*.{ts,tsx}'],
      exclude: ['src/**/*.test.{ts,tsx}', 'src/test/**', 'src/main.tsx'],
    },
  },
})
