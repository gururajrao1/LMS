import type { Metadata } from "next";
import Script from "next/script";
import { Geist, Inter } from "next/font/google";
import "./globals.css";

// DESIGN.md pairs Geist for headings with Inter for body copy. Self-hosting both
// keeps the demo identical on a Mac and on a conference-room Windows machine.
const inter = Inter({ subsets: ["latin"], variable: "--font-inter", display: "swap" });
const geist = Geist({ subsets: ["latin"], variable: "--font-geist", display: "swap" });

export const metadata: Metadata = {
  title: "PharmaLearn",
  description: "Citation-backed medical learning assets",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    // The class on <html> may already be set by the pre-paint script below,
    // so hydration must not complain when React's first render disagrees.
    <html lang="en" suppressHydrationWarning className={`h-full antialiased ${inter.variable} ${geist.variable}`}>
      {/* Same logic as lib/theme.ts, inlined so the first paint already has
          the right theme — no light flash on a dark visit. */}
      <Script
        id="pl-theme-init"
        strategy="beforeInteractive"
        dangerouslySetInnerHTML={{
          __html: `(function(){try{var t=localStorage.getItem("pl-theme");if(t!=="light"&&t!=="dark")t=matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light";if(t==="dark")document.documentElement.classList.add("dark")}catch(e){}})()`,
        }}
      />
      <body className="min-h-full">{children}</body>
    </html>
  );
}
