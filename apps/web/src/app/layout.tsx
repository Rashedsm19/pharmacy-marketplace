import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "سوق الصيدليات | Pharmacy Near-Expiry Marketplace",
  description: "منصة لبيع وشراء الأدوية قرب انتهاء الصلاحية بين الصيدليات",
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
