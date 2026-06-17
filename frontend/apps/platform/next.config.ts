import path from 'path'
import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  output: 'standalone',
  // Trace files from workspace root so workspace packages are bundled correctly
  outputFileTracingRoot: path.join(__dirname, '../..'),
  transpilePackages: ['@juridico/ui', '@juridico/tokens'],
  experimental: {
    serverActions: { allowedOrigins: ['localhost:3000'] },
  },
}

export default nextConfig
