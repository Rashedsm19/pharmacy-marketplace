import createMiddleware from "next-intl/middleware";
import { NextRequest, NextResponse } from "next/server";
import { locales, defaultLocale } from "./i18n/config";

const intlMiddleware = createMiddleware({
  locales,
  defaultLocale,
  localePrefix: "always",
});

const PUBLIC_PATHS = [
  "/login",
  "/register",
  "/pending-review",
  "/forgot-password",
  "/reset-password",
];

export default function middleware(request: NextRequest) {
  const pathname = request.nextUrl.pathname;

  // Strip locale prefix for auth check
  const pathnameWithoutLocale = pathname.replace(/^\/(ar|en)/, "") || "/";

  // Check if path is public
  const isPublic = PUBLIC_PATHS.some(
    (p) => pathnameWithoutLocale === p || pathnameWithoutLocale.startsWith(p + "/")
  );

  if (!isPublic) {
    const token = request.cookies.get("access_token")?.value;
    if (!token) {
      const loginUrl = new URL(`/${defaultLocale}/login`, request.url);
      loginUrl.searchParams.set("redirect", pathname);
      return NextResponse.redirect(loginUrl);
    }
  }

  return intlMiddleware(request);
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico|.*\\..*).*)"],
};
