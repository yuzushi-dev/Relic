/** @type {import('next').NextConfig} */
const isStaticBuild = process.env.RELIC_UI_BUILD_TARGET === "static";
const basePath = process.env.RELIC_UI_BASE_PATH || "";

const nextConfig = {
  reactStrictMode: true,
  output: isStaticBuild ? "export" : "standalone",
  typedRoutes: true,
  // Expose basePath to the client bundle so client components (e.g. raw <img>
  // tags, which next does not auto-prefix) can build correct asset URLs under
  // the GitHub Pages subpath.
  env: { NEXT_PUBLIC_BASE_PATH: basePath },
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
