"use client";
import { ThemeProvider } from "next-themes";
import { PrefsProvider } from "@/lib/prefs";

export default function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      <PrefsProvider>{children}</PrefsProvider>
    </ThemeProvider>
  );
}
