import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { SideNav } from "@/components/SideNav";
import { ThemeScript } from "@/components/ThemeScript";
import { Footer } from "@/components/Footer";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans", display: "swap" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono", display: "swap" });

export const metadata: Metadata = {
  title: { default: "LeanGraph", template: "%s · LeanGraph" },
  description:
    "A benchmark of LLM agents writing Lean 4 proofs, where a proof counts only if Lean verifies it: retrieval, planning and compiler-feedback repair, measured and ablated.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${mono.variable}`} suppressHydrationWarning>
      <head>
        <ThemeScript />
      </head>
      <body className="flex min-h-dvh flex-col lg:flex-row">
        <SideNav />
        <div className="flex min-w-0 flex-1 flex-col">
          <main className="flex-1 px-5 py-8 sm:px-10 lg:py-12">
            <div className="mx-auto max-w-content">{children}</div>
          </main>
          <Footer />
        </div>
      </body>
    </html>
  );
}
