import type { Metadata } from "next";
import "./globals.css";

const basePath = process.env.RELIC_UI_BASE_PATH || "";

export const metadata: Metadata = {
  title: "Researcher Workbench · Relic",
  icons: {
    icon: `${basePath}/icon.svg`,
  },
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        {/* Theme init — runs before paint to prevent flash */}
        <script
          dangerouslySetInnerHTML={{
            __html: `try{var t=localStorage.getItem('relic-theme');if(t!=='light'&&t!=='dark'){t=matchMedia('(prefers-color-scheme: light)').matches?'light':'dark'}document.documentElement.dataset.theme=t}catch(e){}`,
          }}
        />
        {/* Skip navigation — WCAG 2.4.1 */}
        <a href="#main-content" className="skip-nav">
          Skip to main content
        </a>
        {children}
      </body>
    </html>
  );
}
