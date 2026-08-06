import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Kalshi AI Research Terminal",
  description: "AI-assisted research and paper-trading dashboard for Kalshi prediction markets.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen">
        <header className="flex items-center justify-between border-b border-slate-800 px-6 py-4">
          <div>
            <a href="/" className="text-lg font-semibold tracking-tight">
              Kalshi AI Research Terminal
            </a>
            <p className="text-xs text-slate-500">
              Research &amp; decision-support only — not financial advice.
            </p>
          </div>
          <a href="/portfolio" className="text-sm text-slate-400 hover:text-emerald-400">
            Portfolio
          </a>
        </header>
        <main className="mx-auto max-w-6xl px-6 py-8">{children}</main>
      </body>
    </html>
  );
}
