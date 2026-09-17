export default function RootNotFound() {
  return (
    <html lang="ar" dir="rtl">
      <body className="min-h-screen bg-[#fffdf9] text-[#1f2a24] flex items-center justify-center p-6">
        <main className="text-center max-w-md">
          <p className="text-6xl font-black text-[#a88d60]">404</p>
          <h1 className="mt-4 text-xl font-bold">الصفحة غير موجودة</h1>
          <p className="mt-2 text-sm text-[#6d746d]">
            الصفحة التي تحاول الوصول إليها غير موجودة أو تم نقلها.
          </p>
          <p lang="en" dir="ltr" className="mt-1 text-xs text-[#9a8b77]">
            The page you are looking for could not be found.
          </p>
          <a
            href="/"
            className="mt-6 inline-flex h-11 items-center justify-center rounded-full bg-[#1f2a24] px-5 text-sm font-medium text-[#fbf7f0] transition-colors hover:bg-brand-800"
          >
            العودة للرئيسية
          </a>
        </main>
      </body>
    </html>
  );
}
