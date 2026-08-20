import type { Metadata } from "next";
import type { ReactNode } from "react";

import { ExtractionProvider } from "@/context/ExtractionContext";
import "./globals.css";

export const metadata: Metadata = {
  title: "Hardware Set Extractor",
  description:
    "Review hardware sets extracted from Division 08 construction specification documents.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <ExtractionProvider>{children}</ExtractionProvider>
      </body>
    </html>
  );
}
