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
    ];
  },
};

module.exports = nextConfig;
