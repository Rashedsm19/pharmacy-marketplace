import { NextIntlClientProvider } from "next-intl";
import { getMessages } from "next-intl/server";
import { notFound } from "next/navigation";
import { locales } from "@/i18n/config";
import Providers from "@/components/providers";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "سوق الصيدليات | Pharmacy Near-Expiry Marketplace",
  description: "منصة لبيع وشراء الأدوية قرب انتهاء الصلاحية بين الصيدليات",
  icons: {
    icon: "/medsave-logo.png",
    apple: "/medsave-logo.png",
  },
};

export default async function LocaleLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ locale: string }>;
}) {
  const { locale } = await params;

  if (!locales.includes(locale as "ar" | "en")) {
    notFound();
  }

  const messages = await getMessages();

  return (
    <html lang={locale} dir={locale === "ar" ? "rtl" : "ltr"}>
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=Tajawal:wght@300;400;500;700;900&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <NextIntlClientProvider messages={messages}>
          <Providers>{children}</Providers>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
