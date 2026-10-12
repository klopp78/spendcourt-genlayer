import type { Metadata } from "next";
import "./globals.css";
export const metadata: Metadata = { title: "SpendCourt for GenLayer", description: "Consensus settlement for delegated AI-agent work." };
export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) { return <html lang="en"><body>{children}</body></html>; }
