import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Telecom FAQ Semantic Search",
  description: "Support chat for telecom FAQs backed by semantic search."
};

export default function RootLayout({
  children
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ru">
      <body>{children}</body>
    </html>
  );
}

