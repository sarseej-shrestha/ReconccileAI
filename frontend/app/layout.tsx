import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "ReconcileAI · Financial operations",
  description:
    "Intelligent financial reconciliation, with every decision accounted for.",
};
export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
