/** @type {import('next').NextConfig} */
const isStaticBuild = process.env.RELIC_UI_BUILD_TARGET === "static";
const basePath = process.env.RELIC_UI_BASE_PATH || "";

const nextConfig = {
  reactStrictMode: true,
  output: isStaticBuild ? "export" : "standalone",
  typedRoutes: true,
  ...(basePath ? { basePath } : {}),
  ...(isStaticBuild
    ? { trailingSlash: true, images: { unoptimized: true } }
    : {
        async redirects() {
          return [{ source: "/", destination: "/dashboard", permanent: false }];
        },
      }),
};

export default nextConfig;
