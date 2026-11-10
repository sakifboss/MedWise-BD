import type { Metadata, Viewport } from "next";
import { Geist, Geist_Mono, Noto_Sans_Bengali } from "next/font/google";

import { OfflineBanner } from "@/components/offline";
import { SiteFooter } from "@/components/site-footer";
import { ServiceWorkerRegistration } from "@/components/pwa";
import { SiteHeader } from "@/components/site-header";
import { LangProvider } from "@/i18n/client";
import { getDict, getLang } from "@/i18n/server";

import "./globals.css";

const geistSans = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });
const geistMono = Geist_Mono({ variable: "--font-geist-mono", subsets: ["latin"] });
// Renders Bangla search input and names on devices without a Bangla font.
const notoBengali = Noto_Sans_Bengali({ variable: "--font-bengali", subsets: ["bengali"] });

export async function generateMetadata(): Promise<Metadata> {
  const t = await getDict();
  return {
    title: { default: t.meta.title, template: "%s · MedWise BD" },
    description: t.meta.description,
    applicationName: "MedWise BD",
    appleWebApp: { capable: true, title: "MedWise BD", statusBarStyle: "default" },
  };
}

export const viewport: Viewport = { themeColor: "#007565" };

export default async function RootLayout({ children }: LayoutProps<"/">) {
  const lang = await getLang();
  return (
    <html
      lang={lang}
      className={`${geistSans.variable} ${geistMono.variable} ${notoBengali.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col">
        <LangProvider lang={lang}>
          <SiteHeader />
          <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-6 sm:py-10">
            <OfflineBanner />
            {children}
          </main>
          <SiteFooter />
          <ServiceWorkerRegistration />
        </LangProvider>
      </body>
    </html>
  );
}
