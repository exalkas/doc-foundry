import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";
import { AdminAuthProvider } from "@/contexts/admin-auth-context";
import { ErrorBoundary } from "@/components/error-boundary";
import { Toaster } from "@/components/ui/toaster";

const inter = Inter({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "DocFoundry.app Admin",
  description: "Admin platform for DocFoundry.app",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <ErrorBoundary>
          <Providers>
            <AdminAuthProvider>
              {children}
              <Toaster />
            </AdminAuthProvider>
          </Providers>
        </ErrorBoundary>
      </body>
    </html>
  );
}
