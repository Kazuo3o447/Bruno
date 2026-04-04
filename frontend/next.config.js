/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  swcMinify: true,
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: 'http://bruno-backend:8000/api/:path*',
      },
      {
        source: '/ws/:path*',
        destination: 'http://bruno-backend:8000/ws/:path*',
      },
      {
        source: '/logs/ws',
        destination: 'http://bruno-backend:8000/logs/ws',
      },
    ];
  },
};

module.exports = nextConfig;
