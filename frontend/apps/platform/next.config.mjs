import path from 'path'
import { fileURLToPath } from 'url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// Origens permitidas para Server Actions: configuráveis por env em prod
// (ex.: NEXT_SERVER_ACTIONS_ALLOWED_ORIGINS="app.exemplo.com.br").
const allowedOrigins = process.env.NEXT_SERVER_ACTIONS_ALLOWED_ORIGINS
  ? process.env.NEXT_SERVER_ACTIONS_ALLOWED_ORIGINS.split(',').map((s) => s.trim())
  : ['localhost:3000']

/** @type {import('next').NextConfig} */
const nextConfig = {
  output: 'standalone',
  // Trace files from workspace root so workspace packages are bundled correctly
  outputFileTracingRoot: path.join(__dirname, '../..'),
  transpilePackages: ['@juridico/ui', '@juridico/tokens'],
  experimental: {
    serverActions: { allowedOrigins },
  },
}

export default nextConfig
