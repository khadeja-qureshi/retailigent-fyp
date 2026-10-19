import type {
  Metadata,
} from "next";

import type {
  ReactNode,
} from "react";

import {
  Geist,
  Geist_Mono,
} from "next/font/google";

import "./globals.css";

import NavBar from "@/components/NavBar";


const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});


const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});


export const metadata: Metadata = {
  title: "Retailigent",
  description:
    "Agentic AI-powered intelligent clothing retail assistant",
};


interface RootLayoutProps {
  children: ReactNode;
}


export default function RootLayout({
  children,
}: RootLayoutProps) {
  return (
    <html
      lang="en"
      className={
        `${geistSans.variable} ` +
        `${geistMono.variable} ` +
        "h-full antialiased"
      }
    >
      <body
        suppressHydrationWarning
        className="min-h-full"
      >
        <NavBar />

        {children}
      </body>
    </html>
  );
}