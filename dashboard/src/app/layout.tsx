import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { TopNav } from "@/components/top-nav";
import { Footer } from "@/components/footer";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
});
const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-jetbrains",
});

export const metadata: Metadata = {
  title: "Sentinel · Agent Governance",
  description:
    "Gemini-powered control plane: gate every agent tool call, sign every receipt, meter every business unit.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html
      lang="en"
      className={`dark ${inter.variable} ${jetbrains.variable}`}
      suppressHydrationWarning
    >
      <body
        className="min-h-screen bg-background text-foreground"
        style={{ fontFamily: "var(--font-inter), system-ui, sans-serif" }}
      >
        <div className="grid-canvas min-h-screen">
          <TopNav />
          <main className="mx-auto w-full max-w-[1400px] px-6 py-6">
            {children}
          </main>
          <Footer />
        </div>
      </body>
    </html>
  );
}
