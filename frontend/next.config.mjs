/** @type {import('next').NextConfig} */
const nextConfig = {
  async rewrites() {
    const api = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
    return [
      { source: "/api/:path*", destination: `${api}/api/:path*` },
      { source: "/assets/:path*", destination: `${api}/assets/:path*` },
    ];
  },
  devIndicators: {
    buildActivity: false,
  },
};
export default nextConfig;
