import type { Metadata } from "next";
import "./globals.css";
import { TopNav } from "@/components/top-nav";

export const metadata: Metadata = {
  title: "Sentinel — Agent Governance",
  description: "Gemini-powered control plane for enterprise agent fleets.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="min-h-screen bg-background font-sans antialiased">
        <TopNav />
        <main className="container py-6">{children}</main>
      </body>
    </html>
  );
}
