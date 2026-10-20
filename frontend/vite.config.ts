import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { readFileSync } from 'node:fs'
import { isIP } from 'node:net'

const certificate=process.env.SAFERIDE_HTTPS_CERT
const privateKey=process.env.SAFERIDE_HTTPS_KEY
const phoneHost=process.env.SAFERIDE_HTTPS_HOST
if(phoneHost&&!isIP(phoneHost))throw new Error('SAFERIDE_HTTPS_HOST must be a local IP address.')
if(Boolean(certificate)!==Boolean(privateKey))throw new Error('Set both SAFERIDE_HTTPS_CERT and SAFERIDE_HTTPS_KEY for local phone HTTPS.')

export default defineConfig({
  plugins: [react()],
  server: {
    host: certificate ? phoneHost || '0.0.0.0' : '127.0.0.1',
    https: certificate && privateKey ? {cert:readFileSync(certificate),key:readFileSync(privateKey)} : undefined,
    port: 5173,
    strictPort: true,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
