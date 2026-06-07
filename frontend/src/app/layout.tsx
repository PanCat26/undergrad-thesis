import type { Metadata } from "next";

import { Toaster } from "@/components/ui/sonner";
import { AuthProvider } from "@/lib/auth";
import "./globals.css";

export const metadata: Metadata = {
  title: "Agentic Research Tool",
  description: "A LaTeX workspace with grounded, agentic research over your sources.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className="min-h-screen bg-background antialiased">
        <AuthProvider>{children}</AuthProvider>
        <Toaster richColors position="top-right" offset={{ top: 80, right: 16 }} />
      </body>
    </html>
  );
}
