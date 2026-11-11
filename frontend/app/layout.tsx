import type { Metadata, Viewport } from "next";
import Providers from "@/components/Providers";
import "./globals.css";

export const metadata: Metadata = {
  title: "タカネパトロール君｜年初来高値 更新間近",
  description: "年初来高値まであと数%で、出来高を伴って更新しそうな日本株を毎営業日に抽出します。",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#ffffff" },
    { media: "(prefers-color-scheme: dark)", color: "#0d1117" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja" suppressHydrationWarning>
      <body className="min-h-screen bg-slate-50 text-slate-900 antialiased dark:bg-[#0d1117] dark:text-slate-100">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
