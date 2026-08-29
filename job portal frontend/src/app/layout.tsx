import type { Metadata } from "next";
import { ClientChunkRecovery } from "@/components/ClientChunkRecovery";
import { ClientErrorReporter } from "@/components/ClientErrorReporter";
import { AdminAuthRedirect } from "@/components/AdminAuthRedirect";
import { AdSenseScript } from "@/components/AdSenseScript";
import { SiteChrome } from "@/components/SiteChrome";
import { fetchBuildBranding } from "@/lib/api";
import { canonicalSiteUrl } from "@/lib/siteUrl";
import "./globals.css";

function parseKeywords(value: string): string[] {
  return value
    .split(",")
    .map((keyword) => keyword.trim())
    .filter(Boolean);
}

export async function generateMetadata(): Promise<Metadata> {
  const branding = await fetchBuildBranding();
  const title = branding.homepage_meta_title || branding.site_title;
  const description = branding.homepage_meta_description || branding.site_description;
  const logo = branding.logo_url || "/pakistan-jobs-market-logo.png";

  return {
    metadataBase: new URL(canonicalSiteUrl()),
    title: {
      default: title,
      template: `%s | ${branding.site_name}`,
    },
    description,
    keywords: parseKeywords(branding.homepage_meta_keywords),
    icons: {
      icon: logo,
      shortcut: logo,
      apple: logo,
    },
    openGraph: {
      title,
      description,
      type: "website",
      siteName: branding.site_name,
      images: [{ url: logo, alt: `${branding.site_name} logo` }],
    },
    robots: { index: true, follow: true },
  };
}

export default async function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  const branding = await fetchBuildBranding();
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <meta
          {...{
            name: "impact-site-verification",
            value: "db9798fc-f9b2-4459-8ec6-570e00181eae",
          }}
        />
        <meta
          name="google-adsense-account"
          content="ca-pub-1209296651546868"
        />
        <script
          async
          src="https://www.googletagmanager.com/gtag/js?id=G-W6Z1YPL2JY"
        />
        <script
          dangerouslySetInnerHTML={{
            __html: `window.dataLayer = window.dataLayer || [];
function gtag(){dataLayer.push(arguments);}
gtag('js', new Date());
gtag('config', 'G-W6Z1YPL2JY');`,
          }}
        />
        <script
          dangerouslySetInnerHTML={{
            __html: `(function(){try{var t=localStorage.getItem('pakjobs-theme');if(t==='light'||t==='dark'){document.documentElement.setAttribute('data-theme',t);}else if(window.matchMedia('(prefers-color-scheme: light)').matches){document.documentElement.setAttribute('data-theme','light');}}catch(e){}})();`,
          }}
        />
        <AdSenseScript />
      </head>
      <body className="antialiased font-sans">
        <AdminAuthRedirect />
        <ClientChunkRecovery />
        <ClientErrorReporter />
        <SiteChrome initialBranding={branding}>{children}</SiteChrome>
      </body>
    </html>
  );
}
