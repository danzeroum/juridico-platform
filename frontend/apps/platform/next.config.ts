import type { NextConfig } from 'next'

const nextConfig: NextConfig = {
  transpilePackages: ['@juridico/ui', '@juridico/tokens'],
  experimental: {
    serverActions: { allowedOrigins: ['localhost:3000'] },
  },
}

export default nextConfig
