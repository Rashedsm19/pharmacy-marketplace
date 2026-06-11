import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "MedSave | منصة تداول مخزون الصيدليات",
  description: "منصة سعودية عملية لإدارة وتداول مخزون الصيدليات المرخصة قبل انتهاء الصلاحية",
  icons: {
    icon: "/medsave-logo.png",
    apple: "/medsave-logo.png",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
