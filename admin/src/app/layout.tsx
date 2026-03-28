import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "NebulaNet Admin",
  description: "NebulaNet Network Monitor — Super Admin Portal",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="ru" className="h-full">
      <body className="min-h-full flex flex-col bg-[#0f1117] text-slate-200">
        {children}
      </body>
    </html>
  );
}
