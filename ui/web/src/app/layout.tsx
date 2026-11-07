import type { Metadata } from "next";
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
      <head>
        {/* First paint already has the right theme — no light flash on a dark
            visit. A plain blocking script in <head>, so it runs before React
            paints anything; see public/theme-init.js. */}
        <script src="/theme-init.js" />
      </head>
      <body className="min-h-full">{children}</body>
    </html>
  );
}
