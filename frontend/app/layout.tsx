import type { Metadata } from "next";
import { Inter } from "next/font/google";
import type { ReactNode } from "react";

import { ExtractionProvider } from "@/context/ExtractionContext";
import "./globals.css";

// Self-hosted at build time, so the app needs no external font request.
const inter = Inter({ subsets: ["latin"], variable: "--font-sans", display: "swap" });

export const metadata: Metadata = {
  title: "Hardware Set Extractor",
  description:
    "Review hardware sets extracted from Division 08 construction specification documents.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en" className={inter.variable}>
      <body>
        <ExtractionProvider>{children}</ExtractionProvider>
      </body>
    </html>
  );
}
