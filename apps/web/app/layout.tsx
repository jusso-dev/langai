import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = {
  title: "LangAI · Language workspaces",
  description:
    "Private dictionary datasets, representation training and model deployment.",
};
export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
